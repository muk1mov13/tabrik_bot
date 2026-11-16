"""
texts.py — Foydalanuvchiga ko'rinadigan barcha matnlar va ularni yasash.

Bot HTML parse mode'da ishlaydi: foydalanuvchi kiritgan har qanday matn
mention() yoki escape() orqali o'tishi shart.
"""

import random
from datetime import date
from html import escape
from typing import Optional

from birthday_bot.dates import calc_age, format_time
from birthday_bot.models import MAX_REMIND_DAYS, MAX_UPCOMING_DAYS, Birthday, GroupSettings, Upcoming

# Telegram xabar chegarasi 4096 belgi — biroz zaxira qoldiramiz
MESSAGE_LIMIT = 4000

MONTH_NAMES = [
    "", "Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun",
    "Iyul", "Avgust", "Sentabr", "Oktabr", "Noyabr", "Dekabr",
]

GREETINGS = [
    "🎉 Bugun {name} ning tug'ilgan kuni! Uni tabriklashni unutmang 🎂",
    "🎂 E'tibor bering — bugun {name} tug'ilgan kunini nishonlamoqda! 🥳",
    "🎈 Bugungi kun {name} uchun alohida — tug'ilgan kuni! Tabriklaymiz 🎁",
]

HELP_TEXT = (
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

SETTINGS_USAGE = (
    "Sozlamani o'zgartirish (faqat adminlar):\n"
    "• <code>/settings time 09:00</code> — tabrik vaqti\n"
    f"• <code>/settings remind 3</code> — necha kun oldin eslatish "
    f"(0 — o'chirish, max {MAX_REMIND_DAYS})\n"
    f"• <code>/settings upcoming 14</code> — /upcoming necha kunni ko'rsatadi "
    f"(1–{MAX_UPCOMING_DAYS})\n"
    "• stikerga reply qilib <code>/setsticker</code>"
)


def mention(name: str, user_id: Optional[int] = None) -> str:
    """Ism: Telegram user bog'langan bo'lsa — uni belgilaydigan havola."""
    safe = escape(name)
    if user_id:
        return f'<a href="tg://user?id={user_id}">{safe}</a>'
    return safe


def format_date(day: int, month: int, year: Optional[int] = None) -> str:
    return f"{day} {MONTH_NAMES[month]}" + (f" {year}" if year else "")


def birthday_line(b: Birthday) -> str:
    year_part = f" ({b.year})" if b.year else ""
    return f"• [{b.id}] {mention(b.name, b.user_id)} — {b.day} {MONTH_NAMES[b.month]}{year_part}"


def upcoming_line(item: Upcoming) -> str:
    b = item.birthday
    when = "bugun" if item.days_left == 0 else f"{item.days_left} kundan keyin"
    return f"• {mention(b.name, b.user_id)} — {format_date(item.date.day, item.date.month)} ({when})"


def greeting(b: Birthday, on_date: date, rng: random.Random = random) -> str:
    text = rng.choice(GREETINGS).format(name=f"<b>{mention(b.name, b.user_id)}</b>")
    if b.year:
        text += f"\n🎊 U bugun {calc_age(b.year, on_date)} yoshga to'ldi!"
    return text


def reminder(item: Upcoming) -> str:
    b = item.birthday
    text = (
        f"⏰ {item.days_left} kundan keyin ({format_date(item.date.day, item.date.month)}) — "
        f"<b>{mention(b.name, b.user_id)}</b> ning tug'ilgan kuni!"
    )
    if b.year:
        text += f" U {calc_age(b.year, item.date)} yoshga to'ladi."
    return text + "\nSovg'a tayyorlashni unutmang 🎁"


def settings_text(s: GroupSettings) -> str:
    remind = f"{s.remind_days} kun oldin" if s.remind_days else "o'chirilgan"
    sticker = "bor" if s.sticker_file_id else "yo'q"
    return (
        "⚙️ <b>Guruh sozlamalari</b>\n\n"
        f"🕗 Tabrik vaqti: <b>{format_time(s.notify_time)}</b>\n"
        f"⏰ Oldindan eslatma: <b>{remind}</b>\n"
        f"🔔 /upcoming: <b>{s.upcoming_days} kun</b>\n"
        f"🎨 Stiker: <b>{sticker}</b>\n\n"
        + SETTINGS_USAGE
    )


def split_messages(lines: list[str], limit: int = MESSAGE_LIMIT) -> list[str]:
    """Qatorlarni Telegram chegarasidan oshmaydigan xabarlarga bo'ladi."""
    chunks: list[str] = []
    chunk = ""
    for line in lines:
        if chunk and len(chunk) + len(line) + 1 > limit:
            chunks.append(chunk)
            chunk = ""
        chunk = f"{chunk}\n{line}" if chunk else line
    if chunk:
        chunks.append(chunk)
    return chunks
