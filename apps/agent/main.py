"""Devrimo agent core.

FastAPI servisi: OpenAI-uyumlu LLM'e bağlanır, elle yazılmış tool-calling
loop'u çalıştırır, sohbet geçmişini SQLite'ta tutar. Tek demo kullanıcısı,
auth yok.

Araç verisi: ODTUCLASS_URL / ODTU_USERNAME / ODTU_PASSWORD doluysa gerçek
ODTÜClass connector'ü kullanılır; boşsa demo stub'ına düşer. Webmail için
MAIL_USERNAME / MAIL_PASSWORD doluysa IMAP üzerinden salt-okunur okuma/
arama yapılır; boşsa yine demo stub döner. Ayrıca arka planda watcher
thread'i metu sayfalarını izler ve deadline uyarısı üretir
(bkz. watcher.py).
"""

import asyncio
import json
import os
import sqlite3
import sys
import time
from contextlib import asynccontextmanager, closing
from datetime import date, timedelta
from pathlib import Path

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# Load .env from apps/agent/.env (and fall back to repo root .env), letting .env win over inherited env.
for _p in (Path(__file__).resolve().parent / ".env", _REPO_ROOT / ".env"):
    if _p.exists():
        load_dotenv(_p, override=True)

from packages.connectors import conflicts, deadlines, odtuclass, page_watcher, sais, webmail  # noqa: E402

import watcher  # noqa: E402

BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
API_KEY = os.environ.get("OPENAI_API_KEY", "")
MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

DB_PATH = Path(os.environ.get("DEVROMO_DB_PATH") or Path(__file__).parent / "data" / "devrimo.db")
MAX_TOOL_ROUNDS = 5
HISTORY_LIMIT = 20

