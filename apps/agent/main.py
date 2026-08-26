"""Devrimo agent core.

FastAPI servisi: OpenAI-uyumlu LLM'e bağlanır, elle yazılmış tool-calling
loop'u çalıştırır, sohbet geçmişini SQLite'ta tutar. Tek demo kullanıcısı,
auth yok.
"""

import json
import os
import sqlite3
import time
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
API_KEY = os.environ.get("OPENAI_API_KEY", "")
MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

DB_PATH = Path(__file__).parent / "data" / "devrimo.db"
MAX_TOOL_ROUNDS = 5
HISTORY_LIMIT = 20

SYSTEM_PROMPT = (
    "Sen Devrimo'sun: ODTÜ öğrencileri için bir asistan. Kısa ve net cevap ver. "
    "Duyurular veya ders programıyla ilgili sorularda elindeki araçları kullan; "
    "bilmediğini uydurma."
)

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_announcements",
            "description": "Öğrencinin güncel duyurularını döndürür (ODTÜClass, bölüm, OIDB).",
            "parameters": {"type": "object", "properties": {}, "required": []},
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


def get_announcements() -> str:
    return json.dumps(ANNOUNCEMENTS, ensure_ascii=False)


def get_today_schedule() -> str:
    today = DAY_NAMES[time.localtime().tm_wday]
    slots = WEEKLY_SCHEDULE.get(today, [])
    return json.dumps({"gun": today, "dersler": [
        {"saat": f"{s}–{e}", "ders": c, "yer": p} for s, e, c, p in slots
    ]}, ensure_ascii=False)


TOOL_IMPLS = {"get_announcements": get_announcements, "get_today_schedule": get_today_schedule}


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
    return conn


def load_history(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT role, content FROM (SELECT * FROM messages ORDER BY id DESC LIMIT ?) ORDER BY id ASC",
        (HISTORY_LIMIT,),
    ).fetchall()
    return [{"role": r, "content": c} for r, c in rows]


def save_message(conn: sqlite3.Connection, role: str, content: str) -> None:
    conn.execute("INSERT INTO messages (role, content) VALUES (?, ?)", (role, content))


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


async def chat_roundtrip(user_message: str) -> str:
    if not API_KEY:
        raise HTTPException(500, "OPENAI_API_KEY ayarlanmamış.")
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    with db() as conn:
        messages += load_history(conn)
        messages.append({"role": "user", "content": user_message})

        for _ in range(MAX_TOOL_ROUNDS):
            data = await llm_chat(messages)
            choice = data["choices"][0]
            message = choice["message"]

            if choice.get("finish_reason") != "tool_calls":
                save_message(conn, "user", user_message)
                save_message(conn, "assistant", message.get("content") or "")
                return message.get("content") or ""

            messages.append(message)
            for call in message["tool_calls"]:
                result = TOOL_IMPLS[call["function"]["name"]]()
                messages.append({
                    "role": "tool",
                    "tool_call_id": call["id"],
                    "content": result,
                })

        raise HTTPException(502, "Tool döngüsü sınırı aşıldı.")


app = FastAPI(title="devrimo-agent")


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    reply = await chat_roundtrip(req.message)
    return ChatResponse(reply=reply)
