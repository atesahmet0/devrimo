"""Deadline filtresi — assignment verisinden yaklaşan teslimleri süzer.

Girdi: ODTÜClass connector'ünün (veya stub'ın) assignment dict'leri;
``teslim`` alanı ``YYYY-MM-DD`` / ``YYYY-MM-DD HH:MM`` / ISO biçimli olur.
Ayrıştırılamayan, geçmiş veya pencere dışındaki kayıt elenir; kalanlar
teslim tarihine göre sıralanıp ``kalan_gun`` eklenerek döner.
"""

from __future__ import annotations

from datetime import datetime, timedelta


def parse_teslim(value) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).strip())
    except ValueError:
        return None
    return dt.replace(tzinfo=None) if dt.tzinfo else dt


def filter_upcoming(assignments: list[dict], days: int = 7,
                    now: datetime | None = None) -> list[dict]:
    now = now or datetime.now()
    horizon = now + timedelta(days=days)
    out: list[tuple[datetime, dict]] = []
    for a in assignments or []:
        due = parse_teslim(a.get("teslim"))
        if due is None or due < now or due > horizon:
            continue
        item = {**a, "kalan_gun": round((due - now).total_seconds() / 86400, 1)}
        out.append((due, item))
    out.sort(key=lambda t: t[0])
    return [item for _, item in out]
