"""Sayfa izleyici connector'ü — metu.edu.tr sayfalarını hash-diff ile izler.

Polite crawling: sayfa başına döngüde tek istek, timeout var, retry yok.
İçerik normalize edilir (script/style çıkarılır, etiketler sökülür,
boşluklar teke düşer) ve SHA-256 ile hash'lenir; değişim ``page_changes``
tablosuna yazılır.

İzleme listesi ``watched_pages`` tablosunda tutulur (url, selector?,
last_hash, last_change). ``selector`` basit ``#id`` / ``.class`` desteği
verir (best-effort); boşsa tüm sayfa normalleştirilir.

Varsayılan liste: OIDB duyurular, CENG bölüm duyuruları, registrar.
Genişletme::

    page_watcher.add_watch(conn, "https://example.metu.edu.tr/duyurular",
                           selector="#announcements", etiket="Örnek")
"""

from __future__ import annotations

import hashlib
import re
import sqlite3
from datetime import datetime
from html.parser import HTMLParser

import httpx

DEFAULT_TIMEOUT = 15.0
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) devrimo-watcher/0.4"

DEFAULT_WATCHES = [
    ("https://oidb.metu.edu.tr/tr/duyurular", None, "OIDB Duyurular"),
    ("https://www.ceng.metu.edu.tr/announcements", None, "CENG Bölüm Duyuruları"),
    ("https://registrar.metu.edu.tr", None, "Registrar"),
]

_VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input",
              "link", "meta", "param", "source", "track", "wbr"}


def ensure_tables(conn: sqlite3.Connection) -> None:
    conn.execute(
        """CREATE TABLE IF NOT EXISTS watched_pages (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               url TEXT NOT NULL UNIQUE,
               selector TEXT,
               etiket TEXT,
               last_hash TEXT,
               last_change TEXT)"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS page_changes (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               url TEXT NOT NULL,
               eski_hash TEXT,
               yeni_hash TEXT NOT NULL,
               ozet TEXT,
               created_at TEXT NOT NULL DEFAULT (datetime('now')))"""
    )


def seed_default_watches(conn: sqlite3.Connection) -> int:
    """Tablo boşsa varsayılan izleme listesini ekler; eklenen satır sayısını döner."""
    n = conn.execute("SELECT COUNT(*) FROM watched_pages").fetchone()[0]
    if n:
        return 0
    for url, selector, etiket in DEFAULT_WATCHES:
        conn.execute(
            "INSERT OR IGNORE INTO watched_pages (url, selector, etiket) VALUES (?, ?, ?)",
            (url, selector, etiket),
        )
    return conn.total_changes


def add_watch(conn: sqlite3.Connection, url: str, selector: str | None = None,
              etiket: str | None = None) -> None:
    conn.execute(
        "INSERT INTO watched_pages (url, selector, etiket) VALUES (?, ?, ?) "
        "ON CONFLICT(url) DO UPDATE SET selector=excluded.selector, etiket=excluded.etiket",
        (url, selector, etiket),
    )


def remove_watch(conn: sqlite3.Connection, url: str) -> bool:
    cur = conn.execute("DELETE FROM watched_pages WHERE url = ?", (url,))
    return cur.rowcount > 0


def list_watches(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT url, selector, etiket, last_hash, last_change "
        "FROM watched_pages ORDER BY id"
    ).fetchall()
    return [
        {"url": u, "selector": s, "etiket": e, "last_hash": h, "last_change": c}
        for u, s, e, h, c in rows
    ]