SYSTEM_PROMPT = (
    "Sen Devrimo'sun: ODTÜ öğrencileri için bir asistan. Kısa ve net Türkçe cevap ver. "
    "Dersler, duyurular, ödevler, notlar veya ders programıyla ilgili sorularda elindeki "
    "araçları kullan; bilmediğini uydurma. Araç cevaplarında 'kaynak' alanı verinin "
    "gerçek ODTÜClass'tan mı yoksa demo stub'dan mı geldiğini belirtir; kaynağa göre konuş. "
    "'Yaklaşan ödev/deadline', 'yenilik/bildirim var mı' gibi sorularda get_deadlines, "
    "check_updates ve get_notifications araçlarını kullan; izleyici arka planda metu.edu.tr "
    "sayfalarını tarar. 'Okunmamış maillerim', 'mailim var mı', 'maillerde ... ara' gibi "
    "sorularda get_unread_mails ve search_emails araçlarını kullan; METU webmail salt-okunur "
    "erişilir, mail gönderme yok. "
    "'Bugün ne kaçırabilirim', 'günlük özet', 'günün özeti' gibi sorularda get_daily_digest "
    "aracının döndürdüğü birleşik ham akışı (duyurular + sayfa değişiklikleri + okunmamış "
    "mailler) en önemli öğeden başlayarak kısa Türkçe madde listesine çevir; her maddede "
    "kaynağı köşeli parantezle belirt (örn. [CENG 242], [OIDB], [Mail]). "
    "'Programımda çakışma var mı', 'derslerim çakışıyor mu' gibi sorularda "
    "check_schedule_conflicts aracını kullan: tip'i 'cakisma' olanlar uyarıdır, "
    "'lab_bilgi' olanlar aynı dersin lab saati olduğu için yalnızca bilgidir. "
    "SAIS ile ilgili sorularda (öğrenci bilgisi, transkript, dönem programı) "
    "get_sais_info, get_sais_schedule ve get_sais_transcript araçlarını kullan."
)

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_courses",
            "description": "Öğrencinin bu dönemki ders listesini döndürür.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_announcements",
            "description": "Duyuruları döndürür. İsteğe bağlı 'course' parametresi ile tek dersin duyuruları alınır.",
            "parameters": {
                "type": "object",
                "properties": {"course": {"type": "string", "description": "Ders kodu/adı, örn. 'CENG 242'. Boşsa tüm dersler."}},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_assignments",
            "description": "Ödevleri ve teslim tarihlerini döndürür.",
            "parameters": {
                "type": "object",
                "properties": {"course": {"type": "string", "description": "İsteğe bağlı ders filtresi."}},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_grades",
            "description": "Ders notlarını döndürür.",
            "parameters": {
                "type": "object",
                "properties": {"course": {"type": "string", "description": "İsteğe bağlı ders filtresi."}},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_today_schedule",
            "description": "Bugünkü ders programını döndürür.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_updates",
            "description": "İzlenen metu.edu.tr sayfalarında (OIDB, CENG, registrar) izleyicinin yakaladığı son değişiklikleri döndürür.",
            "parameters": {
                "type": "object",
                "properties": {"limit": {"type": "integer", "description": "Kaç kayıt dönsün (varsayılan 10)."}},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_deadlines",
            "description": "Yaklaşan ödev/teslim deadline'larını gün penceresiyle süzer ve kalan günle döndürür.",
            "parameters": {
                "type": "object",
                "properties": {"days": {"type": "integer", "description": "Pencere kaç gün? Varsayılan 7."}},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_notifications",
            "description": "Okunmamış bildirimleri (sayfa değişikliği + yaklaşan deadline uyarıları) döndürür ve okundu işaretler.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_unread_mails",
            "description": "METU webmail'deki okunmamış mailleri döndürür (salt-okunur).",
            "parameters": {
                "type": "object",
                "properties": {"limit": {"type": "integer", "description": "Kaç mail dönsün (varsayılan 20)."}},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_emails",
            "description": "Maillerde Gönderen/Konu/Gövde araması yapar (salt-okunur).",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Anahtar kelime, ör. 'ödev', 'kayıt' veya bir ders kodu."},
                    "limit": {"type": "integer", "description": "Kaç sonuç dönsün (varsayılan 10)."},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_daily_digest",
            "description": "Duyurular + izlenen sayfa değişiklikleri + okunmamış mailleri tek ham metinde birleştirir; özetleme kullanıcıya kalmıştır.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Bölüm başına kaç kayıt (varsayılan 5)."}
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_schedule_conflicts",
            "description": "Haftalık ders programındaki saat çakışmalarını denetler: farklı dersler kesişiyorsa 'cakisma', aynı ders kodunun lab'ı kesişiyorsa 'lab_bilgi' döner.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_sais_info",
            "description": "SAIS öğrenci bilgilerini döndürür (ad, numara, bölüm, sınıf, danışman, GNO).",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_sais_schedule",
            "description": "SAIS haftalık ders programını döndürür.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_sais_transcript",
            "description": "SAIS transkript / dönem notlarını döndürür.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
]

ANNOUNCEMENTS = [
    {"course": "CENG 242", "title": "Ödev 3 yayınlandı", "due": "2026-09-04"},
    {"source": "OIDB", "title": "Kayıt yenileme 31 Ağustos'ta bitiyor", "date": "2026-08-22"},
    {"course": "MATH 260", "title": "Vize kağıtları görüldü", "date": "2026-08-20"},
]

WEEKLY_SCHEDULE = {
    "Pazartesi": [("09:40", "10:30", "MATH 120 Matematik II", "M-13"), ("10:40", "12:30", "CENG 242 Veri Yapıları", "EA-Z01")],
    "Salı": [("13:40", "15:30", "PHYS 106 Fizik II", "P-02")],
    "Çarşamba": [("08:40", "09:30", "ENG 102 İngilizce", "D-114"), ("09:40", "11:30", "CENG 242 Veri Yapıları Lab", "BLG-Lab")],
    "Perşembe": [("09:40", "11:30", "MATH 260 Ayrık Matematik", "M-04")],
    "Cuma": [("10:40", "12:30", "STAT 201 İstatistik", "İ-05")],
}
DAY_NAMES = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]

STUB_COURSES = [
    {"id": "ceng242", "kod": "CENG 242", "ad": "Veri Yapıları"},
    {"id": "math120", "kod": "MATH 120", "ad": "Matematik II"},
    {"id": "math260", "kod": "MATH 260", "ad": "Ayrık Matematik"},
    {"id": "phys106", "kod": "PHYS 106", "ad": "Fizik II"},
    {"id": "eng102", "kod": "ENG 102", "ad": "İngilizce"},
    {"id": "stat201", "kod": "STAT 201", "ad": "İstatistik"},
]

def _in_days(n: int) -> str:
    return (date.today() + timedelta(days=n)).strftime("%Y-%m-%d")


STUB_ASSIGNMENTS = [
    {"course": "CENG 242", "ad": "Ödev 3", "teslim": _in_days(9), "aciklama": "Late policy: her gün %10."},
    {"course": "MATH 260", "ad": "Problem seti 5", "teslim": _in_days(13), "aciklama": ""},
    {"course": "PHYS 106", "ad": "Lab raporu 1", "teslim": _in_days(3), "aciklama": ""},
]


_odtu_client = None


def _get_odtu_client():
    global _odtu_client
    if not odtuclass.is_configured():
        return None
    if _odtu_client is None:
        _odtu_client = odtuclass.from_env()
    return _odtu_client


def db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS messages (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               role TEXT NOT NULL CHECK(role IN ('user','assistant')),
               content TEXT NOT NULL,
               created_at TEXT NOT NULL DEFAULT (datetime('now')))"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS cache (
               key TEXT PRIMARY KEY,
               payload TEXT NOT NULL,
               fetched_at TEXT NOT NULL DEFAULT (datetime('now')))"""
    )
    page_watcher.ensure_tables(conn)
    watcher.ensure_tables(conn)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS credentials (
               key TEXT PRIMARY KEY,
               value TEXT NOT NULL,
               updated_at TEXT NOT NULL DEFAULT (datetime('now')))"""
    )
    return conn


def cred_get(key: str) -> str | None:
    with closing(db()) as conn:
        row = conn.execute("SELECT value FROM credentials WHERE key=?", (key,)).fetchone()
        return row[0] if row else None


def cred_set(key: str, value: str) -> None:
    with closing(db()) as conn:
        with conn:
            conn.execute(
                "INSERT INTO credentials (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=datetime('now')",
                (key, value),
            )


def cred_delete(service: str) -> None:
    prefix = service + "_"
    with closing(db()) as conn:
        with conn:
            conn.execute("DELETE FROM credentials WHERE key LIKE ?", (prefix + "%",))
            conn.execute("DELETE FROM credentials WHERE key=?", (service,))


def _masked(s: str | None) -> str:
    if not s:
        return ""
    s = s.strip()
    if len(s) <= 3:
        return s[0] + "***" if len(s) > 1 else "***"
    return s[:3] + "***"


def _eff(env_key: str, cred_key: str) -> str | None:
    v = cred_get(cred_key)
    if v:
        return v
    return os.environ.get(env_key) or None



def load_history(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT role, content FROM (SELECT * FROM messages ORDER BY id DESC LIMIT ?) ORDER BY id ASC",
        (HISTORY_LIMIT,),
    ).fetchall()
    return [{"role": r, "content": c} for r, c in rows]


def save_message(conn: sqlite3.Connection, role: str, content: str) -> None:
    conn.execute("INSERT INTO messages (role, content) VALUES (?, ?)", (role, content))


def cache_write(conn: sqlite3.Connection, key: str, data) -> None:
    conn.execute(
        "INSERT INTO cache (key, payload) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET payload=excluded.payload, fetched_at=datetime('now')",
        (key, json.dumps(data, ensure_ascii=False)),
    )


def cache_read(conn: sqlite3.Connection, key: str):
    row = conn.execute("SELECT payload, fetched_at FROM cache WHERE key = ?", (key,)).fetchone()
    if not row:
        return None
    try:
        return json.loads(row[0]), row[1]
    except ValueError:
        return None


def _norm(s) -> str:
    return "".join(str(s or "").lower().split())


def _resolve_course_id(courses: list[dict], query: str):
    qn = _norm(query)
    for c in courses:
        if qn in (_norm(c["id"]), _norm(c["kod"]), _norm(c["ad"])):
            return c["id"]
    for c in courses:
        if qn in _norm(c["kod"]) or qn in _norm(c["ad"]):
            return c["id"]
    return None


def _live_with_cache(key: str, fetch) -> dict:
    """Canlı çekim → cache'e yaz; hata olursa temiz mesaj + varsa son bilinen veri."""
    out: dict = {"kaynak": "odtuclass"}
    try:
        data = fetch(_get_odtu_client())
        with closing(db()) as conn:
            with conn:
                cache_write(conn, key, data)
        out["veriler"] = data
        return out
    except Exception as e:
        out["hata"] = str(e) if isinstance(e, odtuclass.ODTUClassError) \
            else f"Beklenmedik hata ({type(e).__name__})."
        with closing(db()) as conn:
            cached = cache_read(conn, key)
        if cached:
            out["veriler"], out["son_guncelleme"] = cached
            out["not"] = "Canlı çekim başarısız; son bilinen veriler gösteriliyor."
        return out


def _mail_with_cache(key: str, fetch) -> dict:
    """IMAP çekimi → cache'e yaz; hata olursa Türkçe mesaj + varsa son bilinen mailler."""
    out: dict = {"kaynak": "webmail"}
    try:
        data = fetch()
        with closing(db()) as conn:
            with conn:
                cache_write(conn, key, data)
        out["veriler"] = data
        return out
    except webmail.WebmailError as e:
        out["hata"] = str(e)
        with closing(db()) as conn:
            cached = cache_read(conn, key)
        if cached:
            out["veriler"], out["son_guncelleme"] = cached
            out["not"] = "Canlı çekim başarısız; son bilinen mailler gösteriliyor."
        return out


def _llm_headers() -> dict:
    h = {"Authorization": f"Bearer {API_KEY}"}
    if "openrouter" in BASE_URL:
        # OpenRouter önerir; yoksa da zararı yok
        h["HTTP-Referer"] = os.environ.get("OPENROUTER_REFERER", "https://github.com/atesahmet0/devrimo")
        h["X-Title"] = os.environ.get("OPENROUTER_TITLE", "Devrimo")
    return h


async def llm_chat(messages: list[dict], tools: list | None = TOOLS) -> dict:
    payload: dict = {"model": MODEL, "messages": messages}
    if tools:
        payload["tools"] = tools
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{BASE_URL}/chat/completions",
            headers=_llm_headers(),
            json=payload,
        )
    if resp.status_code != 200:
        # Key'i asla loglama; host'u göster ki OpenRouter vs OpenAI karışmasın
        host = BASE_URL
        raise HTTPException(502, f"LLM hatası {resp.status_code} @ {host}: {resp.text[:300]}")
    return resp.json()


