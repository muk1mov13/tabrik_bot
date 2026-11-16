"""
handlers.py — Tug'ilgan kun buyruqlarini qayta ishlovchi funksiyalar.
"""

import logging
import re
from html import escape
from typing import Optional, Union

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandObject
from aiogram.filters.callback_data import CallbackData
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

import database as db
from permissions import can_edit, get_target_group_id
from utils import ADD_ARGS_PATTERN, MAX_NAME_LENGTH, MONTH_NAMES, mention, validate_date

logger = logging.getLogger(__name__)

router = Router()

# Telegram xabar chegarasi 4096 belgi — biroz zaxira qoldiramiz
MESSAGE_LIMIT = 4000
LIST_PAGE_SIZE = 20

EDIT_PATTERN = re.compile(r"^(?P<id>\d+)\s+(?P<rest>.+)$")


class ListPage(CallbackData, prefix="list"):
    page: int


ParsedBirthday = tuple[Optional[str], int, int, Optional[int]]


def parse_birthday_args(text: str) -> Union[ParsedBirthday, str]:
    """'[Ism] DD.MM[.YYYY]' ni (ism, kun, oy, yil) ga ajratadi yoki xato matnini qaytaradi."""
    match = ADD_ARGS_PATTERN.match(text.strip())
    if not match:
        return "Format noto'g'ri."
    name = " ".join(match["name"].split()) if match["name"] else None
    day, month = int(match["day"]), int(match["month"])
    year = int(match["year"]) if match["year"] else None
    if name and len(name) > MAX_NAME_LENGTH:
        return f"Ism {MAX_NAME_LENGTH} belgidan oshmasligi kerak."
    error = validate_date(day, month, year)
    if error:
        return error
    return name, day, month, year


def format_date(day: int, month: int, year: Optional[int] = None) -> str:
    return f"{day} {MONTH_NAMES[month]}" + (f" {year}" if year else "")


def format_row(row) -> str:
    year_part = f" ({row['year']})" if row["year"] else ""
    return (
        f"• [{row['id']}] {mention(row['name'], row['user_id'])} — "
        f"{row['day']} {MONTH_NAMES[row['month']]}{year_part}"
    )


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
        "<b>Hamma uchun:</b>\n"
        "• <code>/list</code> — saqlangan tug'ilgan kunlar\n"
        "• <code>/upcoming</code> — yaqin kunlardagi tug'ilgan kunlar\n"
        "• <code>/find Ism</code> — ism bo'yicha qidirish\n"
        "• <code>/settings</code> — guruh sozlamalari\n\n"
        "<b>Adminlar uchun:</b>\n"
        "• <code>/add Ism 15.03</code> yoki <code>/add Ism 15.03.1998</code>\n"
        "• odam xabariga reply qilib <code>/add 15.03</code> — tabrikda u belgilanadi\n"
        "• <code>/edit ID Ism 15.03.1998</code> yoki <code>/edit ID 15.03</code>\n"
        "• <code>/remove ID</code> — yozuvni o'chirish\n"
        "• <code>/settings time 09:00</code> — tabrik vaqti\n"
        "• <code>/settings remind 3</code> — 3 kun oldin eslatma (0 — o'chirish)\n"
        "• <code>/settings upcoming 14</code> — /upcoming necha kunni ko'rsatadi\n"
        "• stikerga reply qilib <code>/setsticker</code> — tabrik stikeri "
        "(<code>/setsticker off</code> — o'chirish)\n\n"
        "ID ni /list dan oling. Botni guruhga qo'shing — u tug'ilgan kuni bor "
        "odamni har kuni tabriklab turadi 🎉"
    )
    await message.answer(text)


@router.message(Command("add"))
async def cmd_add(message: Message, command: CommandObject, bot: Bot):
    allowed, group_id = await can_edit(message, bot)
    if not allowed:
        await message.answer("⛔ Tug'ilgan kun qo'shish faqat guruh adminlariga ruxsat etilgan.")
        return

    parsed = parse_birthday_args(command.args or "")
    if isinstance(parsed, str):
        await message.answer(
            f"❗ {parsed} Namuna:\n"
            "<code>/add Ism 15.03</code>\n"
            "<code>/add Ism 15.03.1998</code>\n"
            "yoki odam xabariga reply qilib <code>/add 15.03</code>"
        )
        return
    name, day, month, year = parsed

    # Reply qilingan xabar egasi tabrikda belgilanadi
    user_id = None
    replied = message.reply_to_message
    if replied and replied.from_user and not replied.from_user.is_bot:
        user_id = replied.from_user.id
        name = name or replied.from_user.full_name[:MAX_NAME_LENGTH]

    if not name:
        await message.answer(
            "❗ Ism ko'rsatilmagan. <code>/add Ism 15.03</code> yozing "
            "yoki odam xabariga reply qiling."
        )
        return

    record_id = await db.add_birthday(
        group_id=group_id,
        name=name,
        day=day,
        month=month,
        year=year,
        added_by=message.from_user.id if message.from_user else None,
        user_id=user_id,
    )
    await message.answer(
        f"✅ Qo'shildi: <b>{mention(name, user_id)}</b> — {format_date(day, month, year)}"
        f"\n(ID: {record_id})"
    )


