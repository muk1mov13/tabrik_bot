"""
keyboards.py — Shaxsiy chat menyusi tugmalari va guruhdagi taklif tugmasi.

Callback ma'lumotida group_id bor, lekin unga ishonilmaydi: har bir
bosishda adminlik qayta tekshiriladi (handlers/ui.py: ensure_admin).
"""

from datetime import time

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from birthday_bot.dates import format_time
from birthday_bot.models import Birthday, Group, GroupSettings
from birthday_bot.texts import record_button_text

RECORDS_PAGE_SIZE = 10
TIME_CHOICES = [time(7, 0), time(8, 0), time(9, 0), time(10, 0), time(12, 0)]
REMIND_CHOICES = [0, 1, 3, 7]
CUSTOM_TIME = -1


class Menu(CallbackData, prefix="m"):
    action: str  # home | add | list | settings | groups
    group_id: int


class PickGroup(CallbackData, prefix="pg"):
    group_id: int


class Cancel(CallbackData, prefix="x"):
    group_id: int


class SaveNew(CallbackData, prefix="sv"):
    pass


class RecordPage(CallbackData, prefix="rp"):
    group_id: int
    page: int


class RecordAction(CallbackData, prefix="r"):
    action: str  # show | name | date | del | delyes
    group_id: int
    record_id: int
    page: int = 0


class SetTime(CallbackData, prefix="st"):
    group_id: int
    minutes: int  # kun boshidan daqiqalar; CUSTOM_TIME — qo'lda kiritish


class SetRemind(CallbackData, prefix="sr"):
    group_id: int
    days: int


def _kb(*rows: list[InlineKeyboardButton]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[row for row in rows if row])


def _cb(text: str, data: CallbackData) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data.pack())


def _mark(text: str, selected: bool) -> str:
    return f"✅ {text}" if selected else text


def home_button(group_id: int) -> InlineKeyboardButton:
    return _cb("🏠 Menyu", Menu(action="home", group_id=group_id))


def group_invite_keyboard(bot_username: str, group_id: int) -> InlineKeyboardMarkup:
    url = f"https://t.me/{bot_username}?start=g_{group_id}"
    return _kb([InlineKeyboardButton(text="➕ Tug'ilgan kun qo'shish", url=url)])


def main_menu_keyboard(group_id: int, many_groups: bool) -> InlineKeyboardMarkup:
    rows = [
        [
            _cb("➕ Qo'shish", Menu(action="add", group_id=group_id)),
            _cb("📋 Ro'yxat", Menu(action="list", group_id=group_id)),
        ],
        [_cb("⚙️ Sozlamalar", Menu(action="settings", group_id=group_id))],
    ]
    if many_groups:
        rows.append([_cb("🔄 Guruhni almashtirish", Menu(action="groups", group_id=group_id))])
    return _kb(*rows)


def groups_keyboard(groups: list[Group]) -> InlineKeyboardMarkup:
    return _kb(*[[_cb(g.title or str(g.group_id), PickGroup(group_id=g.group_id))] for g in groups])


def cancel_keyboard(group_id: int) -> InlineKeyboardMarkup:
    return _kb([_cb("❌ Bekor qilish", Cancel(group_id=group_id))])


def add_confirm_keyboard(group_id: int) -> InlineKeyboardMarkup:
    return _kb([_cb("✅ Saqlash", SaveNew()), _cb("❌ Bekor qilish", Cancel(group_id=group_id))])


def after_add_keyboard(group_id: int) -> InlineKeyboardMarkup:
    return _kb([_cb("➕ Yana qo'shish", Menu(action="add", group_id=group_id)), home_button(group_id)])


def empty_list_keyboard(group_id: int) -> InlineKeyboardMarkup:
    return _kb([_cb("➕ Qo'shish", Menu(action="add", group_id=group_id)), home_button(group_id)])


def records_keyboard(
    group_id: int, birthdays: list[Birthday], page: int, pages: int
) -> InlineKeyboardMarkup:
    rows = [
        [_cb(record_button_text(b), RecordAction(action="show", group_id=group_id, record_id=b.id, page=page))]
        for b in birthdays
    ]
    nav = []
    if page > 0:
        nav.append(_cb("⬅️", RecordPage(group_id=group_id, page=page - 1)))
    if page < pages - 1:
        nav.append(_cb("➡️", RecordPage(group_id=group_id, page=page + 1)))
    return _kb(*rows, nav, [home_button(group_id)])


def record_keyboard(group_id: int, record_id: int, page: int) -> InlineKeyboardMarkup:
    def act(action: str) -> RecordAction:
        return RecordAction(action=action, group_id=group_id, record_id=record_id, page=page)

    return _kb(
        [_cb("✏️ Ismni o'zgartirish", act("name"))],
        [_cb("📅 Sanani o'zgartirish", act("date"))],
        [_cb("🗑 O'chirish", act("del"))],
        [_cb("⬅️ Orqaga", RecordPage(group_id=group_id, page=page))],
    )


def confirm_delete_keyboard(group_id: int, record_id: int, page: int) -> InlineKeyboardMarkup:
    def act(action: str) -> RecordAction:
        return RecordAction(action=action, group_id=group_id, record_id=record_id, page=page)

    return _kb([_cb("Ha, o'chirish", act("delyes")), _cb("Yo'q", act("show"))])


def settings_keyboard(group_id: int, s: GroupSettings) -> InlineKeyboardMarkup:
    times = [
        _cb(_mark(format_time(t), t == s.notify_time),
            SetTime(group_id=group_id, minutes=t.hour * 60 + t.minute))
        for t in TIME_CHOICES
    ]
    custom = s.notify_time not in TIME_CHOICES
    custom_label = "✍️ Boshqa vaqt" + (f" ({format_time(s.notify_time)})" if custom else "")
    remind = [
        _cb(_mark("🔕 O'chiq" if d == 0 else f"{d} kun", d == s.remind_days),
            SetRemind(group_id=group_id, days=d))
        for d in REMIND_CHOICES
    ]
    return _kb(
        times[:3],
        [*times[3:], _cb(_mark(custom_label, custom), SetTime(group_id=group_id, minutes=CUSTOM_TIME))],
        remind,
        [home_button(group_id)],
    )
