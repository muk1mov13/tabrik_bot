"""
settings_menu.py — Sozlamalar tugmalari: tabrik vaqti va oldindan eslatma.
"""

from datetime import time

from aiogram import Bot, F, Router
from aiogram.enums import ChatType
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from birthday_bot.database import Database
from birthday_bot.dates import parse_time
from birthday_bot.handlers.ui import TEXT_INPUT, ensure_manager, show
from birthday_bot.keyboards import CUSTOM_TIME, Menu, SetRemind, SetTime, cancel_keyboard, settings_keyboard
from birthday_bot.models import MAX_REMIND_DAYS
from birthday_bot.texts import ASK_TIME_TEXT, STALE_TEXT, settings_menu_text

router = Router(name="settings_menu")
router.message.filter(F.chat.type == ChatType.PRIVATE)


class SettingsInput(StatesGroup):
    time = State()


async def settings_view(db: Database, group_id: int) -> tuple[str, InlineKeyboardMarkup]:
    settings = await db.get_settings(group_id)
    return settings_menu_text(settings), settings_keyboard(group_id, settings)


@router.callback_query(Menu.filter(F.action == "settings"))
async def cb_settings(callback: CallbackQuery, callback_data: Menu, bot: Bot, db: Database):
    if await ensure_manager(callback, bot, db, callback_data.group_id):
        text, keyboard = await settings_view(db, callback_data.group_id)
        await show(callback, text, keyboard)


@router.callback_query(SetTime.filter())
async def cb_set_time(
    callback: CallbackQuery, callback_data: SetTime, bot: Bot, db: Database, state: FSMContext
):
    group_id, minutes = callback_data.group_id, callback_data.minutes
    if not await ensure_manager(callback, bot, db, group_id):
        return
    if minutes == CUSTOM_TIME:
        await state.set_state(SettingsInput.time)
        await state.set_data({"group_id": group_id})
        await show(callback, ASK_TIME_TEXT, cancel_keyboard(group_id))
        return
    if not 0 <= minutes < 24 * 60:
        await callback.answer(STALE_TEXT, show_alert=True)
        return
    await db.set_setting(group_id, "notify_time", time(*divmod(minutes, 60)))
    text, keyboard = await settings_view(db, group_id)
    await show(callback, text, keyboard)


@router.callback_query(SetRemind.filter())
async def cb_set_remind(callback: CallbackQuery, callback_data: SetRemind, bot: Bot, db: Database):
    group_id, days = callback_data.group_id, callback_data.days
    if not await ensure_manager(callback, bot, db, group_id):
        return
    if not 0 <= days <= MAX_REMIND_DAYS:
        await callback.answer(STALE_TEXT, show_alert=True)
        return
    await db.set_setting(group_id, "remind_days", days)
    text, keyboard = await settings_view(db, group_id)
    await show(callback, text, keyboard)


@router.message(SettingsInput.time, TEXT_INPUT)
async def got_time(message: Message, bot: Bot, db: Database, state: FSMContext):
    group_id = (await state.get_data())["group_id"]
    at = parse_time(message.text)
    if at is None:
        await message.answer(
            f"❗ Vaqt formati noto'g'ri.\n\n{ASK_TIME_TEXT}", reply_markup=cancel_keyboard(group_id)
        )
        return
    await state.clear()
    if not await ensure_manager(message, bot, db, group_id):
        return
    await db.set_setting(group_id, "notify_time", at)
    text, keyboard = await settings_view(db, group_id)
    await message.answer(text, reply_markup=keyboard)
