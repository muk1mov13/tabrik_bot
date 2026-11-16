"""
scheduler.py — Har kuni belgilangan vaqtda tug'ilgan kunlarni tekshirib,
tegishli guruhlarga tabrik xabarini yuboradi.
"""

import logging
import os
import random
from datetime import time
from html import escape
from typing import Optional

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramForbiddenError
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

import database as db
from utils import TZ, calc_age, now, today

logger = logging.getLogger(__name__)

GREETINGS = [
    "🎉 Bugun {name} ning tug'ilgan kuni! Uni tabriklashni unutmang 🎂",
    "🎂 E'tibor bering — bugun {name} tug'ilgan kunini nishonlamoqda! 🥳",
    "🎈 Bugungi kun {name} uchun alohida — tug'ilgan kuni! Tabriklaymiz 🎁",
]


def _build_message(name: str, year: Optional[int]) -> str:
    text = random.choice(GREETINGS).format(name=f"<b>{escape(name)}</b>")
    if year:
        text += f"\n🎊 U bugun {calc_age(year, today())} yoshga to'ldi!"
    return text


def get_notification_time() -> time:
    value = os.getenv("NOTIFICATION_TIME", "08:00")
    try:
        hour, minute = (int(part) for part in value.split(":"))
        return time(hour, minute)
    except ValueError:
        logger.warning("NOTIFICATION_TIME noto'g'ri (%r), 08:00 ishlatiladi.", value)
        return time(8, 0)


async def check_and_notify(bot: Bot):
    current = today()
    rows = await db.get_pending_birthdays(current)
    if not rows:
        logger.info("Bugun uchun yuborilmagan tabrik yo'q.")
        return

    for row in rows:
        try:
            await bot.send_message(
                chat_id=row["group_id"],
                text=_build_message(row["name"], row["year"]),
            )
        except TelegramForbiddenError:
            logger.warning(
                "Bot guruhga yoza olmaydi (chiqarilgan bo'lishi mumkin): guruh=%s",
                row["group_id"],
            )
            continue
        except TelegramAPIError as exc:
            logger.error("Xabar yuborishda xatolik (guruh=%s): %s", row["group_id"], exc)
            continue

        await db.mark_notified(row["id"], current)
        logger.info("Xabar yuborildi: guruh=%s, id=%s", row["group_id"], row["id"])


async def notify_if_missed(bot: Bot):
    """Bot belgilangan vaqtdan keyin ishga tushgan bo'lsa, bugungi tabriklarni yuboradi."""
    if now().time() >= get_notification_time():
        await check_and_notify(bot)


def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    """Har kuni NOTIFICATION_TIME da (bot vaqt mintaqasida) tekshiruvchi scheduler."""
    at = get_notification_time()
    scheduler = AsyncIOScheduler(timezone=TZ)
    scheduler.add_job(
        check_and_notify,
        trigger=CronTrigger(hour=at.hour, minute=at.minute, timezone=TZ),
        kwargs={"bot": bot},
        id="daily_birthday_check",
        replace_existing=True,
        misfire_grace_time=3600,
        coalesce=True,
    )
    scheduler.start()
    logger.info("Scheduler ishga tushdi: har kuni soat %s da (%s) tekshiriladi.", at.strftime("%H:%M"), TZ.key)
    return scheduler
