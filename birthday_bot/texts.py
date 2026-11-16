"""
texts.py — Foydalanuvchiga ko'rinadigan barcha matnlar va ularni yasash.

Bot HTML parse mode'da ishlaydi: foydalanuvchi kiritgan har qanday matn
mention() yoki escape() orqali o'tishi shart.
"""

import random
from datetime import date
from html import escape
from typing import Optional, Sequence

from birthday_bot.dates import calc_age, format_time, next_birthday
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
    "• <code>/menu</code> — tugmali menyu: qo'shish, ro'yxat, sozlamalar (eng oson yo'l)\n"
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

MANAGER_USAGE = (
    "Boshqaruvchi tayinlash: odamning xabariga reply qilib <code>/manager</code> yozing.\n"
    "Olib tashlash: reply qilib <code>/manager off</code>."
)
MANAGER_ADMIN_ONLY_TEXT = "⛔ Boshqaruvchilarni faqat guruh adminlari tayinlaydi."
GROUP_UNAVAILABLE_TEXT = (
    "Bot bu guruhda topilmadi yoki guruh o'zgargan. "
    "Guruhda /menu yozing va yangi tugmani bosing."
)
NOT_IN_GROUP_TEXT = (
    "⛔ Siz bu guruh a'zosi emassiz. Guruhga qo'shilgach, tugmani qayta bosing."
)
ASK_OWN_DATE_TEXT = (
    "Tug'ilgan kuningiz qachon? Masalan: <code>15.03</code> yoki "
    "<code>15.03.1990</code> (yili ixtiyoriy)"
)
OWN_SAVED_TEXT = "✅ Saqlandi! U kuni guruhda tabriklayman 🎉"
OWN_DELETED_TEXT = "🗑 Tug'ilgan kuningiz o'chirildi."
OWN_DELETE_CONFIRM_TEXT = "🗑 Tug'ilgan kuningiz ro'yxatdan o'chirilsinmi?"
# Callback alert — oddiy matn (HTML emas), 200 belgigacha
NOT_ADMIN_ALERT = "⛔ Bu amal faqat guruh adminlari va boshqaruvchilariga ruxsat etilgan."
STALE_TEXT = "Bu menyu eskirgan. /menu ni bosing."
NO_GROUPS_TEXT = (
    "Hali birorta guruhingiz ulanmagan.\n\n"
    "1. Meni oila guruhingizga qo'shing.\n"
    "2. Guruhda <b>🎂 Tug'ilgan kun qo'shish</b> tugmasini bosing "
    "(tugma ko'rinmasa, guruhda /menu yozing).\n\n"
    "Botni guruhga qo'shgan odam va guruh adminlari hamma tug'ilgan kunlarni "
    "boshqaradi, qolganlar o'z tug'ilgan kunini qo'sha oladi."
)
CHOOSE_GROUP_TEXT = "Qaysi guruh bilan ishlaymiz?"
ASK_NAME_TEXT = "Kimning tug'ilgan kuni? Ismini yozing.\nMasalan: <i>Karim aka</i>"
ASK_DATE_TEXT = (
    "Sanasi? Masalan: <code>15.03</code> yoki <code>15.03.1980</code> (yili ixtiyoriy)"
)
PICK_USER_HINT_TEXT = (
    "Yoki odamni pastdagi tugma bilan Telegram'dan tanlang 👇 — "
    "shunda tabrikda u belgilanadi."
)
CANCELLED_TEXT = "Bekor qilindi."
ASK_NEW_NAME_TEXT ="Yangi ismni yozing:"
ASK_NEW_DATE_TEXT = "Yangi sanani yozing: <code>15.03</code> yoki <code>15.03.1980</code>"
ASK_TIME_TEXT = "Tabrik vaqtini yozing, masalan <code>09:30</code>"
EMPTY_LIST_TEXT = "Hali hech kim qo'shilmagan."
RECORD_GONE_TEXT = "Bu yozuv endi yo'q."
SAVED_TEXT = "✏️ Saqlandi."


def mention(name: str, user_id: Optional[int] = None) -> str:
    """Ism: Telegram user bog'langan bo'lsa — uni belgilaydigan havola."""
    safe = escape(name)
    if user_id:
        return f'<a href="tg://user?id={user_id}">{safe}</a>'
    return safe


