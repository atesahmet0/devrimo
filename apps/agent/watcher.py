"""Arka plan izleyici thread'i — watched_pages taraması + deadline kontrolü.

main.py lifespan'ında başlatılır: her WATCHER_INTERVAL_SECS'te bir
(varsayılan 15 dk) izlenen sayfalar hash-diff ile taranır, yaklaşan
deadline'lar süzülür; yeni bulgular SQLite ``notifications`` tablosuna
yazılır (dedupe anahtarıyla, tekrar bildirilmez).

main.py'den bağımsızdır: DB erişimi ve assignment kaynağı start() ile enjekte
edilir. Durum healthz'e status() ile yansır.
"""

from __future__ import annotations

import os
import threading
from contextlib import closing
from datetime import datetime

from packages.connectors import deadlines, page_watcher

WATCHER_INTERVAL_SECS = max(5, int(os.environ.get("WATCHER_INTERVAL_SECS", "900")))
DEADLINE_WINDOW_DAYS = int(os.environ.get("DEADLINE_WINDOW_DAYS", "7"))

_lock = threading.Lock()
_thread: threading.Thread | None = None
_stop = threading.Event()
_state: dict = {"aktif": False, "dongu": 0, "son_tarama": None, "son_hata": None}
_db_factory = None
_assignments_provider = None


def ensure_tables(conn) -> None:
    conn.execute(
        """CREATE TABLE IF NOT EXISTS notifications (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               tur TEXT NOT NULL CHECK(tur IN ('sayfa','deadline')),
               baslik TEXT NOT NULL,
               detay TEXT,
               url TEXT,
               dedupe TEXT UNIQUE,
               okundu INTEGER NOT NULL DEFAULT 0,
               created_at TEXT NOT NULL DEFAULT (datetime('now')))"""
    )


def notify(conn, tur: str, baslik: str, detay: str | None = None,
           url: str | None = None, dedupe: str | None = None) -> bool:
    cur = conn.execute(
        "INSERT OR IGNORE INTO notifications (tur, baslik, detay, url, dedupe) "
        "VALUES (?, ?, ?, ?, ?)",
        (tur, baslik, detay, url, dedupe),
    )
    return cur.rowcount > 0


def unread_count(conn) -> int:
    return conn.execute("SELECT COUNT(*) FROM notifications WHERE okundu = 0").fetchone()[0]


def status() -> dict:
    with _lock:
        out = dict(_state)
    out["aralik_dk"] = round(WATCHER_INTERVAL_SECS / 60, 1)
    out["deadline_pencere_gun"] = DEADLINE_WINDOW_DAYS
    if _thread is not None:
        out["thread"] = _thread.name
        out["canli"] = _thread.is_alive()
    else:
        out["canli"] = False
    return out


def start(db_factory, assignments_provider) -> None:
    """Watcher thread'ini başlatır (idempotent). İlk döngü hemen çalışır."""
    global _db_factory, _assignments_provider, _thread
    with _lock:
        if _thread is not None and _thread.is_alive():
            return
        _db_factory = db_factory
        _assignments_provider = assignments_provider
        _stop.clear()
        with closing(db_factory()) as conn, conn:
            page_watcher.ensure_tables(conn)
            ensure_tables(conn)
            page_watcher.seed_default_watches(conn)
        _state.update(aktif=True, dongu=0, son_tarama=None, son_hata=None)
        _thread = threading.Thread(target=_run, name="devrimo-watcher", daemon=True)
        _thread.start()


def stop() -> None:
    _stop.set()


def _run() -> None:
    while not _stop.is_set():
        try:
            _cycle()
            _state["son_hata"] = None
        except Exception as e:  # thread asla ölmesin
            _state["son_hata"] = f"{type(e).__name__}: {e}"
        _state["dongu"] += 1
        _state["son_tarama"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        _stop.wait(WATCHER_INTERVAL_SECS)


def _cycle() -> None:
    with closing(_db_factory()) as conn, conn:
        for ch in page_watcher.check_all(conn):
            if ch.get("durum") == "degisti":
                notify(
                    conn,
                    "sayfa",
                    f"Sayfa güncellendi: {ch.get('etiket') or ch['url']}",
                    detay=ch.get("ozet"),
                    url=ch["url"],
                    dedupe=f"sayfa:{ch['url']}:{ch['yeni_hash']}",
                )

        assignments: list[dict] = []
        try:
            assignments = _assignments_provider() or []
        except Exception:
            assignments = []
        for d in deadlines.filter_upcoming(assignments, days=DEADLINE_WINDOW_DAYS):
            kalan = d.get("kalan_gun")
            kalan_txt = "bugün" if isinstance(kalan, (int, float)) and kalan < 1 \
                else f"~{kalan} gün"
            notify(
                conn,
                "deadline",
                f"{d.get('course', '')}: {d.get('ad', '')} — son {kalan_txt}",
                detay=d.get("teslim"),
                url=d.get("url"),
                dedupe=f"deadline:{d.get('course', '')}:{d.get('ad', '')}:{d.get('teslim')}",
            )
