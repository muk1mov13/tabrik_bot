"""
handlers.py — Bot buyruqlarini qayta ishlovchi funksiyalar.
"""

import logging
import os
from html import escape
from typing import Optional

from aiogram import Bot, Router
from aiogram.enums import ChatMemberStatus, ChatType
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

import database as db
from utils import ADD_ARGS_PATTERN, MAX_NAME_LENGTH, MONTH_NAMES, validate_date

logger = logging.getLogger(__name__)

router = Router()

# Telegram xabar chegarasi 4096 belgi — biroz zaxira qoldiramiz
MESSAGE_LIMIT = 4000

ADMIN_STATUSES = {ChatMemberStatus.CREATOR, ChatMemberStatus.ADMINISTRATOR}


def get_default_group_id() -> Optional[int]:
    value = os.getenv("DEFAULT_GROUP_ID")
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        logger.warning("DEFAULT_GROUP_ID noto'g'ri: %r", value)
        return None


def get_target_group_id(message: Message) -> int:
    """
    Agar shaxsiy chatdan yozilgan bo'lsa va DEFAULT_GROUP_ID mavjud bo'lsa,
    o'sha guruh ID'sini qaytaradi. Aks holda hozirgi chat ID'sini qaytaradi.
    """
    default_gid = get_default_group_id()
    if message.chat.type == ChatType.PRIVATE and default_gid:
        return default_gid
    return message.chat.id


async def can_edit(message: Message, bot: Bot) -> tuple[bool, Optional[int]]:
    """
    Foydalanuvchi yozuvlarni o'zgartira oladimi? (ruxsat, guruh_id) qaytaradi.
    Guruhda — shu guruh admini; shaxsiy chatda — DEFAULT_GROUP_ID guruhining admini.
    """
    if message.chat.type == ChatType.PRIVATE:
        group_id = get_default_group_id()
        if group_id is None:
            return False, None
    else:
        group_id = message.chat.id
        # Anonim admin guruh nomidan yozadi
        if message.sender_chat and message.sender_chat.id == group_id:
            return True, group_id

    if message.from_user is None:
        return False, group_id
    try:
        member = await bot.get_chat_member(group_id, message.from_user.id)
    except TelegramAPIError as exc:
        logger.warning("Adminlikni tekshirib bo'lmadi (guruh=%s): %s", group_id, exc)
        return False, group_id
    return member.status in ADMIN_STATUSES, group_id


async def answer_long(message: Message, lines: list[str]):
    """Uzun ro'yxatni Telegram chegarasidan oshirmay bo'laklab yuboradi."""
    chunk = ""
    for line in lines:
        if chunk and len(chunk) + len(line) + 1 > MESSAGE_LIMIT:
            await message.answer(chunk)
            chunk = ""
        chunk = f"{chunk}\n{line}" if chunk else line
    if chunk:
        await message.answer(chunk)


@router.message(Command("start", "help"))
async def cmd_help(message: Message):
    text = (
        "🎂 <b>Tug'ilgan kun eslatuvchi bot</b>\n\n"
        "Buyruqlar:\n"
        "• <code>/add Ism 15.03</code> — tug'ilgan kun qo'shish\n"
        "• <code>/add Ism 15.03.1998</code> — yil bilan (yosh hisoblanadi)\n"
        "• <code>/list</code> — barcha saqlangan tug'ilgan kunlar\n"
        "• <code>/upcoming</code> — yaqin 7 kundagi tug'ilgan kunlar\n"
        "• <code>/remove ID</code> — yozuvni o'chirish (ID ni /list dan oling)\n\n"
        "ℹ️ <code>/add</code> va <code>/remove</code> faqat guruh adminlari uchun.\n\n"
        "Botni guruhga qo'shing — u har kuni ertalab "
        "tug'ilgan kuni bor odamni eslatib turadi 🎉"
    )
    await message.answer(text)


@router.message(Command("add"))
async def cmd_add(message: Message, command: CommandObject, bot: Bot):
    allowed, group_id = await can_edit(message, bot)
    if not allowed:
        await message.answer("⛔ Tug'ilgan kun qo'shish faqat guruh adminlariga ruxsat etilgan.")
        return

    match = ADD_ARGS_PATTERN.match((command.args or "").strip())
    if not match:
        await message.answer(
            "❗ Format noto'g'ri. Namuna:\n"
            "<code>/add Ism 15.03</code>\n"
            "<code>/add Ism 15.03.1998</code>"
        )
        return

    name = " ".join(match.group("name").split())
    day = int(match.group("day"))
    month = int(match.group("month"))
    year = int(match.group("year")) if match.group("year") else None

    if len(name) > MAX_NAME_LENGTH:
        await message.answer(f"❗ Ism {MAX_NAME_LENGTH} belgidan oshmasligi kerak.")
        return

    error = validate_date(day, month, year)
    if error:
        await message.answer(f"❗ {error}")
        return

    record_id = await db.add_birthday(
        group_id=group_id,
        name=name,
        day=day,
        month=month,
        year=year,
        added_by=message.from_user.id if message.from_user else None,
    )
    await message.answer(
        f"✅ Qo'shildi: <b>{escape(name)}</b> — {day} {MONTH_NAMES[month]}"
        + (f" {year}" if year else "")
        + f"\n(ID: {record_id})"
    )


@router.message(Command("list"))
async def cmd_list(message: Message):
    rows = await db.list_birthdays(get_target_group_id(message))
    if not rows:
        await message.answer("Bu guruhda hali birorta tug'ilgan kun qo'shilmagan.")
        return

    lines = ["📋 <b>Saqlangan tug'ilgan kunlar:</b>\n"]
    for row in rows:
        year_part = f" ({row['year']})" if row["year"] else ""
        lines.append(
            f"• [{row['id']}] {escape(row['name'])} — "
            f"{row['day']} {MONTH_NAMES[row['month']]}{year_part}"
        )
    await answer_long(message, lines)


@router.message(Command("upcoming"))
async def cmd_upcoming(message: Message):
    upcoming = await db.get_upcoming(get_target_group_id(message), days_ahead=7)
    if not upcoming:
        await message.answer("Keyingi 7 kun ichida tug'ilgan kun yo'q.")
        return

    lines = ["🔔 <b>Yaqin kunlardagi tug'ilgan kunlar:</b>\n"]
    for item in upcoming:
        row = item["row"]
        bday = item["date"]
        days_left = item["days_left"]
        when = "bugun" if days_left == 0 else f"{days_left} kundan keyin"
        lines.append(
            f"• {escape(row['name'])} — {bday.day} {MONTH_NAMES[bday.month]} ({when})"
        )
    await answer_long(message, lines)


@router.message(Command("remove"))
async def cmd_remove(message: Message, command: CommandObject, bot: Bot):
    allowed, group_id = await can_edit(message, bot)
    if not allowed:
        await message.answer("⛔ Yozuvni o'chirish faqat guruh adminlariga ruxsat etilgan.")
        return

    arg = (command.args or "").strip()
    if not arg.isdigit():
        await message.answer("❗ Namuna: <code>/remove 3</code> (ID ni /list dan oling)")
        return

    if await db.remove_birthday(group_id, int(arg)):
        await message.answer("🗑 O'chirildi.")
    else:
        await message.answer("Bunday ID topilmadi.")
