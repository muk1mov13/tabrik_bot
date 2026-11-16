"""
scheduler.py — Har daqiqada tekshiradi: guruhning tabrik vaqti kelgan bo'lsa,
bugungi tug'ilgan kunlarni tabriklaydi va oldindan eslatmalarni yuboradi.

Har bir yozuv uchun last_notified / last_reminded saqlanadi va faqat
muvaffaqiyatli yuborilgandan keyin qo'yiladi — shuning uchun xabar kuniga bir
martadan ortiq ketmaydi (restart bo'lsa ham). Bot tabrik vaqtidan keyin ishga
tushsa, o'tkazib yuborilgan xabarlar darhol yuboriladi.
"""

import logging
from datetime import date, datetime
from typing import Optional

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramForbiddenError, TelegramNetworkError
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from birthday_bot.config import Config
from birthday_bot.database import Database
from birthday_bot.dates import now
from birthday_bot.permissions import Role, get_role
from birthday_bot.texts import greeting, reminder, send_failed_text

logger = logging.getLogger(__name__)


async def _send(
    bot: Bot, chat_id: int, text: str, sticker: Optional[str] = None
) -> Optional[TelegramAPIError]:
    """Xabarni yuboradi; muvaffaqiyatli bo'lsa None, aks holda xatoning o'zi."""
    try:
        await bot.send_message(chat_id=chat_id, text=text)
    except TelegramNetworkError as exc:
        logger.warning("Internet bilan muammo, keyingi daqiqada qayta uriniladi (guruh=%s): %s", chat_id, exc)
        return exc
    except TelegramForbiddenError as exc:
        logger.warning("Bot guruhga yoza olmaydi (chiqarilgan bo'lishi mumkin): guruh=%s", chat_id)
        return exc
    except TelegramAPIError as exc:
        logger.error("Xabar yuborishda xatolik (guruh=%s): %s", chat_id, exc)
        return exc

    if sticker:
        try:
            await bot.send_sticker(chat_id=chat_id, sticker=sticker)
        except TelegramAPIError as exc:
            # Stiker xatosi tabrikni qayta yuborishga sabab bo'lmasligi kerak
            logger.warning("Stiker yuborilmadi (guruh=%s): %s", chat_id, exc)
    return None


async def _report_failure(
    bot: Bot,
    db: Database,
    group_id: int,
    on_date: date,
    error: TelegramAPIError,
    failures: Optional[set],
):
    """
    Guruhga yozib bo'lmasa — boshqaruvchilar va adminlarga shaxsiy xabar, har guruh
    uchun kuniga bir marta (tabrik har daqiqada qayta uriniladi). Internet uzilishi
    guruh muammosi emas — u haqda xabar berilmaydi.
    """
    if isinstance(error, TelegramNetworkError):
        return
    if failures is None or (group_id, on_date) in failures:
        return
    failures.add((group_id, on_date))

    group = await db.get_group(group_id)
    text = send_failed_text(group.title if group and group.title else str(group_id), error.message)
    # Boshqaruvchilar rol tekshirilmasdan: bot chiqarilgan bo'lsa rolni ham bilib bo'lmaydi
    recipients = set(await db.list_managers(group_id))
    for user_id in await db.linked_users(group_id):
        if user_id not in recipients and await get_role(bot, db, group_id, user_id) == Role.ADMIN:
            recipients.add(user_id)
    for user_id in sorted(recipients):
        try:
            await bot.send_message(chat_id=user_id, text=text)
        except TelegramAPIError as exc:
            # Foydalanuvchi botga hech yozmagan bo'lishi mumkin
            logger.warning("Xato haqida xabar yuborilmadi (user=%s): %s", user_id, exc)


async def check_and_notify(
    bot: Bot, db: Database, current: datetime, failures: Optional[set] = None
):
    on_date, at = current.date(), current.time().replace(second=0, microsecond=0)

    for birthday, sticker in await db.get_pending_greetings(on_date, at):
        template = (await db.get_settings(birthday.group_id)).greeting_template
        text = greeting(birthday, on_date, template=template)
        error = await _send(bot, birthday.group_id, text, sticker)
        if error is None:
            await db.mark_notified(birthday.id, on_date)
            logger.info("Tabrik yuborildi: guruh=%s, id=%s", birthday.group_id, birthday.id)
        else:
            await _report_failure(bot, db, birthday.group_id, on_date, error, failures)

    for item in await db.get_pending_reminders(on_date, at):
        birthday = item.birthday
        error = await _send(bot, birthday.group_id, reminder(item))
        if error is None:
            await db.mark_reminded(birthday.id, on_date)
            logger.info("Eslatma yuborildi: guruh=%s, id=%s", birthday.group_id, birthday.id)
        else:
            await _report_failure(bot, db, birthday.group_id, on_date, error, failures)


async def _scheduled_check(bot: Bot, db: Database, config: Config, failures: set):
    try:
        await check_and_notify(bot, db, now(config.timezone), failures)
    except Exception:
        logger.exception("Tug'ilgan kunlarni tekshirishda xatolik")


def setup_scheduler(bot: Bot, db: Database, config: Config) -> AsyncIOScheduler:
    """Har daqiqada ishlaydigan tekshiruvchi scheduler (bot vaqt mintaqasida)."""
    scheduler = AsyncIOScheduler(timezone=config.timezone)
    scheduler.add_job(
        _scheduled_check,
        trigger=CronTrigger(minute="*", timezone=config.timezone),
        # failures — bugun xato haqida xabar berilgan (guruh, sana) juftliklari
        kwargs={"bot": bot, "db": db, "config": config, "failures": set()},
        id="birthday_check",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        next_run_time=now(config.timezone),  # ishga tushganda darhol bir marta tekshiradi
    )
    scheduler.start()
    logger.info("Scheduler ishga tushdi: har daqiqada tekshiriladi (%s).", config.timezone.key)
    return scheduler
