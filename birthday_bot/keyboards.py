"""
keyboards.py — Shaxsiy chat menyusi tugmalari va guruhdagi taklif tugmasi.

Callback ma'lumotida group_id bor, lekin unga ishonilmaydi: har bir
bosishda rol qayta tekshiriladi (handlers/ui.py: ensure_role).
"""

from datetime import time
from typing import Optional

from aiogram.filters.callback_data import CallbackData
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    KeyboardButtonRequestUsers,
    ReplyKeyboardMarkup,
)

from birthday_bot.dates import format_time
from birthday_bot.models import Birthday, Group, GroupSettings
from birthday_bot.texts import record_button_text

RECORDS_PAGE_SIZE = 10
TIME_CHOICES = [time(7, 0), time(8, 0), time(9, 0), time(10, 0), time(12, 0)]
REMIND_CHOICES = [0, 1, 3, 7]
CUSTOM_TIME = -1
# request_users so'rovlari: yangi yozuv uchun odam tanlash / mavjud yozuvni bog'lash
PICK_USER_REQUEST = 1
PICK_LINK_REQUEST = 2


class Menu(CallbackData, prefix="m"):
    action: str  # home | add | list | settings | groups | guide
    group_id: int


class PickGroup(CallbackData, prefix="pg"):
    group_id: int


class Cancel(CallbackData, prefix="x"):
    group_id: int


class SaveNew(CallbackData, prefix="sv"):
    pass


class SaveBulk(CallbackData, prefix="sl"):
    pass


class RecordPage(CallbackData, prefix="rp"):
    group_id: int
    page: int


class ListTool(CallbackData, prefix="lt"):
    action: str  # search | export
    group_id: int


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


class SettingsAction(CallbackData, prefix="sa"):
    action: str  # greeting | preview | reset_greeting | sticker | del_sticker | digest
    group_id: int


class RemoveManager(CallbackData, prefix="rm"):
    group_id: int
    user_id: int


class CreateInvite(CallbackData, prefix="iv"):
    group_id: int


class SelfAction(CallbackData, prefix="me"):
    action: str  # add | date | save | del | delyes — faqat o'z yozuvi
    group_id: int


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
    return _kb([InlineKeyboardButton(text="🎂 Tug'ilgan kun qo'shish", url=url)])


def guide_keyboard(bot_username: str, group_id: Optional[int] = None) -> InlineKeyboardMarkup:
    """Yo'riqnoma ostida: botni guruhga qo'shish va (menyudan ochilgan bo'lsa) orqaga."""
    url = f"https://t.me/{bot_username}?startgroup=true"
    return _kb(
        [InlineKeyboardButton(text="➕ Guruhga qo'shish", url=url)],
        [home_button(group_id)] if group_id is not None else [],
    )


def main_menu_keyboard(group_id: int, many_groups: bool) -> InlineKeyboardMarkup:
    rows = [
        [
            _cb("➕ Qo'shish", Menu(action="add", group_id=group_id)),
            _cb("📋 Ro'yxat", Menu(action="list", group_id=group_id)),
        ],
        [
            _cb("⚙️ Sozlamalar", Menu(action="settings", group_id=group_id)),
            _cb("👥 Boshqaruvchilar", Menu(action="managers", group_id=group_id)),
        ],
    ]
    if many_groups:
        rows.append([_cb("🔄 Guruhni almashtirish", Menu(action="groups", group_id=group_id))])
    rows.append([_cb("📖 Yo'riqnoma", Menu(action="guide", group_id=group_id))])
    return _kb(*rows)


def member_menu_keyboard(group_id: int, has_record: bool, many_groups: bool) -> InlineKeyboardMarkup:
    if has_record:
        rows = [
            [_cb("📅 Sanani o'zgartirish", SelfAction(action="date", group_id=group_id))],
            [_cb("🗑 O'chirish", SelfAction(action="del", group_id=group_id))],
        ]
    else:
        rows = [[_cb("🎂 Tug'ilgan kunimni qo'shish", SelfAction(action="add", group_id=group_id))]]
    if many_groups:
        rows.append([_cb("🔄 Guruhni almashtirish", Menu(action="groups", group_id=group_id))])
    rows.append([_cb("📖 Yo'riqnoma", Menu(action="guide", group_id=group_id))])
    return _kb(*rows)


def self_confirm_keyboard(group_id: int) -> InlineKeyboardMarkup:
    return _kb([
        _cb("✅ Saqlash", SelfAction(action="save", group_id=group_id)),
        _cb("❌ Bekor qilish", Cancel(group_id=group_id)),
    ])


def self_delete_keyboard(group_id: int) -> InlineKeyboardMarkup:
    return _kb([
        _cb("Ha, o'chirish", SelfAction(action="delyes", group_id=group_id)),
        _cb("Yo'q", Menu(action="home", group_id=group_id)),
    ])


def managers_keyboard(
    group_id: int, managers: list[tuple[int, str]], can_remove: bool
) -> InlineKeyboardMarkup:
    rows = []
    if can_remove:
        rows = [
            [_cb(f"🗑 {name}", RemoveManager(group_id=group_id, user_id=user_id))]
            for user_id, name in managers
        ]
    invite = [_cb("🔗 Taklif havolasi", CreateInvite(group_id=group_id))]
    return _kb(*rows, invite, [home_button(group_id)])


