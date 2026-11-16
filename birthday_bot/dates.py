"""
dates.py — Sana va vaqt bilan ishlash: validatsiya, 29-fevral, yosh.

Funksiyalar "bugun"ni parametr sifatida oladi — server vaqtiga bog'liq emas
va testlarda oson tekshiriladi.
"""

import re
from datetime import date, datetime, time
from typing import Optional
from zoneinfo import ZoneInfo

MIN_YEAR = 1900

TIME_PATTERN = re.compile(r"^(?P<hour>\d{1,2}):(?P<minute>\d{2})$")


def now(tz: ZoneInfo) -> datetime:
    return datetime.now(tz)


def is_leap(year: int) -> bool:
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def validate_date(day: int, month: int, year: Optional[int], today: date) -> Optional[str]:
    """
    Sanani tekshiradi. To'g'ri bo'lsa None, aks holda xato matnini qaytaradi.
    Yil ko'rsatilmasa 29-fevral ham qabul qilinadi.
    """
    if year is not None and not (MIN_YEAR <= year <= today.year):
        return f"Yil {MIN_YEAR} va {today.year} oralig'ida bo'lishi kerak."
    try:
        # 2000-yil kabisa — yilsiz 29.02 ham o'tadi
        birth = date(year or 2000, month, day)
    except ValueError:
        return "Bunday sana mavjud emas."
    if year is not None and birth > today:
        return "Tug'ilgan sana kelajakda bo'lishi mumkin emas."
    return None


def birthday_in_year(day: int, month: int, year: int) -> date:
    """Berilgan yildagi tug'ilgan kun sanasi. Kabisa bo'lmagan yilda 29.02 → 28.02."""
    if month == 2 and day == 29 and not is_leap(year):
        return date(year, 2, 28)
    return date(year, month, day)


def next_birthday(day: int, month: int, from_date: date) -> date:
    """from_date dan boshlab (shu kun ham kiradi) eng yaqin tug'ilgan kun sanasi."""
    bday = birthday_in_year(day, month, from_date.year)
    if bday < from_date:
        bday = birthday_in_year(day, month, from_date.year + 1)
    return bday


def birthday_keys_for(d: date) -> list[tuple[int, int]]:
    """Shu sanada nishonlanadigan (kun, oy) juftliklari."""
    keys = [(d.day, d.month)]
    if d.month == 2 and d.day == 28 and not is_leap(d.year):
        keys.append((29, 2))
    return keys


def calc_age(birth_year: int, on_date: date) -> int:
    return on_date.year - birth_year


def parse_time(value: str) -> Optional[time]:
    """'HH:MM' ni time ga aylantiradi, noto'g'ri bo'lsa None."""
    match = TIME_PATTERN.match(value.strip())
    if not match:
        return None
    hour, minute = int(match["hour"]), int(match["minute"])
    if hour > 23 or minute > 59:
        return None
    return time(hour, minute)


def format_time(value: time) -> str:
    return value.strftime("%H:%M")
