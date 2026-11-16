"""
parsing.py — Buyruq argumentlari va savol-javob javoblarini tahlil qilish.
"""

import re
from dataclasses import dataclass
from datetime import date
from typing import Optional

from birthday_bot.dates import validate_date
from birthday_bot.models import MAX_NAME_LENGTH

# "Ism Familiya 15.03", "Ism 15.03.1998" yoki faqat "15.03" (ism reply qilingan
# xabar egasidan yoki /edit da eski yozuvdan olinadi)
BIRTHDAY_PATTERN = re.compile(
    r"^(?:(?P<name>.+?)\s+)?(?P<day>\d{1,2})\.(?P<month>\d{1,2})(?:\.(?P<year>\d{4}))?$"
)
EDIT_PATTERN = re.compile(r"^(?P<id>\d+)\s+(?P<rest>.+)$")
# /start payloadi: "g_<guruh ID>" (guruhdagi "➕ Qo'shish" tugmasidan)
GROUP_PAYLOAD_PATTERN = re.compile(r"^g_(?P<id>-?\d+)$")


class ParseError(ValueError):
    pass


@dataclass(frozen=True)
class ParsedBirthday:
    name: Optional[str]
    day: int
    month: int
    year: Optional[int] = None


def parse_name(text: str) -> str:
    """Ismdagi ortiqcha bo'shliqlarni olib tashlaydi va uzunligini tekshiradi."""
    name = " ".join(text.split())
    if not name:
        raise ParseError("Ism bo'sh bo'lmasligi kerak.")
    if len(name) > MAX_NAME_LENGTH:
        raise ParseError(f"Ism {MAX_NAME_LENGTH} belgidan oshmasligi kerak.")
    return name


def parse_birthday(text: str, today: date) -> ParsedBirthday:
    match = BIRTHDAY_PATTERN.match(text.strip())
    if not match:
        raise ParseError("Format noto'g'ri.")

    name = parse_name(match["name"]) if match["name"] else None
    day, month = int(match["day"]), int(match["month"])
    year = int(match["year"]) if match["year"] else None

    error = validate_date(day, month, year, today)
    if error:
        raise ParseError(error)
    return ParsedBirthday(name=name, day=day, month=month, year=year)


def parse_date(text: str, today: date) -> ParsedBirthday:
    """Faqat sana: '15.03' yoki '15.03.1998' (ism bo'lmasligi kerak)."""
    parsed = parse_birthday(text, today)
    if parsed.name:
        raise ParseError("Format noto'g'ri.")
    return parsed


def parse_edit(text: str, today: date) -> tuple[int, ParsedBirthday]:
    match = EDIT_PATTERN.match(text.strip())
    if not match:
        raise ParseError("Format noto'g'ri.")
    return int(match["id"]), parse_birthday(match["rest"], today)


def parse_group_payload(payload: str) -> Optional[int]:
    """/start dagi 'g_<guruh ID>' dan guruh ID'si, noto'g'ri bo'lsa None."""
    match = GROUP_PAYLOAD_PATTERN.match(payload.strip())
    return int(match["id"]) if match else None