def _stub_filter(items: list[dict], course) -> list[dict]:
    if course:
        qn = _norm(course)
        items = [a for a in items if qn in _norm(a.get("course") or a.get("kod", ""))]
    return items


def tool_get_courses(args: dict) -> dict:
    if _get_odtu_client() is None:
        return {"kaynak": "demo-stub", "veriler": STUB_COURSES}
    return _live_with_cache("odtuclass:courses", lambda cli: cli.get_courses())


def _scoped_tool(cache_kind: str, method: str):
    def impl(args: dict) -> dict:
        course = (args or {}).get("course")
        if _get_odtu_client() is None:
            stubs = {"announcements": ANNOUNCEMENTS, "assignments": STUB_ASSIGNMENTS,
                     "grades": [{"course": c["kod"], "kalem": "Quiz 1", "not": "-"} for c in STUB_COURSES]}
            return {"kaynak": "demo-stub", "veriler": _stub_filter(stubs[cache_kind], course)}

        def fetch(cli):
            cid = None
            if course:
                cid = _resolve_course_id(cli.get_courses(), course)
                if cid is None:
                    raise odtuclass.ODTUDataError(
                        f"'{course}' adında bir ders bulamadım; get_courses ile ders listesine bak.")
            return getattr(cli, method)(cid)

        return _live_with_cache(f"odtuclass:{cache_kind}:{_norm(course) or 'all'}", fetch)
    return impl


