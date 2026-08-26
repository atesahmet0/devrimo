"""Devrimo agent core.

FastAPI servisi: OpenAI-uyumlu LLM'e bağlanır, elle yazılmış tool-calling
loop'u çalıştırır, sohbet geçmişini SQLite'ta tutar. Tek demo kullanıcısı,
auth yok.

Araç verisi: ODTUCLASS_URL / ODTU_USERNAME / ODTU_PASSWORD doluysa gerçek
ODTÜClass connector'ü kullanılır; boşsa demo stub'ına düşer.
"""

import asyncio
import json
import os
import sqlite3
import sys
import time
from contextlib import closing
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from packages.connectors import odtuclass  # noqa: E402

BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
API_KEY = os.environ.get("OPENAI_API_KEY", "")
MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

DB_PATH = Path(__file__).parent / "data" / "devrimo.db"
MAX_TOOL_ROUNDS = 5
HISTORY_LIMIT = 20

SYSTEM_PROMPT = (
    "Sen Devrimo'sun: ODTÜ öğrencileri için bir asistan. Kısa ve net Türkçe cevap ver. "
    "Dersler, duyurular, ödevler, notlar veya ders programıyla ilgili sorularda elindeki "
    "araçları kullan; bilmediğini uydurma. Araç cevaplarında 'kaynak' alanı verinin "
    "gerçek ODTÜClass'tan mı yoksa demo stub'dan mı geldiğini belirtir; kaynağa göre konuş."
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

STUB_ASSIGNMENTS = [
    {"course": "CENG 242", "ad": "Ödev 3", "teslim": "2026-09-04", "aciklama": "Late policy: her gün %10."},
    {"course": "MATH 260", "ad": "Problem seti 5", "teslim": "2026-09-08", "aciklama": ""},
    {"course": "PHYS 106", "ad": "Lab raporu 1", "teslim": "2026-09-11", "aciklama": ""},
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
    return conn


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


async def llm_chat(messages: list[dict]) -> dict:
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {API_KEY}"},
            json={"model": MODEL, "messages": messages, "tools": TOOLS},
        )
    if resp.status_code != 200:
        raise HTTPException(502, f"LLM hatası {resp.status_code}: {resp.text[:300]}")
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


TOOL_IMPLS = {
    "get_courses": tool_get_courses,
    "get_announcements": tool_get_announcements,
    "get_assignments": tool_get_assignments,
    "get_grades": tool_get_grades,
    "get_today_schedule": tool_get_today_schedule,
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


app = FastAPI(title="devrimo-agent")


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str


@app.get("/healthz")
def healthz():
    return {"status": "ok", "odtuclass": odtuclass.is_configured()}


@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    reply = await chat_roundtrip(req.message)
    return ChatResponse(reply=reply)
