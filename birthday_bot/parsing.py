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
# Oy nomi bilan: "Ism 27 may 2021", "29-noyabr 2022-yil", "1 февраль"
NAMED_MONTH_PATTERN = re.compile(
    r"^(?:(?P<name>.+?)\s+)?(?P<day>\d{1,2})(?:\s+|\s*-\s*)(?P<month>[^\W\d_]+)"
    r"(?:(?:\s+|\s*,\s*)(?P<year>\d{4})(?:\s*-?\s*yil)?)?$",
    re.IGNORECASE,
)
# Ro'yxat qatori boshidagi belgilar: "-", "•", "1.", "2)"
LIST_MARKER = re.compile(r"^(?:[-•*·]|\d{1,3}[.)])\s+")
MAX_BULK_ENTRIES = 50


def _month_names() -> dict[str, int]:
    latin = [
        "yanvar", "fevral", "mart", "aprel", "may", "iyun",
        "iyul", "avgust", "sentabr", "oktabr", "noyabr", "dekabr",
    ]
    names = {name: number for number, name in enumerate(latin, start=1)}
    names.update({"sentyabr": 9, "oktyabr": 10})
    # Kirill (o'zbek va rus): "феврал", "февраль", "февраля"
    cyrillic = [
        "январ", "феврал", "март", "апрел", "май", "июн",
        "июл", "август", "сентябр", "октябр", "ноябр", "декабр",
    ]
    for number, stem in enumerate(cyrillic, start=1):
        names.update({stem: number, stem + "ь": number, stem + "я": number})
    names.update({"марта": 3, "мая": 5, "августа": 8})
    return names


MONTH_NAMES = _month_names()

EDIT_PATTERN = re.compile(r"^(?P<id>\d+)\s+(?P<rest>.+)$")
# /start payloadi: "g_<guruh ID>" (guruhdagi "➕ Qo'shish" tugmasidan)
GROUP_PAYLOAD_PATTERN = re.compile(r"^g_(?P<id>-?\d+)$")
# Boshqaruvchi taklifi: "m_<token>" (Database.create_invite)
INVITE_PAYLOAD_PATTERN = re.compile(r"^m_(?P<token>[A-Za-z0-9_-]{8,40})$")


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


@dataclass(frozen=True)
class BulkResult:
    entries: list[ParsedBirthday]
    errors: list[tuple[str, str]]  # (qator, sabab)


def parse_birthday(text: str, today: date) -> ParsedBirthday:
    text = text.strip()
    match = BIRTHDAY_PATTERN.match(text)
    if match:
        month = int(match["month"])
    else:
        match = NAMED_MONTH_PATTERN.match(text)
        if not match:
            raise ParseError("Format noto'g'ri.")
        month = MONTH_NAMES.get(match["month"].lower())
        if month is None:
            raise ParseError(f"Oy nomi tushunilmadi: «{match['month']}».")

    name = parse_name(match["name"]) if match["name"] else None
    day = int(match["day"])
    year = int(match["year"]) if match["year"] else None

    error = validate_date(day, month, year, today)
    if error:
        raise ParseError(error)
    return ParsedBirthday(name=name, day=day, month=month, year=year)


def parse_bulk(text: str, today: date) -> BulkResult:
    """
    Har qatorda bitta odam: "Ism 27 may 2021" yoki "Ism 27.05.2021". Bo'sh qatorlar
    o'tkazib yuboriladi, tushunilmagan qatorlar sababi bilan qaytariladi.
    """
    entries: list[ParsedBirthday] = []
    errors: list[tuple[str, str]] = []
    for raw in text.splitlines():
        line = " ".join(raw.split())
        if not line:
            continue
        try:
            parsed = parse_birthday(LIST_MARKER.sub("", line), today)
        except ParseError as exc:
            errors.append((line, str(exc)))
            continue
        if not parsed.name:
            errors.append((line, "Ism ko'rsatilmagan."))
        elif len(entries) >= MAX_BULK_ENTRIES:
            errors.append((line, f"Bir martada {MAX_BULK_ENTRIES} tadan ko'p qo'shib bo'lmaydi."))
        else:
            entries.append(parsed)
    return BulkResult(entries=entries, errors=errors)


def parse_date(text: str, today: date) -> ParsedBirthday:
    """Faqat sana: '15.03', '15.03.1998' yoki '15 mart 1998' (ism bo'lmasligi kerak)."""
    parsed = parse_birthday(text, today)
    if parsed.name:
        raise ParseError("Format noto'g'ri.")
    return parsed


def parse_edit(text: str, today: date) -> tuple[int, ParsedBirthday]:
    match = EDIT_PATTERN.match(text.strip())
    if not match:
        raise ParseError("Format noto'g'ri.")
    return int(match["id"]), parse_birthday(match["rest"], today)


MAX_TEMPLATE_LENGTH = 500
NAME_PLACEHOLDER = "{ism}"


def parse_greeting_template(text: str) -> str:
    """Guruhning o'z tabrik matni: {ism} — odamning ismi qo'yiladigan joy."""
    template = text.strip()
    if NAME_PLACEHOLDER not in template:
        raise ParseError(f"Matnda {NAME_PLACEHOLDER} bo'lishi kerak — u yerga odamning ismi qo'yiladi.")
    if len(template) > MAX_TEMPLATE_LENGTH:
        raise ParseError(f"Matn {MAX_TEMPLATE_LENGTH} belgidan oshmasligi kerak.")
    return template


def parse_invite_payload(payload: str) -> Optional[str]:
    """/start dagi 'm_<token>' dan taklif tokeni, noto'g'ri bo'lsa None."""
    match = INVITE_PAYLOAD_PATTERN.match(payload.strip())
    return match["token"] if match else None


def parse_group_payload(payload: str) -> Optional[int]:
    """/start dagi 'g_<guruh ID>' dan guruh ID'si, noto'g'ri bo'lsa None."""
    match = GROUP_PAYLOAD_PATTERN.match(payload.strip())
    return int(match["id"]) if match else None