def invite_keyboard(group_id: int) -> InlineKeyboardMarkup:
    return _kb([
        _cb("⬅️ Orqaga", Menu(action="managers", group_id=group_id)),
        home_button(group_id),
    ])


def groups_keyboard(groups: list[Group]) -> InlineKeyboardMarkup:
    return _kb(*[[_cb(g.title or str(g.group_id), PickGroup(group_id=g.group_id))] for g in groups])


def pick_user_keyboard(request_id: int = PICK_USER_REQUEST) -> ReplyKeyboardMarkup:
    """Odamni kontaktlardan tanlash — Telegram buni faqat oddiy klaviaturada beradi."""
    button = KeyboardButton(
        text="👤 Telegram'dan tanlash",
        request_users=KeyboardButtonRequestUsers(
            request_id=request_id, user_is_bot=False, max_quantity=1, request_name=True
        ),
    )
    return ReplyKeyboardMarkup(keyboard=[[button]], resize_keyboard=True, one_time_keyboard=True)


def cancel_keyboard(group_id: int) -> InlineKeyboardMarkup:
    return _kb([_cb("❌ Bekor qilish", Cancel(group_id=group_id))])


def add_confirm_keyboard(group_id: int) -> InlineKeyboardMarkup:
    return _kb([_cb("✅ Saqlash", SaveNew()), _cb("❌ Bekor qilish", Cancel(group_id=group_id))])


def bulk_confirm_keyboard(group_id: int, count: int) -> InlineKeyboardMarkup:
    return _kb(
        [_cb(f"✅ Hammasini saqlash ({count})", SaveBulk())],
        [_cb("❌ Bekor qilish", Cancel(group_id=group_id))],
    )


def after_add_keyboard(group_id: int) -> InlineKeyboardMarkup:
    return _kb([_cb("➕ Yana qo'shish", Menu(action="add", group_id=group_id)), home_button(group_id)])


def empty_list_keyboard(group_id: int) -> InlineKeyboardMarkup:
    return _kb([_cb("➕ Qo'shish", Menu(action="add", group_id=group_id)), home_button(group_id)])


def records_keyboard(
    group_id: int, birthdays: list[Birthday], page: int, pages: int
) -> InlineKeyboardMarkup:
    nav = []
    if page > 0:
        nav.append(_cb("⬅️", RecordPage(group_id=group_id, page=page - 1)))
    if page < pages - 1:
        nav.append(_cb("➡️", RecordPage(group_id=group_id, page=page + 1)))
    tools = [
        _cb("🔎 Qidirish", ListTool(action="search", group_id=group_id)),
        _cb("📤 Yuklab olish", ListTool(action="export", group_id=group_id)),
    ]
    return _kb(*_record_rows(group_id, birthdays, page), nav, tools, [home_button(group_id)])


def _record_rows(group_id: int, birthdays: list[Birthday], page: int) -> list[list[InlineKeyboardButton]]:
    return [
        [_cb(record_button_text(b), RecordAction(action="show", group_id=group_id, record_id=b.id, page=page))]
        for b in birthdays
    ]


def search_results_keyboard(group_id: int, birthdays: list[Birthday]) -> InlineKeyboardMarkup:
    again = _cb("🔎 Yana qidirish", ListTool(action="search", group_id=group_id))
    return _kb(*_record_rows(group_id, birthdays, 0), [again, home_button(group_id)])


def record_keyboard(group_id: int, record_id: int, page: int) -> InlineKeyboardMarkup:
    def act(action: str) -> RecordAction:
        return RecordAction(action=action, group_id=group_id, record_id=record_id, page=page)

    return _kb(
        [_cb("✏️ Ismni o'zgartirish", act("name"))],
        [_cb("📅 Sanani o'zgartirish", act("date"))],
        [_cb("👤 Telegram'dan belgilash", act("link"))],
        [_cb("🗑 O'chirish", act("del"))],
        [_cb("⬅️ Orqaga", RecordPage(group_id=group_id, page=page))],
    )


def confirm_delete_keyboard(group_id: int, record_id: int, page: int) -> InlineKeyboardMarkup:
    def act(action: str) -> RecordAction:
        return RecordAction(action=action, group_id=group_id, record_id=record_id, page=page)

    return _kb([_cb("Ha, o'chirish", act("delyes")), _cb("Yo'q", act("show"))])


def settings_keyboard(
    group_id: int, s: GroupSettings, digest_enabled: bool = True
) -> InlineKeyboardMarkup:
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
    def act(action: str) -> SettingsAction:
        return SettingsAction(action=action, group_id=group_id)

    look = [_cb("✍️ Tabrik matni", act("greeting")), _cb("👁 Ko'rish", act("preview"))]
    extras = [_cb("🎨 Stiker", act("sticker"))]
    if s.greeting_template:
        extras.append(_cb("↩️ Standart matn", act("reset_greeting")))
    if s.sticker_file_id:
        extras.append(_cb("🗑 Stikerni o'chirish", act("del_sticker")))
    # Shaxsiy sozlama: faqat shu boshqaruvchining ertalabki xabari
    digest_label = "🔔 Ertalabki xabar: yoqilgan" if digest_enabled else "🔕 Ertalabki xabar: o'chirilgan"
    return _kb(
        times[:3],
        [*times[3:], _cb(_mark(custom_label, custom), SetTime(group_id=group_id, minutes=CUSTOM_TIME))],
        remind,
        look,
        extras,
        [_cb(digest_label, act("digest"))],
        [home_button(group_id)],
    )
