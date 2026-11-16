"""
settings.py — Guruh sozlamalari: /settings va /setsticker.
"""

from aiogram import Bot, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from birthday_bot.config import Config
from birthday_bot.database import Database
from birthday_bot.dates import format_time, parse_time
from birthday_bot.models import MAX_REMIND_DAYS, MAX_UPCOMING_DAYS
from birthday_bot.permissions import editable_group_id, target_group_id
from birthday_bot.texts import SETTINGS_USAGE, settings_text

router = Router(name="settings")


@router.message(Command("settings"))
async def cmd_settings(message: Message, command: CommandObject, bot: Bot, db: Database, config: Config):
    args = (command.args or "").split()
    if not args:
        settings = await db.get_settings(target_group_id(message.chat, config))
        await message.answer(settings_text(settings))
        return

    group_id = await editable_group_id(message, bot, db, config)
    if group_id is None:
        await message.answer("⛔ Sozlamalarni faqat guruh adminlari va boshqaruvchilari o'zgartira oladi.")
        return

    if len(args) != 2:
        await message.answer(f"❗ {SETTINGS_USAGE}")
        return
    key, value = args[0].lower(), args[1]

    if key == "time":
        at = parse_time(value)
        if at is None:
            await message.answer("❗ Vaqt formati: <code>HH:MM</code>, masalan <code>09:00</code>")
            return
        await db.set_setting(group_id, "notify_time", at)
        await message.answer(f"✅ Tabrik vaqti: <b>{format_time(at)}</b>")

    elif key == "remind":
        if not value.isdigit() or int(value) > MAX_REMIND_DAYS:
            await message.answer(f"❗ 0 dan {MAX_REMIND_DAYS} gacha son kiriting.")
            return
        days = int(value)
        await db.set_setting(group_id, "remind_days", days)
        await message.answer(
            f"✅ Oldindan eslatma: <b>{days} kun oldin</b>" if days
            else "✅ Oldindan eslatma o'chirildi."
        )

    elif key == "upcoming":
        if not value.isdigit() or not 1 <= int(value) <= MAX_UPCOMING_DAYS:
            await message.answer(f"❗ 1 dan {MAX_UPCOMING_DAYS} gacha son kiriting.")
            return
        await db.set_setting(group_id, "upcoming_days", int(value))
        await message.answer(f"✅ /upcoming endi <b>{int(value)} kun</b>ni ko'rsatadi.")

    else:
        await message.answer(f"❗ Noma'lum sozlama.\n\n{SETTINGS_USAGE}")


@router.message(Command("setsticker"))
async def cmd_setsticker(message: Message, command: CommandObject, bot: Bot, db: Database, config: Config):
    group_id = await editable_group_id(message, bot, db, config)
    if group_id is None:
        await message.answer("⛔ Stikerni faqat guruh adminlari va boshqaruvchilari o'zgartira oladi.")
        return

    if (command.args or "").strip().lower() == "off":
        await db.set_setting(group_id, "sticker_file_id", None)
        await message.answer("✅ Tabrik stikeri o'chirildi.")
        return

    replied = message.reply_to_message
    if not replied or not replied.sticker:
        await message.answer(
            "❗ Stikerga reply qilib <code>/setsticker</code> yozing. "
            "O'chirish: <code>/setsticker off</code>"
        )
        return

    await db.set_setting(group_id, "sticker_file_id", replied.sticker.file_id)
    await message.answer("✅ Tabrik stikeri saqlandi 🎉")
