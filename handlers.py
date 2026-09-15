"""
handlers.py — Bot buyruqlarini qayta ishlovchi funksiyalar.
"""

import os
import re
from datetime import date

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message

import database as db

router = Router()

MONTH_NAMES = [
    "", "Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun",
    "Iyul", "Avgust", "Sentabr", "Oktabr", "Noyabr", "Dekabr",
]

# /add Ism Familiya 15.03  yoki  /add Ism 15.03.1998
ADD_PATTERN = re.compile(
    r"^/add\s+(?P<name>.+?)\s+(?P<day>\d{1,2})\.(?P<month>\d{1,2})(?:\.(?P<year>\d{4}))?$"
)


def get_target_group_id(message: Message) -> int:
    """
    Agar shaxsiy chatdan yozilgan bo'lsa va DEFAULT_GROUP_ID mavjud bo'lsa,
    o'sha guruh ID'sini qaytaradi. Aks holda hozirgi chat ID'sini qaytaradi.
    """
    default_gid = os.getenv("DEFAULT_GROUP_ID")
    if message.chat.type == "private" and default_gid:
        try:
            return int(default_gid)
        except ValueError:
            pass
    return message.chat.id


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
        "Botni guruhga qo'shing va admin qiling — u har kuni ertalab "
        "tug'ilgan kuni bor odamni eslatib turadi 🎉"
    )
    await message.answer(text)


@router.message(Command("add"))
async def cmd_add(message: Message):
    match = ADD_PATTERN.match(message.text.strip())
    if not match:
        await message.answer(
            "❗ Format noto'g'ri. Namuna:\n"
            "<code>/add Ism 15.03</code>\n"
            "<code>/add Ism 15.03.1998</code>"
        )
        return

    name = match.group("name").strip()
    day = int(match.group("day"))
    month = int(match.group("month"))
    year = int(match.group("year")) if match.group("year") else None

    if not (1 <= day <= 31 and 1 <= month <= 12):
        await message.answer("❗ Kun yoki oy noto'g'ri kiritildi.")
        return

    target_group_id = get_target_group_id(message)
    record_id = await db.add_birthday(
        group_id=target_group_id,
        name=name,
        day=day,
        month=month,
        year=year,
        added_by=message.from_user.id,
    )
    await message.answer(
        f"✅ Qo'shildi: <b>{name}</b> — {day} {MONTH_NAMES[month]}"
        + (f" {year}" if year else "")
        + f"\n(ID: {record_id})"
    )


@router.message(Command("list"))
async def cmd_list(message: Message):
    target_group_id = get_target_group_id(message)
    rows = await db.list_birthdays(target_group_id)
    if not rows:
        await message.answer("Bu guruhda hali birorta tug'ilgan kun qo'shilmagan.")
        return

    lines = ["📋 <b>Saqlangan tug'ilgan kunlar:</b>\n"]
    for row in rows:
        year_part = f" ({row['year']})" if row["year"] else ""
        lines.append(
            f"• [{row['id']}] {row['name']} — {row['day']} {MONTH_NAMES[row['month']]}{year_part}"
        )
    await message.answer("\n".join(lines))


@router.message(Command("upcoming"))
async def cmd_upcoming(message: Message):
    target_group_id = get_target_group_id(message)
    upcoming = await db.get_upcoming(target_group_id, days_ahead=7)
    if not upcoming:
        await message.answer("Keyingi 7 kun ichida tug'ilgan kun yo'q.")
        return

    lines = ["🔔 <b>Yaqin kunlardagi tug'ilgan kunlar:</b>\n"]
    for item in upcoming:
        row = item["row"]
        days_left = item["days_left"]
        when = "bugun" if days_left == 0 else f"{days_left} kundan keyin"
        lines.append(f"• {row['name']} — {row['day']} {MONTH_NAMES[row['month']]} ({when})")
    await message.answer("\n".join(lines))


@router.message(Command("remove"))
async def cmd_remove(message: Message):
    parts = message.text.strip().split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("❗ Namuna: <code>/remove 3</code> (ID ni /list dan oling)")
        return

    record_id = int(parts[1])
    target_group_id = get_target_group_id(message)
    success = await db.remove_birthday(target_group_id, record_id)
    if success:
        await message.answer("🗑 O'chirildi.")
    else:
        await message.answer("Bunday ID topilmadi.")

