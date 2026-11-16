"""
utils.py — Umumiy yordamchi funksiyalar: vaqt mintaqasi, sanalarni tekshirish,
yoshni hisoblash.
"""

import os
import re
from datetime import date, datetime
from typing import Optional
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()

TZ = ZoneInfo(os.getenv("TIMEZONE", "Asia/Tashkent"))

MONTH_NAMES = [
    "", "Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun",
    "Iyul", "Avgust", "Sentabr", "Oktabr", "Noyabr", "Dekabr",
]

MAX_NAME_LENGTH = 64

# /add buyrug'ining argumentlari: "Ism Familiya 15.03" yoki "Ism 15.03.1998"
ADD_ARGS_PATTERN = re.compile(
    r"^(?P<name>.+?)\s+(?P<day>\d{1,2})\.(?P<month>\d{1,2})(?:\.(?P<year>\d{4}))?$"
)


def now() -> datetime:
    """Bot vaqt mintaqasidagi (default Toshkent) joriy vaqt."""
    return datetime.now(TZ)


def today() -> date:
    """Bot vaqt mintaqasidagi bugungi sana (server vaqtiga bog'liq emas)."""
    return now().date()


def is_leap(year: int) -> bool:
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def validate_date(day: int, month: int, year: Optional[int] = None) -> Optional[str]:
    """
    Sanani tekshiradi. To'g'ri bo'lsa None, aks holda xato matnini qaytaradi.
    Yil ko'rsatilmasa 29-fevral ham qabul qilinadi.
    """
    if year is not None and not (1900 <= year <= today().year):
        return f"Yil 1900 va {today().year} oralig'ida bo'lishi kerak."
    try:
        # 2000-yil kabisa — yilsiz 29.02 ham o'tadi
        birth = date(year or 2000, month, day)
    except ValueError:
        return "Bunday sana mavjud emas."
    if year is not None and birth > today():
        return "Tug'ilgan sana kelajakda bo'lishi mumkin emas."
    return None


def birthday_in_year(day: int, month: int, year: int) -> date:
    """Berilgan yildagi tug'ilgan kun sanasi. Kabisa bo'lmagan yilda 29.02 → 28.02."""
    if month == 2 and day == 29 and not is_leap(year):
        return date(year, 2, 28)
    return date(year, month, day)


def birthday_keys_for(d: date) -> list[tuple[int, int]]:
    """Shu sanada nishonlanadigan (kun, oy) juftliklari."""
    keys = [(d.day, d.month)]
    if d.month == 2 and d.day == 28 and not is_leap(d.year):
        keys.append((29, 2))
    return keys


def calc_age(birth_year: int, on_date: date) -> int:
    return on_date.year - birth_year