tool_get_announcements = _scoped_tool("announcements", "get_announcements")
tool_get_assignments = _scoped_tool("assignments", "get_assignments")
tool_get_grades = _scoped_tool("grades", "get_grades")


def tool_get_today_schedule(args: dict) -> dict:
    uyari = None
    cli = _get_odtu_client()
    if cli is not None:
        try:
            sched = cli.get_today_schedule()
            if sched:
                return {"kaynak": "odtuclass-takvim", "veriler": sched}
        except odtuclass.ODTUClassError as e:
            uyari = str(e)
    today = DAY_NAMES[time.localtime().tm_wday]
    slots = WEEKLY_SCHEDULE.get(today, [])
    out = {"kaynak": "demo-stub", "veriler": {"gun": today, "dersler": [
        {"saat": f"{s}–{e}", "ders": c, "yer": p} for s, e, c, p in slots
    ]}}
    if uyari:
        out["uyari"] = uyari
    elif cli is not None:
        out["not"] = "ODTÜClass takviminde bugün kayıt yok; haftalık programdan türetildi."
    return out


def tool_check_updates(args: dict) -> dict:
    limit = max(1, min(50, int((args or {}).get("limit") or 10)))
    with closing(db()) as conn:
        rows = conn.execute(
            "SELECT c.url, COALESCE(w.etiket, ''), c.eski_hash, c.yeni_hash, "
            "c.ozet, c.created_at FROM page_changes c "
            "LEFT JOIN watched_pages w ON w.url = c.url ORDER BY c.id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        watches = page_watcher.list_watches(conn)
    return {
        "kaynak": "izleyici",
        "izlenen_sayfa": len(watches),
        "veriler": [
            {"url": u, "etiket": e, "ozet": o, "tarih": t}
            for u, e, _oh, _nh, o, t in rows
        ],
    }


def tool_get_deadlines(args: dict) -> dict:
    days = max(1, min(60, int((args or {}).get("days") or 7)))
    src = tool_get_assignments({})
    items = src.get("veriler") or []
    out: dict = {"kaynak": src.get("kaynak"), "pencere_gun": days,
                 "veriler": deadlines.filter_upcoming(items, days=days)}
    if src.get("hata"):
        out["uyari"] = f"Ödev verisi alınamadı ({src['hata']})."
    return out


def tool_get_notifications(_args: dict) -> dict:
    with closing(db()) as conn:
        rows = conn.execute(
            "SELECT id, tur, baslik, detay, url, created_at FROM notifications "
            "WHERE okundu = 0 ORDER BY id DESC LIMIT 20"
        ).fetchall()
        if rows:
            ids = [r[0] for r in rows]
            with conn:
                conn.execute(
                    f"UPDATE notifications SET okundu = 1 WHERE id IN "
                    f"({', '.join('?' * len(ids))})",
                    ids,
                )
        kalan = watcher.unread_count(conn)
    return {
        "kaynak": "bildirim",
        "veriler": [
            {"tur": t, "baslik": b, "detay": d, "url": u, "tarih": c}
            for _i, t, b, d, u, c in rows
        ],
        "kalan_okunmamis": kalan,
    }


def tool_get_unread_mails(args: dict) -> dict:
    limit = max(1, min(50, int((args or {}).get("limit") or 20)))
    if not webmail.is_configured():
        return {"kaynak": "demo-stub", "veriler": webmail.list_unread(limit=limit)}
    return _mail_with_cache("webmail:unread", lambda: webmail.list_unread(limit=limit))


def tool_search_emails(args: dict) -> dict:
    query = str((args or {}).get("query") or "").strip()
    limit = max(1, min(50, int((args or {}).get("limit") or 10)))
    if not query:
        return {"hata": "Arama için bir anahtar kelime gerekli."}
    if not webmail.is_configured():
        return {"kaynak": "demo-stub", "veriler": webmail.search_mail(query, limit=limit)}
    return _mail_with_cache(f"webmail:search:{_norm(query)}",
                            lambda: webmail.search_mail(query, limit=limit))


def _weekly_schedule_slots() -> list[dict]:
    """WEEKLY_SCHEDULE'ı detect_conflicts'un beklediği dict biçimine çevirir."""
    return [
        {"gun": gun, "baslangic": s, "bitis": e, "ders": ders, "yer": yer}
        for gun, rows in WEEKLY_SCHEDULE.items()
        for s, e, ders, yer in rows
    ]


def tool_check_schedule_conflicts(_args: dict) -> dict:
    bulgular = conflicts.detect_conflicts(_weekly_schedule_slots())
    out: dict = {
        "kaynak": "haftalik-program",
        "veriler": bulgular,
        "ozet": (f"{len(bulgular)} çakışma bulundu." if bulgular
                 else "Programda saat çakışması yok."),
    }
    if _get_odtu_client() is not None:
        out["not"] = ("ODTÜClass'ta haftalık çizelge API'si olmadığı için "
                      "kayıtlı haftalık program esas alındı.")
    return out


def _digest_section(lines: list[str], baslik: str, src: dict, render) -> None:
    veriler = src.get("veriler") or []
    lines.append(f"== {baslik} (kaynak: {src.get('kaynak', '?' )}, {len(veriler)} kayıt) ==")
    if not veriler:
        lines.append("(kayıt yok)")
        return
    if src.get("hata"):
        lines.append(f"(veri alınamadı: {src['hata']})")
        return
    lines.extend(render(v) for v in veriler)





def tool_get_daily_digest(args: dict) -> dict:
    limit = max(1, min(20, int((args or {}).get("limit") or 5)))
    ann = tool_get_announcements({})
    upd = tool_check_updates({"limit": limit})
    mail = tool_get_unread_mails({"limit": limit})

    def ann_line(a):
        title = a.get("baslik") or a.get("title") or ""
        course = a.get("course")
        tarih = a.get("tarih") or a.get("date") or a.get("due")
        ozet = a.get("ozet") or ""
        parts = [f"[{course}] {title}".strip()] if course else [title]
        if tarih:
            parts.append(f"({tarih})")
        if ozet:
            parts.append(f"— {str(ozet)[:120]}")
        return "- " + " ".join(parts)

    def upd_line(u):
        label = u.get("etiket") or u.get("url") or ""
        bits = [f"[{label}]"] if label else ["[sayfa]"]
        if u.get("ozet"):
            bits.append(str(u["ozet"])[:160])
        if u.get("tarih"):
            bits.append(f"({u['tarih']})")
        return "- " + " ".join(bits)

    def mail_line(m):
        konu = m.get("konu") or ""
        bits = [f"[Mail] {m.get('kimden', '')} — {konu}".strip()]
        if m.get("tarih"):
            bits.append(f"({m['tarih']})")
        if m.get("ozet"):
            bits.append(f"— {str(m['ozet'])[:120]}")
        return "- " + " ".join(bits)

    lines = [f"GÜNLÜK BİRLEŞİK AKIŞ — {date.today().isoformat()}"]
    _digest_section(lines, "DUYURULAR", ann, ann_line)
    _digest_section(lines, "İZLENEN SAYFA DEĞİŞİKLİKLERİ", upd, upd_line)
    _digest_section(lines, "OKUNMAMIŞ MAILLER", mail, mail_line)

    return {
        "kaynak": "birlesik-akis",
        "kaynaklar": [ann.get("kaynak"), upd.get("kaynak"), mail.get("kaynak")],
        "adet": {"duyuru": len(ann.get("veriler") or []),
                 "sayfa_degisikligi": len(upd.get("veriler") or []),
                 "okunmamis_mail": len(mail.get("veriler") or [])},
        "metin": "\n".join(lines),
    }


def tool_get_sais_info(_args: dict | None = None) -> dict:
    if not sais.is_configured():
        return {"kaynak": "sais-stub", "veriler": sais.SAIS_STUB_INFO}
    try:
        cli = sais.from_env()
        info = cli.get_student_info() if cli else sais.SAIS_STUB_INFO
        return {"kaynak": "sais", "veriler": info}
    except sais.SAISError as e:
        return {"kaynak": "sais", "hata": str(e), "veriler": sais.SAIS_STUB_INFO}


def tool_get_sais_schedule(_args: dict | None = None) -> dict:
    if not sais.is_configured():
        return {"kaynak": "sais-stub", "veriler": sais.SAIS_STUB_SCHEDULE}
    try:
        cli = sais.from_env()
        sched = cli.get_schedule() if cli else sais.SAIS_STUB_SCHEDULE
        return {"kaynak": "sais", "veriler": sched}
    except sais.SAISError as e:
        return {"kaynak": "sais", "hata": str(e), "veriler": sais.SAIS_STUB_SCHEDULE}


def tool_get_sais_transcript(_args: dict | None = None) -> dict:
    if not sais.is_configured():
        return {"kaynak": "sais-stub", "veriler": sais.SAIS_STUB_TRANSCRIPT}
    try:
        cli = sais.from_env()
        tr = cli.get_transcript() if cli else sais.SAIS_STUB_TRANSCRIPT
        return {"kaynak": "sais", "veriler": tr}
    except sais.SAISError as e:
        return {"kaynak": "sais", "hata": str(e), "veriler": sais.SAIS_STUB_TRANSCRIPT}


TOOL_IMPLS = {
    "get_courses": tool_get_courses,
    "get_announcements": tool_get_announcements,
    "get_assignments": tool_get_assignments,
    "get_grades": tool_get_grades,
    "get_today_schedule": tool_get_today_schedule,
    "check_updates": tool_check_updates,
    "get_deadlines": tool_get_deadlines,
    "get_notifications": tool_get_notifications,
    "get_unread_mails": tool_get_unread_mails,
    "search_emails": tool_search_emails,
    "get_daily_digest": tool_get_daily_digest,
    "check_schedule_conflicts": tool_check_schedule_conflicts,
    "get_sais_info": tool_get_sais_info,
    "get_sais_schedule": tool_get_sais_schedule,
    "get_sais_transcript": tool_get_sais_transcript,
}


async def run_tool(name: str, raw_args) -> dict:
    fn = TOOL_IMPLS.get(name)
    if fn is None:
        return {"hata": f"Bilinmeyen araç: {name}"}
    if isinstance(raw_args, str):
        try:
            raw_args = json.loads(raw_args)
        except ValueError:
            raw_args = {}
    return await asyncio.to_thread(fn, raw_args or {})


async def chat_roundtrip(user_message: str) -> str:
    if not API_KEY:
        raise HTTPException(500, "OPENAI_API_KEY ayarlanmamış.")
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    with closing(db()) as conn:
        messages += load_history(conn)
        messages.append({"role": "user", "content": user_message})

        for _ in range(MAX_TOOL_ROUNDS):
            data = await llm_chat(messages)
            choice = data["choices"][0]
            message = choice["message"]

            if choice.get("finish_reason") != "tool_calls":
                with conn:
                    save_message(conn, "user", user_message)
                    save_message(conn, "assistant", message.get("content") or "")
                return message.get("content") or ""

            messages.append(message)
            for call in message["tool_calls"]:
                result = await run_tool(call["function"]["name"],
                                        call["function"].get("arguments"))
                messages.append({
                    "role": "tool",
                    "tool_call_id": call["id"],
                    "content": json.dumps(result, ensure_ascii=False),
                })

        raise HTTPException(502, "Tool döngüsü sınırı aşıldı.")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    watcher.start(
        db_factory=db,
        assignments_provider=lambda: tool_get_assignments({}).get("veriler") or [],
    )
    yield
    watcher.stop()


app = FastAPI(title="devrimo-agent", lifespan=lifespan)


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str


@app.get("/healthz")
def healthz():
    return {
        "status": "ok",
        "odtuclass": odtuclass.is_configured(),
        "webmail": webmail.is_configured(),
        "sais": sais.is_configured(),
        "watcher": watcher.status(),
    }


@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    reply = await chat_roundtrip(req.message)
    return ChatResponse(reply=reply)


@app.get("/api/updates")
def api_updates(limit: int = 15):
    return tool_check_updates({"limit": limit})


@app.get("/api/connections")
def api_connections():
    def masked_user(service: str, env_key: str, cred_key: str) -> str:
        u = _eff(env_key, cred_key)
        return _masked(u) if u else ""

    odtu_u = _eff("ODTU_USERNAME", "odtu_username")
    sais_u = _eff("SAIS_USERNAME", "sais_username")
    mail_u = _eff("MAIL_USERNAME", "mail_username")
    return {
        "email": {
            "configured": bool(mail_u and _eff("MAIL_PASSWORD", "mail_password")),
            "host": _eff("IMAP_HOST", "mail_host") or "mail.metu.edu.tr",
            "port": int(_eff("IMAP_PORT", "mail_port") or 993),
            "username_masked": _masked(mail_u),
            "source": "db" if cred_get("mail_username") else ("env" if mail_u else "none"),
        },
        "odtuclass": {
            "configured": bool(odtu_u and _eff("ODTU_PASSWORD", "odtu_password") and _eff("ODTUCLASS_URL", "odtu_url")),
            "url": _eff("ODTUCLASS_URL", "odtu_url") or "",
            "username_masked": _masked(odtu_u),
            "source": "db" if cred_get("odtu_username") else ("env" if odtu_u else "none"),
        },
        "sais": {
            "configured": bool(sais_u and _eff("SAIS_PASSWORD", "sais_password")),
            "username_masked": _masked(sais_u),
            "source": "db" if cred_get("sais_username") else ("env" if sais_u else "none"),
        },
    }


class ConnTestRequest(BaseModel):
    service: str
    host: str | None = None
    port: int | None = None
    username: str | None = None
    password: str | None = None
    url: str | None = None


class ConnSaveRequest(BaseModel):
    service: str
    host: str | None = None
    port: int | None = None
    username: str | None = None
    password: str | None = None
    url: str | None = None


def _test_service(service: str, host=None, port=None, username=None, password=None, url=None) -> tuple[bool, str]:
    try:
        if service == "email":
            h = host or "mail.metu.edu.tr"
            p = int(port or 993)
            u = username or ""
            pw = password or ""
            if not (u and pw):
                return False, "Kullanıcı adı ve şifre gerekli."
            cli = webmail.WebmailClient(h, p, u, pw, timeout=10)
            cli.list_unread(limit=1)
            return True, "Bağlantı başarılı."
        elif service == "odtuclass":
            u = url or "https://odtuclass.metu.edu.tr"
            un = username or ""
            pw = password or ""
            if not (un and pw):
                return False, "Kullanıcı adı ve şifre gerekli."
            cli = odtuclass.ODTUClassClient(u, un, pw, timeout=10)
            try:
                cli.ensure_login()
                cli.get_courses()
                return True, "Bağlantı başarılı."
            finally:
                try:
                    cli.close()
                except Exception:
                    pass
        elif service == "sais":
            un = username or ""
            pw = password or ""
            if not (un and pw):
                return False, "Kullanıcı adı ve şifre gerekli."
            cli = sais.SAISClient(un, pw, timeout=10)
            try:
                cli.ensure_login()
                return True, "Bağlantı başarılı."
            finally:
                try:
                    cli._client.close()
                except Exception:
                    pass
        else:
            return False, f"Bilinmeyen servis: {service}"
    except (odtuclass.ODTUClassError, webmail.WebmailError, sais.SAISError) as e:
        return False, str(e)
    except Exception as e:
        return False, f"Bağlantı hatası: {type(e).__name__}: {str(e)[:120]}"


@app.post("/api/connections/test")
def api_connections_test(req: ConnTestRequest):
    ok, msg = _test_service(req.service, req.host, req.port, req.username, req.password, req.url)
    return {"ok": ok, "message": msg}


@app.post("/api/connections")
def api_connections_save(req: ConnSaveRequest):
    svc = req.service.strip().lower()
    if svc not in ("email", "odtuclass", "sais"):
        raise HTTPException(400, f"Bilinmeyen servis: {svc}")
    # persist
    if svc == "email":
        if req.host is not None:
            cred_set("mail_host", req.host)
        if req.port is not None:
            cred_set("mail_port", str(req.port))
        if req.username is not None:
            cred_set("mail_username", req.username)
        if req.password is not None:
            cred_set("mail_password", req.password)
    elif svc == "odtuclass":
        if req.url is not None:
            cred_set("odtu_url", req.url)
        if req.username is not None:
            cred_set("odtu_username", req.username)
        if req.password is not None:
            cred_set("odtu_password", req.password)
    elif svc == "sais":
        if req.username is not None:
            cred_set("sais_username", req.username)
        if req.password is not None:
            cred_set("sais_password", req.password)
    ok, msg = _test_service(svc, req.host, req.port, req.username, req.password, req.url)
    return {"ok": ok, "message": msg, "service": svc}


@app.delete("/api/connections/{service}")
def api_connections_delete(service: str):
    svc = service.strip().lower()
    if svc not in ("email", "odtuclass", "sais"):
        raise HTTPException(400, f"Bilinmeyen servis: {svc}")
    cred_delete(svc)
    # also delete prefixed keys for email/odtuclass
    mapping = {"email": ["mail_host", "mail_port", "mail_username", "mail_password"], "odtuclass": ["odtu_url", "odtu_username", "odtu_password"], "sais": ["sais_username", "sais_password"]}
    with closing(db()) as conn:
        with conn:
            for k in mapping[svc]:
                conn.execute("DELETE FROM credentials WHERE key=?", (k,))
    return {"ok": True, "message": f"{svc} bağlantısı silindi."}


@app.get("/api/deadlines")
def api_deadlines(days: int = 7):
    return tool_get_deadlines({"days": days})


@app.get("/api/notifications")
def api_notifications():
    return tool_get_notifications({})


@app.get("/api/mails")
def api_mails(limit: int = 20):
    return tool_get_unread_mails({"limit": limit})


DIGEST_PROMPT = (
    "Aşağıda bir ODTÜ öğrencisinin duyuruları, izlenen sayfa değişiklikleri ve "
    "okunmamış maillerinin birleşik ham akışı var. Bugün kaçırabilecekleri açısından "
    "en önemliden başlayarak kısa Türkçe madde listesi üret. En fazla 6 madde; her "
    "maddenin sonunda kaynağı köşeli parantezle belirt ([CENG 242], [OIDB], [Mail] gibi). "
    "Akış boşsa tek cümleyle 'Bugün için öne çıkan bir şey yok' de.\n\n"
)


@app.get("/api/digest")
async def api_digest():
    if not API_KEY:
        raise HTTPException(503, "OPENAI_API_KEY ayarlanmamış; günlük özet üretilemez.")
    raw = tool_get_daily_digest({})
    metin = (raw.get("metin") or "").strip()
    if not metin:
        return {"ozet": "Bugün için öne çıkan bir duyuru, değişiklik veya okunmamış mail yok.",
                "kaynaklar": [], "tarih": date.today().isoformat()}
    data = await llm_chat(
        [{"role": "system", "content": DIGEST_PROMPT}, {"role": "user", "content": metin}],
        tools=None,
    )
    ozet = ((data.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
    return {"ozet": ozet.strip(), "kaynaklar": raw.get("kaynaklar"),
            "adet": raw.get("adet"), "tarih": date.today().isoformat()}


@app.get("/api/conflicts")
def api_conflicts():
    return tool_check_schedule_conflicts({})
