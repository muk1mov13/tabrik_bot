"""
scheduler.py — Har daqiqada tekshiradi: guruhning tabrik vaqti kelgan bo'lsa,
bugungi tug'ilgan kunlarni tabriklaydi va oldindan eslatmalarni yuboradi.

Har bir yozuv uchun last_notified / last_reminded saqlanadi va faqat
muvaffaqiyatli yuborilgandan keyin qo'yiladi — shuning uchun xabar kuniga bir
martadan ortiq ketmaydi (restart bo'lsa ham). Bot tabrik vaqtidan keyin ishga
tushsa, o'tkazib yuborilgan xabarlar darhol yuboriladi.
"""

import logging
from datetime import datetime
from typing import Optional

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramForbiddenError
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from birthday_bot.config import Config
from birthday_bot.database import Database
from birthday_bot.dates import now
from birthday_bot.texts import greeting, reminder

logger = logging.getLogger(__name__)


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


async def check_and_notify(bot: Bot, db: Database, current: datetime):
    on_date, at = current.date(), current.time().replace(second=0, microsecond=0)

    for birthday, sticker in await db.get_pending_greetings(on_date, at):
        if await _send(bot, birthday.group_id, greeting(birthday, on_date), sticker):
            await db.mark_notified(birthday.id, on_date)
            logger.info("Tabrik yuborildi: guruh=%s, id=%s", birthday.group_id, birthday.id)

    for item in await db.get_pending_reminders(on_date, at):
        birthday = item.birthday
        if await _send(bot, birthday.group_id, reminder(item)):
            await db.mark_reminded(birthday.id, on_date)
            logger.info("Eslatma yuborildi: guruh=%s, id=%s", birthday.group_id, birthday.id)


async def _scheduled_check(bot: Bot, db: Database, config: Config):
    try:
        await check_and_notify(bot, db, now(config.timezone))
    except Exception:
        logger.exception("Tug'ilgan kunlarni tekshirishda xatolik")


def setup_scheduler(bot: Bot, db: Database, config: Config) -> AsyncIOScheduler:
    """Har daqiqada ishlaydigan tekshiruvchi scheduler (bot vaqt mintaqasida)."""
    scheduler = AsyncIOScheduler(timezone=config.timezone)
    scheduler.add_job(
        _scheduled_check,
        trigger=CronTrigger(minute="*", timezone=config.timezone),
        kwargs={"bot": bot, "db": db, "config": config},
        id="birthday_check",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        next_run_time=now(config.timezone),  # ishga tushganda darhol bir marta tekshiradi
    )
    scheduler.start()
    logger.info("Scheduler ishga tushdi: har daqiqada tekshiriladi (%s).", config.timezone.key)
    return scheduler
