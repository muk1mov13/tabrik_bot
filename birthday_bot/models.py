"""
models.py — Ma'lumot tuzilmalari va cheklovlar.
"""

from dataclasses import dataclass
from datetime import date, time
from typing import Optional

MAX_NAME_LENGTH = 64
MAX_REMIND_DAYS = 30
MAX_UPCOMING_DAYS = 60


@dataclass(frozen=True)
class Birthday:
    id: int
    group_id: int
    name: str
    day: int
    month: int
    year: Optional[int] = None
    user_id: Optional[int] = None


@dataclass(frozen=True)
class GroupSettings:
    notify_time: time
    remind_days: int = 0
    upcoming_days: int = 7
    sticker_file_id: Optional[str] = None
    greeting_template: Optional[str] = None  # None — standart tabriklar


@dataclass(frozen=True)
class Upcoming:
    birthday: Birthday
    date: date
    days_left: int


@dataclass(frozen=True)
class Group:
    group_id: int
    title: str
    active: bool = True