@router.message(Command("edit"))
async def cmd_edit(message: Message, command: CommandObject, bot: Bot):
    allowed, group_id = await can_edit(message, bot)
    if not allowed:
        await message.answer("⛔ Tahrirlash faqat guruh adminlariga ruxsat etilgan.")
        return

    usage = "Namuna: <code>/edit 3 Ism 15.03.1998</code> yoki <code>/edit 3 15.03</code>"
    match = EDIT_PATTERN.match((command.args or "").strip())
    if not match:
        await message.answer(f"❗ {usage}")
        return

    record_id = int(match["id"])
    parsed = parse_birthday_args(match["rest"])
    if isinstance(parsed, str):
        await message.answer(f"❗ {parsed} {usage}")
        return
    name, day, month, year = parsed

    row = await db.get_birthday(group_id, record_id)
    if row is None:
        await message.answer("Bunday ID topilmadi.")
        return
    name = name or row["name"]

    await db.update_birthday(group_id, record_id, name, day, month, year)
    await message.answer(
        f"✏️ Yangilandi: <b>{mention(name, row['user_id'])}</b> — "
        f"{format_date(day, month, year)} (ID: {record_id})"
    )


async def build_list_page(group_id: int, page: int) -> Optional[tuple[str, InlineKeyboardMarkup]]:
    total = await db.count_birthdays(group_id)
    if total == 0:
        return None
    pages = (total + LIST_PAGE_SIZE - 1) // LIST_PAGE_SIZE
    page = max(0, min(page, pages - 1))
    rows = await db.list_birthdays(group_id, limit=LIST_PAGE_SIZE, offset=page * LIST_PAGE_SIZE)

    lines = [f"📋 <b>Saqlangan tug'ilgan kunlar</b> ({total} ta):\n"]
    lines.extend(format_row(row) for row in rows)

    buttons = []
    if page > 0:
        buttons.append(InlineKeyboardButton(text="◀️", callback_data=ListPage(page=page - 1).pack()))
    if pages > 1:
        buttons.append(InlineKeyboardButton(text=f"{page + 1}/{pages}", callback_data=ListPage(page=page).pack()))
    if page < pages - 1:
        buttons.append(InlineKeyboardButton(text="▶️", callback_data=ListPage(page=page + 1).pack()))
    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=[buttons] if buttons else [])


@router.message(Command("list"))
async def cmd_list(message: Message):
    result = await build_list_page(get_target_group_id(message.chat), 0)
    if result is None:
        await message.answer("Bu guruhda hali birorta tug'ilgan kun qo'shilmagan.")
        return
    text, keyboard = result
    await message.answer(text, reply_markup=keyboard)


@router.callback_query(ListPage.filter())
async def cb_list_page(callback: CallbackQuery, callback_data: ListPage):
    if not isinstance(callback.message, Message):
        await callback.answer("Xabar eskirgan, /list ni qayta yuboring.")
        return
    result = await build_list_page(get_target_group_id(callback.message.chat), callback_data.page)
    try:
        if result is None:
            await callback.message.edit_text("Bu guruhda hali birorta tug'ilgan kun qo'shilmagan.")
        else:
            text, keyboard = result
            await callback.message.edit_text(text, reply_markup=keyboard)
    except TelegramBadRequest as exc:
        # Sahifa raqami tugmasi bosilganda matn o'zgarmaydi — bu xato emas
        if "message is not modified" not in str(exc):
            raise
    await callback.answer()


@router.message(Command("find"))
async def cmd_find(message: Message, command: CommandObject):
    query = (command.args or "").strip()
    if not query:
        await message.answer("❗ Namuna: <code>/find Ali</code>")
        return

    rows = await db.find_birthdays(get_target_group_id(message.chat), query)
    if not rows:
        await message.answer(f"«{escape(query)}» bo'yicha hech narsa topilmadi.")
        return

    lines = [f"🔎 <b>«{escape(query)}» bo'yicha natijalar:</b>\n"]
    lines.extend(format_row(row) for row in rows)
    await answer_long(message, lines)


@router.message(Command("upcoming"))
async def cmd_upcoming(message: Message):
    group_id = get_target_group_id(message.chat)
    days = (await db.get_settings(group_id))["upcoming_days"]
    upcoming = await db.get_upcoming(group_id, days_ahead=days)
    if not upcoming:
        await message.answer(f"Keyingi {days} kun ichida tug'ilgan kun yo'q.")
        return

    lines = [f"🔔 <b>Yaqin {days} kundagi tug'ilgan kunlar:</b>\n"]
    for item in upcoming:
        row = item["row"]
        bday = item["date"]
        days_left = item["days_left"]
        when = "bugun" if days_left == 0 else f"{days_left} kundan keyin"
        lines.append(
            f"• {mention(row['name'], row['user_id'])} — "
            f"{bday.day} {MONTH_NAMES[bday.month]} ({when})"
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


@router.message(F.migrate_to_chat_id)
async def on_group_migrated(message: Message):
    """Oddiy guruh supergroupga aylanganda yozuvlarni yangi chat ID ga ko'chiradi."""
    await db.migrate_group(message.chat.id, message.migrate_to_chat_id)
    logger.info("Guruh ko'chirildi: %s -> %s", message.chat.id, message.migrate_to_chat_id)
