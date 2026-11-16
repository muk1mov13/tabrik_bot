"""
group_settings.py — Guruh sozlamalari buyruqlari: /settings va /setsticker.
"""

from aiogram import Bot, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

import database as db
from permissions import can_edit, get_target_group_id
from utils import parse_time

router = Router()

MAX_REMIND_DAYS = 30
MAX_UPCOMING_DAYS = 60

SETTINGS_USAGE = (
    "Sozlamani o'zgartirish (faqat adminlar):\n"
    "• <code>/settings time 09:00</code> — tabrik vaqti\n"
    f"• <code>/settings remind 3</code> — necha kun oldin eslatish (0 — o'chirish, max {MAX_REMIND_DAYS})\n"
    f"• <code>/settings upcoming 14</code> — /upcoming necha kunni ko'rsatadi (1–{MAX_UPCOMING_DAYS})\n"
    "• stikerga reply qilib <code>/setsticker</code>"
)


def format_settings(settings: dict) -> str:
    remind = settings["remind_days"]
    return (
        "⚙️ <b>Guruh sozlamalari</b>\n\n"
        f"🕗 Tabrik vaqti: <b>{settings['notify_time'].strftime('%H:%M')}</b>\n"
        f"⏰ Oldindan eslatma: <b>{f'{remind} kun oldin' if remind else 'o‘chirilgan'}</b>\n"
        f"🔔 /upcoming: <b>{settings['upcoming_days']} kun</b>\n"
        f"🎨 Stiker: <b>{'bor' if settings['sticker_file_id'] else 'yo‘q'}</b>\n\n"
        + SETTINGS_USAGE
    )


@router.message(Command("settings"))
async def cmd_settings(message: Message, command: CommandObject, bot: Bot):
    args = (command.args or "").split()
    if not args:
        settings = await db.get_settings(get_target_group_id(message.chat))
        await message.answer(format_settings(settings))
        return

    allowed, group_id = await can_edit(message, bot)
    if not allowed:
        await message.answer("⛔ Sozlamalarni faqat guruh adminlari o'zgartira oladi.")
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
        await message.answer(f"✅ Tabrik vaqti: <b>{at.strftime('%H:%M')}</b>")
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
        await message.answer(f"✅ /upcoming endi <b>{value} kun</b>ni ko'rsatadi.")
    else:
        await message.answer(f"❗ Noma'lum sozlama.\n\n{SETTINGS_USAGE}")


@router.message(Command("setsticker"))
async def cmd_setsticker(message: Message, command: CommandObject, bot: Bot):
    allowed, group_id = await can_edit(message, bot)
    if not allowed:
        await message.answer("⛔ Stikerni faqat guruh adminlari o'zgartira oladi.")
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