def welcome_text(adder_name: Optional[str] = None, adder_id: Optional[int] = None) -> str:
    text = (
        "👋 Salom! Men shu guruhdagilarning tug'ilgan kunini eslab, "
        "o'z vaqtida tabriklayman 🎉\n\n"
    )
    if adder_name:
        text += f"Meni {mention(adder_name, adder_id)} qo'shdi — u tug'ilgan kunlarni boshqaradi.\n"
    return text + (
        "Har kim o'z tug'ilgan kunini pastdagi tugma orqali qo'sha oladi.\n"
        "Hamma uchun: /upcoming — yaqin tug'ilgan kunlar, /list — ro'yxat."
    )


def manager_added_text(name: str, user_id: int) -> str:
    return (
        f"✅ {mention(name, user_id)} endi tug'ilgan kunlarni boshqaradi. "
        "Botga shaxsiy yozib /menu ni bosishi kifoya."
    )


def manager_removed_text(name: str, user_id: int) -> str:
    return f"✅ {mention(name, user_id)} endi boshqaruvchi emas."


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


def menu_text(title: str) -> str:
    return f"🏠 <b>{escape(title) or 'Guruh'}</b>\n\nNima qilamiz?"


def member_menu_text(title: str, own: Optional[Birthday], today: date) -> str:
    header = f"🏠 <b>{escape(title) or 'Guruh'}</b>\n\n"
    if own is None:
        return header + "Tug'ilgan kuningizni qo'shing — u kuni guruhda tabriklayman 🎉"
    return header + "Sizning yozuvingiz:\n" + record_card(own, today)


def managers_text(managers: list[tuple[int, str]], is_admin: bool) -> str:
    lines = ["👥 <b>Boshqaruvchilar</b>\n"]
    if managers:
        lines.extend(f"• {mention(name, user_id)}" for user_id, name in managers)
    else:
        lines.append("Hali boshqaruvchi yo'q.")
    lines.append("\nGuruh adminlari ham tug'ilgan kunlarni boshqaradi.")
    if is_admin:
        lines.append(MANAGER_USAGE)
    return "\n".join(lines)


def name_accepted_text(name: str, user_id: Optional[int] = None) -> str:
    return f"👤 <b>{mention(name, user_id)}</b>"


def add_preview(
    name: str, day: int, month: int, year: Optional[int], duplicates: Sequence[Birthday] = ()
) -> str:
    text = f"Tekshiring:\n<b>{escape(name)}</b> — {format_date(day, month, year)}\n\n"
    if not duplicates:
        return text + "Saqlaymizmi?"
    existing = ", ".join(
        f"{mention(b.name, b.user_id)} — {format_date(b.day, b.month, b.year)}" for b in duplicates
    )
    return text + f"⚠️ Ro'yxatda allaqachon bor: {existing}. Baribir saqlaymizmi?"


def added_text(name: str, day: int, month: int, year: Optional[int]) -> str:
    return f"✅ Qo'shildi: <b>{escape(name)}</b> — {format_date(day, month, year)}"


def deleted_text(name: str) -> str:
    return f"🗑 O'chirildi: <b>{escape(name)}</b>"


def records_title(total: int) -> str:
    return f"📋 <b>Tug'ilgan kunlar</b> ({total} ta)\nKimnidir tanlang:"


def record_button_text(b: Birthday) -> str:
    # Tugma matni HTML sifatida o'qilmaydi — escape kerak emas
    return f"{b.name} — {format_date(b.day, b.month)}"


def record_card(b: Birthday, today: date) -> str:
    nxt = next_birthday(b.day, b.month, today)
    when = "bugun" if nxt == today else f"{(nxt - today).days} kundan keyin"
    text = (
        f"👤 <b>{mention(b.name, b.user_id)}</b>\n"
        f"📅 {format_date(b.day, b.month, b.year)}\n"
        f"⏳ Keyingi tug'ilgan kun: {when}"
    )
    if b.year:
        text += f", {calc_age(b.year, nxt)} yoshga to'ladi"
    return text


def confirm_delete_text(b: Birthday) -> str:
    return f"🗑 <b>{escape(b.name)}</b> rostdan o'chirilsinmi?"


def settings_menu_text(s: GroupSettings) -> str:
    remind = f"{s.remind_days} kun oldin" if s.remind_days else "o'chirilgan"
    return (
        "⚙️ <b>Sozlamalar</b>\n\n"
        f"🕗 Tabrik vaqti: <b>{format_time(s.notify_time)}</b>\n"
        f"⏰ Oldindan eslatma: <b>{remind}</b>\n\n"
        "Yuqorida — tabrik vaqti, pastda — necha kun oldin eslatish."
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
