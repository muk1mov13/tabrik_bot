"""
config.py — Bot sozlamalarini muhit o'zgaruvchilaridan (.env) o'qish.
Noto'g'ri qiymat bo'lsa bot darhol tushunarli xato bilan to'xtaydi.
"""

import os
from dataclasses import dataclass
from datetime import time
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotenv import load_dotenv

from birthday_bot.dates import parse_time


class ConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class Config:
    bot_token: str
    database_path: Path
    timezone: ZoneInfo
    notify_time: time
    default_group_id: Optional[int] = None


def load_config() -> Config:
    load_dotenv()

    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise ConfigError("BOT_TOKEN topilmadi. .env fayliga qo'shing: BOT_TOKEN=...")

    tz_name = os.getenv("TIMEZONE", "Asia/Tashkent").strip()
    try:
        timezone = ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, ValueError):
        raise ConfigError(f"TIMEZONE noto'g'ri: {tz_name!r} (masalan: Asia/Tashkent)")

    raw_time = os.getenv("NOTIFICATION_TIME", "08:00")
    notify_time = parse_time(raw_time)
    if notify_time is None:
        raise ConfigError(f"NOTIFICATION_TIME noto'g'ri: {raw_time!r} (format: HH:MM)")

    raw_group = os.getenv("DEFAULT_GROUP_ID", "").strip()
    default_group_id = None
    if raw_group:
        try:
            default_group_id = int(raw_group)
        except ValueError:
            raise ConfigError(f"DEFAULT_GROUP_ID butun son bo'lishi kerak: {raw_group!r}")

    database_path = Path(os.getenv("DATABASE_PATH", "data/birthdays.db").strip())

    return Config(
        bot_token=token,
        database_path=database_path,
        timezone=timezone,
        notify_time=notify_time,
        default_group_id=default_group_id,
    )
