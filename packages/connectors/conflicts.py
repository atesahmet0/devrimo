"""Ders programı çakışma tespiti — saf Python, agent'ten bağımsız.

``detect_conflicts(schedule)`` aynı gün içinde zaman aralıkları kesişen
ders çiftlerini bulur. Bir dersle aynı kodun lab'ı (adında lab/laboratuvar
geçen kayıt) kesişiyorsa bu uyarı değil bilgi kabul edilir: ``lab_bilgi``.
Farklı kodlar kesişiyorsa ``cakisma`` olur.

Girdi satırları esnek dict'lerdir; tanınan anahtarlar:
``gun``/``day``, ``baslangic``/``start``, ``bitis``/``end``,
``ders``/``course``/``ad``. İsteğe bağlı ``tur`` alanı ("lab"/"ders")
varsa ad taramasına üstünlük verir.

Çıktı: ``{ders1, ders2, gun, aralik, tip}`` kayıtları; güne ve başlangıç
saatine göre sıralı.
"""

from __future__ import annotations

import re

_CODE_RE = re.compile(r"[A-ZÇĞİÖŞÜ]{2,4}\s?\d{3}")
_LAB_RE = re.compile(r"\blab\b|laboratuvar", re.IGNORECASE)

_TR_FOLD = str.maketrans({
    "ç": "c", "Ç": "c", "ğ": "g", "Ğ": "g", "ı": "i", "I": "i",
    "İ": "i", "ö": "o", "Ö": "o", "ş": "s", "Ş": "s", "ü": "u", "Ü": "u",
})

_DAY_ORDER = {
    "pazartesi": 0, "sali": 1, "carsamba": 2, "persembe": 3,
    "cuma": 4, "cumartesi": 5, "pazar": 6,
}


def _pick(slot: dict, *keys):
    for k in keys:
        v = slot.get(k)
        if v:
            return v
    return None


def _minutes(value) -> int | None:
    m = re.match(r"^(\d{1,2}):(\d{2})", str(value or "").strip())
    if not m:
        return None
    hour, minute = int(m.group(1)), int(m.group(2))
    if hour > 23 or minute > 59:
        return None
    return hour * 60 + minute


def _fmt(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _fold(text: str) -> str:
    return (text or "").translate(_TR_FOLD).lower()


def _day_key(gun: str):
    folded = _fold(str(gun).strip())
    return _DAY_ORDER.get(folded, len(_DAY_ORDER)), folded


def _course_code(ders: str) -> str | None:
    m = _CODE_RE.search(str(ders).upper().translate(_TR_FOLD))
    return m.group(0).replace(" ", "") if m else None


def detect_conflicts(schedule: list[dict]) -> list[dict]:
    slots = []
    for raw in schedule or []:
        if not isinstance(raw, dict):
            continue
        gun = _pick(raw, "gun", "day")
        start = _minutes(_pick(raw, "baslangic", "start"))
        end = _minutes(_pick(raw, "bitis", "end"))
        ders = str(_pick(raw, "ders", "course", "ad") or "").strip()
        if not gun or start is None or end is None or end <= start or not ders:
            continue
        tur = _fold(str(raw.get("tur") or ""))
        is_lab = "lab" in tur.split() or tur == "lab" or bool(_LAB_RE.search(ders))
        slots.append({
            "gun": str(gun), "baslangic": start, "bitis": end,
            "ders": ders, "lab": is_lab,
            "kod": _course_code(ders) or _fold(ders),
        })

    slots.sort(key=lambda s: (_day_key(s["gun"]), s["baslangic"]))
    out: list[dict] = []
    for i, a in enumerate(slots):
        for b in slots[i + 1:]:
            if a["gun"] != b["gun"]:
                continue
            if a["baslangic"] >= b["bitis"] or b["baslangic"] >= a["bitis"]:
                continue
            same_code = a["kod"] == b["kod"]
            tip = "lab_bilgi" if same_code and (a["lab"] or b["lab"]) else "cakisma"
            out.append({
                "ders1": a["ders"],
                "ders2": b["ders"],
                "gun": a["gun"],
                "aralik": f"{_fmt(max(a['baslangic'], b['baslangic']))}–"
                          f"{_fmt(min(a['bitis'], b['bitis']))}",
                "tip": tip,
            })
    return out
