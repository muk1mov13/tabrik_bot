"""
settings_menu.py — Sozlamalar tugmalari: tabrik vaqti, oldindan eslatma,
guruhning o'z tabrik matni (ko'rish bilan) va stiker.
"""

from datetime import time

from aiogram import Bot, F, Router
from aiogram.enums import ChatType
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from birthday_bot.config import Config
from birthday_bot.database import Database
from birthday_bot.dates import now, parse_time
from birthday_bot.handlers.ui import TEXT_INPUT, ensure_manager, show
from birthday_bot.keyboards import (
    CUSTOM_TIME,
    Menu,
    SetRemind,
    SetTime,
    SettingsAction,
    cancel_keyboard,
    settings_keyboard,
)
from birthday_bot.models import MAX_REMIND_DAYS, Birthday
from birthday_bot.parsing import ParseError, parse_greeting_template
from birthday_bot.texts import (
    ASK_GREETING_TEXT,
    ASK_STICKER_TEXT,
    ASK_TIME_TEXT,
    NOT_A_STICKER_TEXT,
    PREVIEW_HEADER,
    STALE_TEXT,
    greeting,
    settings_menu_text,
)

router = Router(name="settings_menu")
router.message.filter(F.chat.type == ChatType.PRIVATE)

# "👁 Ko'rish" uchun namunaviy odam
PREVIEW_NAME, PREVIEW_AGE = "Karim aka", 50


class SettingsInput(StatesGroup):
    time = State()
    greeting = State()
    sticker = State()


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


@router.callback_query(SettingsAction.filter())
async def cb_settings_action(
    callback: CallbackQuery,
    callback_data: SettingsAction,
    bot: Bot,
    db: Database,
    config: Config,
    state: FSMContext,
):
    group_id, action = callback_data.group_id, callback_data.action
    if not await ensure_manager(callback, bot, db, group_id):
        return

    if action in ("greeting", "sticker"):
        await state.set_state(SettingsInput.greeting if action == "greeting" else SettingsInput.sticker)
        await state.set_data({"group_id": group_id})
        prompt = ASK_GREETING_TEXT if action == "greeting" else ASK_STICKER_TEXT
        await show(callback, prompt, cancel_keyboard(group_id))
        return

    if action == "preview":
        await _send_preview(callback, bot, db, config, group_id)
        return

    if action == "reset_greeting":
        await db.set_setting(group_id, "greeting_template", None)
    elif action == "del_sticker":
        await db.set_setting(group_id, "sticker_file_id", None)
    else:
        await callback.answer(STALE_TEXT, show_alert=True)
        return
    text, keyboard = await settings_view(db, group_id)
    await show(callback, text, keyboard)


async def _send_preview(
    callback: CallbackQuery, bot: Bot, db: Database, config: Config, group_id: int
):
    """Tabrik guruhda qanday ko'rinishini shaxsiy chatga yuboradi, keyin sozlamalar menyusi."""
    settings = await db.get_settings(group_id)
    today = now(config.timezone).date()
    sample = Birthday(
        id=0, group_id=group_id, name=PREVIEW_NAME,
        day=today.day, month=today.month, year=today.year - PREVIEW_AGE,
    )
    chat_id = callback.from_user.id
    text = greeting(sample, today, template=settings.greeting_template)
    await bot.send_message(chat_id, f"{PREVIEW_HEADER}\n\n{text}")
    if settings.sticker_file_id:
        try:
            await bot.send_sticker(chat_id, settings.sticker_file_id)
        except TelegramAPIError:
            pass  # stiker o'chirilgan bo'lishi mumkin — ko'rish uchun muhim emas
    menu_text, keyboard = await settings_view(db, group_id)
    await bot.send_message(chat_id, menu_text, reply_markup=keyboard)
    await callback.answer()


@router.message(SettingsInput.time, TEXT_INPUT)
async def got_time(message: Message, bot: Bot, db: Database, state: FSMContext):
    group_id = (await state.get_data())["group_id"]
    at = parse_time(message.text)
    if at is None:
        await message.answer(
            f"❗ Vaqt formati noto'g'ri.\n\n{ASK_TIME_TEXT}", reply_markup=cancel_keyboard(group_id)
        )
        return
    await _save_and_show(message, bot, db, state, group_id, "notify_time", at)


@router.message(SettingsInput.greeting, TEXT_INPUT)
async def got_greeting(message: Message, bot: Bot, db: Database, state: FSMContext):
    group_id = (await state.get_data())["group_id"]
    try:
        template = parse_greeting_template(message.text)
    except ParseError as exc:
        await message.answer(f"❗ {exc}\n\n{ASK_GREETING_TEXT}", reply_markup=cancel_keyboard(group_id))
        return
    await _save_and_show(message, bot, db, state, group_id, "greeting_template", template)


@router.message(SettingsInput.sticker, F.sticker)
async def got_sticker(message: Message, bot: Bot, db: Database, state: FSMContext):
    group_id = (await state.get_data())["group_id"]
    await _save_and_show(message, bot, db, state, group_id, "sticker_file_id", message.sticker.file_id)


@router.message(SettingsInput.sticker, TEXT_INPUT)
async def got_not_sticker(message: Message, state: FSMContext):
    group_id = (await state.get_data())["group_id"]
    await message.answer(NOT_A_STICKER_TEXT, reply_markup=cancel_keyboard(group_id))


async def _save_and_show(
    message: Message, bot: Bot, db: Database, state: FSMContext, group_id: int, field: str, value
):
    await state.clear()
    if not await ensure_manager(message, bot, db, group_id):
        return
    await db.set_setting(group_id, field, value)
    text, keyboard = await settings_view(db, group_id)
    await message.answer(text, reply_markup=keyboard)
