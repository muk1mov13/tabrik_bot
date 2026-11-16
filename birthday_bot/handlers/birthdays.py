"""
birthdays.py — Tug'ilgan kunlar: /add, /edit, /remove, /list, /find, /upcoming.
"""

from html import escape
from typing import Optional

from aiogram import Bot, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandObject
from aiogram.filters.callback_data import CallbackData
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from birthday_bot.config import Config
from birthday_bot.database import Database
from birthday_bot.dates import now
from birthday_bot.models import MAX_NAME_LENGTH
from birthday_bot.parsing import ParseError, parse_birthday, parse_edit
from birthday_bot.permissions import editable_group_id, target_group_id
from birthday_bot.texts import (
    birthday_line,
    format_date,
    mention,
    split_messages,
    upcoming_line,
)

router = Router(name="birthdays")

LIST_PAGE_SIZE = 20

ADD_USAGE = (
    "Namuna:\n"
    "<code>/add Ism 15.03</code>\n"
    "<code>/add Ism 15.03.1998</code>\n"
    "yoki odam xabariga reply qilib <code>/add 15.03</code>"
)
EDIT_USAGE = "Namuna: <code>/edit 3 Ism 15.03.1998</code> yoki <code>/edit 3 15.03</code>"


class ListPage(CallbackData, prefix="list"):
    page: int


async def answer_lines(message: Message, lines: list[str]):
    for chunk in split_messages(lines):
        await message.answer(chunk)


@router.message(Command("add"))
async def cmd_add(message: Message, command: CommandObject, bot: Bot, db: Database, config: Config):
    group_id = await editable_group_id(message, bot, db, config)
    if group_id is None:
        await message.answer("⛔ Tug'ilgan kun qo'shish faqat guruh adminlari va boshqaruvchilariga ruxsat etilgan.")
        return

    try:
        parsed = parse_birthday(command.args or "", now(config.timezone).date())
    except ParseError as exc:
        await message.answer(f"❗ {exc} {ADD_USAGE}")
        return

    # Reply qilingan xabar egasi tabrikda belgilanadi
    name, user_id = parsed.name, None
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
        day=parsed.day,
        month=parsed.month,
        year=parsed.year,
        added_by=message.from_user.id if message.from_user else None,
        user_id=user_id,
    )
    await message.answer(
        f"✅ Qo'shildi: <b>{mention(name, user_id)}</b> — "
        f"{format_date(parsed.day, parsed.month, parsed.year)}\n(ID: {record_id})"
    )


@router.message(Command("edit"))
async def cmd_edit(message: Message, command: CommandObject, bot: Bot, db: Database, config: Config):
    group_id = await editable_group_id(message, bot, db, config)
    if group_id is None:
        await message.answer("⛔ Tahrirlash faqat guruh adminlari va boshqaruvchilariga ruxsat etilgan.")
        return

    try:
        record_id, parsed = parse_edit(command.args or "", now(config.timezone).date())
    except ParseError as exc:
        await message.answer(f"❗ {exc} {EDIT_USAGE}")
        return

    existing = await db.get_birthday(group_id, record_id)
    if existing is None:
        await message.answer("Bunday ID topilmadi.")
        return

    name = parsed.name or existing.name
    await db.update_birthday(group_id, record_id, name, parsed.day, parsed.month, parsed.year)
    await message.answer(
        f"✏️ Yangilandi: <b>{mention(name, existing.user_id)}</b> — "
        f"{format_date(parsed.day, parsed.month, parsed.year)} (ID: {record_id})"
    )


@router.message(Command("remove"))
async def cmd_remove(message: Message, command: CommandObject, bot: Bot, db: Database, config: Config):
    group_id = await editable_group_id(message, bot, db, config)
    if group_id is None:
        await message.answer("⛔ Yozuvni o'chirish faqat guruh adminlari va boshqaruvchilariga ruxsat etilgan.")
        return

    arg = (command.args or "").strip()
    if not arg.isdigit():
        await message.answer("❗ Namuna: <code>/remove 3</code> (ID ni /list dan oling)")
        return

    if await db.remove_birthday(group_id, int(arg)):
        await message.answer("🗑 O'chirildi.")
    else:
        await message.answer("Bunday ID topilmadi.")


async def build_list_page(
    db: Database, group_id: int, page: int
) -> Optional[tuple[str, InlineKeyboardMarkup]]:
    total = await db.count_birthdays(group_id)
    if total == 0:
        return None
    pages = (total + LIST_PAGE_SIZE - 1) // LIST_PAGE_SIZE
    page = max(0, min(page, pages - 1))
    birthdays = await db.list_birthdays(group_id, limit=LIST_PAGE_SIZE, offset=page * LIST_PAGE_SIZE)

    lines = [f"📋 <b>Saqlangan tug'ilgan kunlar</b> ({total} ta):\n"]
    lines.extend(birthday_line(b) for b in birthdays)

    buttons = []
    if page > 0:
        buttons.append(InlineKeyboardButton(text="◀️", callback_data=ListPage(page=page - 1).pack()))
    if pages > 1:
        buttons.append(
            InlineKeyboardButton(text=f"{page + 1}/{pages}", callback_data=ListPage(page=page).pack())
        )
    if page < pages - 1:
        buttons.append(InlineKeyboardButton(text="▶️", callback_data=ListPage(page=page + 1).pack()))
    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=[buttons] if buttons else [])


@router.message(Command("list"))
async def cmd_list(message: Message, db: Database, config: Config):
    result = await build_list_page(db, target_group_id(message.chat, config), 0)
    if result is None:
        await message.answer("Bu guruhda hali birorta tug'ilgan kun qo'shilmagan.")
        return
    text, keyboard = result
    await message.answer(text, reply_markup=keyboard)


@router.callback_query(ListPage.filter())
async def cb_list_page(callback: CallbackQuery, callback_data: ListPage, db: Database, config: Config):
    if not isinstance(callback.message, Message):
        await callback.answer("Xabar eskirgan, /list ni qayta yuboring.")
        return

    result = await build_list_page(db, target_group_id(callback.message.chat, config), callback_data.page)
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
async def cmd_find(message: Message, command: CommandObject, db: Database, config: Config):
    query = (command.args or "").strip()
    if not query:
        await message.answer("❗ Namuna: <code>/find Ali</code>")
        return

    found = await db.find_birthdays(target_group_id(message.chat, config), query)
    if not found:
        await message.answer(f"«{escape(query)}» bo'yicha hech narsa topilmadi.")
        return

    lines = [f"🔎 <b>«{escape(query)}» bo'yicha natijalar:</b>\n"]
    lines.extend(birthday_line(b) for b in found)
    await answer_lines(message, lines)


@router.message(Command("upcoming"))
async def cmd_upcoming(message: Message, db: Database, config: Config):
    group_id = target_group_id(message.chat, config)
    days = (await db.get_settings(group_id)).upcoming_days
    upcoming = await db.get_upcoming(group_id, now(config.timezone).date(), days)
    if not upcoming:
        await message.answer(f"Keyingi {days} kun ichida tug'ilgan kun yo'q.")
        return

    lines = [f"🔔 <b>Yaqin {days} kundagi tug'ilgan kunlar:</b>\n"]
    lines.extend(upcoming_line(item) for item in upcoming)
    await answer_lines(message, lines)