class _TextOnly(HTMLParser):
    """script/style/noscript dışındaki metin düğümlerini toplar."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip = 0
        self.buf: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self._skip += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript") and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip and data.strip():
            self.buf.append(data)


def normalize_html(page: str) -> str:
    p = _TextOnly()
    p.feed(page or "")
    return " ".join(" ".join(p.buf).split())


def content_hash(normalized: str) -> str:
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


class _BlockFinder(HTMLParser):
    """Verilen #id veya .class değerini taşıyan ilk açılış etiketinin konumunu bulur."""

    def __init__(self, attr_name: str, attr_value: str) -> None:
        super().__init__(convert_charrefs=True)
        self.attr_name = attr_name
        self.attr_value = attr_value
        self.hit: tuple[int, str] | None = None  # (char offset, tag)

    def handle_starttag(self, tag, attrs):
        if self.hit is not None or tag in _VOID_TAGS:
            return
        d = dict(attrs)
        if self.attr_name == "class":
            ok = self.attr_value in (d.get("class") or "").split()
        else:
            ok = d.get(self.attr_name) == self.attr_value
        if ok:
            line, col = self.getpos()
            self.hit = (self._line_offsets[line - 1] + col, tag)

    def feed_with_offsets(self, page: str) -> None:
        self._line_offsets = [0]
        for i, ch in enumerate(page):
            if ch == "\n":
                self._line_offsets.append(i + 1)
        self.feed(page)


_TAG_RE = re.compile(r"<(/?)([a-zA-Z][a-zA-Z0-9]*)((?:\"[^\"]*\"|'[^']*'|[^'\">])*)>")


def extract_selector_block(page: str, selector: str) -> str:
    """Basit CSS seçici desteği: yalnızca ``#id`` ve ``.class``; bulunamazsa tüm sayfa."""
    selector = (selector or "").strip()
    m = re.fullmatch(r"#([\w-]+)|\.([\w-]+)", selector)
    if not m:
        return page
    finder = _BlockFinder("id" if m.group(1) else "class", m.group(1) or m.group(2))
    finder.feed_with_offsets(page)
    if finder.hit is None:
        return page
    start, tag = finder.hit
    gt = page.find(">", start)
    if gt == -1:
        return page[start:]
    body_start = gt + 1
    depth = 1
    for t in _TAG_RE.finditer(page, body_start):
        closing, name = t.group(1), t.group(2).lower()
        if name != tag.lower():
            continue
        if closing:
            depth -= 1
            if depth == 0:
                return page[start:t.end()]
        elif t.group(0).rstrip().endswith("/>") or name in _VOID_TAGS:
            continue
        else:
            depth += 1
    return page[start:]


def fetch_page(url: str, timeout: float = DEFAULT_TIMEOUT) -> str:
    resp = httpx.get(
        url,
        timeout=timeout,
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT},
    )
    resp.raise_for_status()
    return resp.text


def check_page(conn: sqlite3.Connection, watch: dict,
               timeout: float = DEFAULT_TIMEOUT) -> dict:
    """Tek sayfayı tarar. İlk kontrolde taban hash'i alınır, değişim bildirilmez."""
    url, selector = watch["url"], watch.get("selector")
    page = fetch_page(url, timeout=timeout)
    normalized = normalize_html(extract_selector_block(page, selector) if selector else page)
    h = content_hash(normalized)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    out: dict = {"url": url, "etiket": watch.get("etiket"), "yeni_hash": h}

    if not watch.get("last_hash"):
        conn.execute(
            "UPDATE watched_pages SET last_hash = ?, last_change = ? WHERE url = ?",
            (h, now, url),
        )
        out["durum"] = "taban"
        return out

    if h == watch["last_hash"]:
        out["durum"] = "ayni"
        return out

    conn.execute(
        "INSERT INTO page_changes (url, eski_hash, yeni_hash, ozet) VALUES (?, ?, ?, ?)",
        (url, watch["last_hash"], h, normalized[:200]),
    )
    conn.execute(
        "UPDATE watched_pages SET last_hash = ?, last_change = ? WHERE url = ?",
        (h, now, url),
    )
    out.update({"durum": "degisti", "ozet": normalized[:200], "tarih": now})
    return out


def check_all(conn: sqlite3.Connection, timeout: float = DEFAULT_TIMEOUT) -> list[dict]:
    results: list[dict] = []
    for watch in list_watches(conn):
        try:
            results.append(check_page(conn, watch, timeout=timeout))
        except Exception as e:  # polite: tek sayfanın hatası döngüyü bozmaz
            results.append({"url": watch["url"], "etiket": watch.get("etiket"),
                            "durum": "hata", "hata": f"{type(e).__name__}: {e}"})
    return results
