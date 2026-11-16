"""
scheduler.py — Har daqiqada tekshiradi: guruhning tabrik vaqti kelgan bo'lsa,
bugungi tug'ilgan kunlarni tabriklaydi va oldindan eslatmalarni yuboradi.

Har bir yozuv uchun last_notified / last_reminded saqlanadi, shuning uchun
xabar kuniga bir martadan ortiq ketmaydi (restart bo'lsa ham). Bot tabrik
vaqtidan keyin ishga tushsa, o'tkazib yuborilgan xabarlar darhol yuboriladi.
"""

import logging
import random
from typing import Optional

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramForbiddenError
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

import database as db
from utils import MONTH_NAMES, TZ, calc_age, mention, now

logger = logging.getLogger(__name__)

GREETINGS = [
    "🎉 Bugun {name} ning tug'ilgan kuni! Uni tabriklashni unutmang 🎂",
    "🎂 E'tibor bering — bugun {name} tug'ilgan kunini nishonlamoqda! 🥳",
    "🎈 Bugungi kun {name} uchun alohida — tug'ilgan kuni! Tabriklaymiz 🎁",
]


def build_greeting(row, on_date) -> str:
    text = random.choice(GREETINGS).format(name=f"<b>{mention(row['name'], row['user_id'])}</b>")
    if row["year"]:
        text += f"\n🎊 U bugun {calc_age(row['year'], on_date)} yoshga to'ldi!"
    return text


def build_reminder(item: dict) -> str:
    row, bday, days_left = item["row"], item["date"], item["days_left"]
    text = (
        f"⏰ {days_left} kundan keyin ({bday.day} {MONTH_NAMES[bday.month]}) — "
        f"<b>{mention(row['name'], row['user_id'])}</b> ning tug'ilgan kuni!"
    )
    if row["year"]:
        text += f" U {calc_age(row['year'], bday)} yoshga to'ladi."
    return text + "\nSovg'a tayyorlashni unutmang 🎁"


async def _send(bot: Bot, chat_id: int, text: str, sticker: Optional[str] = None) -> bool:
    try:
        await bot.send_message(chat_id=chat_id, text=text)
    except TelegramForbiddenError:
        logger.warning("Bot guruhga yoza olmaydi (chiqarilgan bo'lishi mumkin): guruh=%s", chat_id)
        return False
    except TelegramAPIError as exc:
        logger.error("Xabar yuborishda xatolik (guruh=%s): %s", chat_id, exc)
        return False

    if sticker:
        try:
            await bot.send_sticker(chat_id=chat_id, sticker=sticker)
        except TelegramAPIError as exc:
            # Stiker xatosi tabrikni qayta yuborishga sabab bo'lmasligi kerak
            logger.warning("Stiker yuborilmadi (guruh=%s): %s", chat_id, exc)
    return True


async def check_and_notify(bot: Bot):
    current = now()
    on_date, at = current.date(), current.time().replace(second=0, microsecond=0)

    for row in await db.get_pending_birthdays(on_date, at):
        if await _send(bot, row["group_id"], build_greeting(row, on_date), row["sticker_file_id"]):
            await db.mark_notified(row["id"], on_date)
            logger.info("Tabrik yuborildi: guruh=%s, id=%s", row["group_id"], row["id"])

    for item in await db.get_pending_reminders(on_date, at):
        row = item["row"]
        if await _send(bot, row["group_id"], build_reminder(item)):
            await db.mark_reminded(row["id"], on_date)
            logger.info("Eslatma yuborildi: guruh=%s, id=%s", row["group_id"], row["id"])


async def _safe_check(bot: Bot):
    try:
        await check_and_notify(bot)
    except Exception:
        logger.exception("Tug'ilgan kunlarni tekshirishda xatolik")


def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    """Har daqiqada ishlaydigan tekshiruvchi scheduler (bot vaqt mintaqasida)."""
    scheduler = AsyncIOScheduler(timezone=TZ)
    scheduler.add_job(
        _safe_check,
        trigger=CronTrigger(minute="*", timezone=TZ),
        kwargs={"bot": bot},
        id="birthday_check",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        next_run_time=now(),  # ishga tushganda darhol bir marta tekshiradi
    )
    scheduler.start()
    logger.info("Scheduler ishga tushdi: har daqiqada tekshiriladi (%s).", TZ.key)
    return scheduler
