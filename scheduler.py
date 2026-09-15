"""
scheduler.py — Har kuni belgilangan vaqtda tug'ilgan kunlarni tekshirib,
tegishli guruhlarga tabrik xabarini yuboradi.
"""

import logging
import os
import random
from datetime import date


from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

import database as db

logger = logging.getLogger(__name__)

MONTH_NAMES = [
    "", "Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun",
    "Iyul", "Avgust", "Sentabr", "Oktabr", "Noyabr", "Dekabr",
]

GREETINGS = [
    "🎉 Bugun {name} ning tug'ilgan kuni! Uni tabriklashni unutmang 🎂",
    "🎂 E'tibor bering — bugun {name} tug'ilgan kunini nishonlamoqda! 🥳",
    "🎈 Bugungi kun {name} uchun alohida — tug'ilgan kuni! Tabriklaymiz 🎁",
]


def _build_message(name: str, year: int | None) -> str:
    text = random.choice(GREETINGS).format(name=name)
    if year:
        age = date.today().year - year
        text += f"\n🎊 U bugun {age} yoshga to'ldi!"
    return text


async def check_and_notify(bot: Bot):
    today = date.today()
    rows = await db.get_birthdays_for_date(today.day, today.month)
    if not rows:
        logger.info("Bugun uchun tug'ilgan kun topilmadi.")
        return

    for row in rows:
        try:
            await bot.send_message(
                chat_id=row["group_id"],
                text=_build_message(row["name"], row["year"]),
            )
            logger.info("Xabar yuborildi: guruh=%s, ism=%s", row["group_id"], row["name"])
        except Exception as exc:
            logger.error("Xabar yuborishda xatolik (guruh=%s): %s", row["group_id"], exc)


def setup_scheduler(bot: Bot, hours: str | None = None, minute: int = 0) -> AsyncIOScheduler:
    """
    Har kuni belgilangan soatlarda (masalan, 08:00 va 10:00, Toshkent vaqti bo'yicha)
    tug'ilgan kunlarni tekshiradigan scheduler yaratadi va ishga tushiradi.
    """
    if not hours:
        hours = os.getenv("NOTIFICATION_HOURS", "8,10")

    scheduler = AsyncIOScheduler(timezone="Asia/Tashkent")
    scheduler.add_job(
        check_and_notify,
        trigger=CronTrigger(hour=hours, minute=minute),
        kwargs={"bot": bot},
        id="daily_birthday_check",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler ishga tushdi: har kuni soat %s:%02d da tekshiriladi.", hours, minute)
    return scheduler

