"""
self_flow.py — Oddiy a'zo o'z tug'ilgan kunini qo'shadi, o'zgartiradi yoki
o'chiradi. Yozuv har doim from_user.id orqali topiladi — boshqaning yozuviga
tegib bo'lmaydi.
"""

from aiogram import Bot, F, Router
from aiogram.enums import ChatType
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from birthday_bot.config import Config
from birthday_bot.database import Database
from birthday_bot.dates import now
from birthday_bot.handlers.menu import main_menu_view
from birthday_bot.handlers.ui import TEXT_INPUT, ensure_role, show
from birthday_bot.keyboards import (
    SelfAction,
    cancel_keyboard,
    self_confirm_keyboard,
    self_delete_keyboard,
)
from birthday_bot.models import MAX_NAME_LENGTH
from birthday_bot.parsing import ParseError, parse_date
from birthday_bot.permissions import Role
from birthday_bot.texts import (
    ASK_OWN_DATE_TEXT,
    OWN_DELETE_CONFIRM_TEXT,
    OWN_DELETED_TEXT,
    OWN_SAVED_TEXT,
    STALE_TEXT,
    add_preview,
)

router = Router(name="self_flow")
router.message.filter(F.chat.type == ChatType.PRIVATE)


class SelfBirthday(StatesGroup):
    date = State()
    confirm = State()


async def _show_menu(
    callback: CallbackQuery, db: Database, config: Config, group_id: int, role: Role, prefix: str = ""
):
    text, keyboard = await main_menu_view(db, config, callback.from_user.id, group_id, role)
    await show(callback, f"{prefix}\n\n{text}" if prefix else text, keyboard)


@router.callback_query(SelfAction.filter(F.action.in_({"add", "date"})))
async def cb_self_date(
    callback: CallbackQuery, callback_data: SelfAction, bot: Bot, db: Database, state: FSMContext
):
    group_id = callback_data.group_id
    if await ensure_role(callback, bot, db, group_id, Role.MEMBER) is None:
        return
    await state.set_state(SelfBirthday.date)
    await state.set_data({"group_id": group_id})
    await show(callback, ASK_OWN_DATE_TEXT, cancel_keyboard(group_id))


@router.message(SelfBirthday.date, TEXT_INPUT)
async def got_own_date(message: Message, state: FSMContext, config: Config):
    group_id = (await state.get_data())["group_id"]
    try:
        parsed = parse_date(message.text, now(config.timezone).date())
    except ParseError as exc:
        await message.answer(f"❗ {exc}\n\n{ASK_OWN_DATE_TEXT}", reply_markup=cancel_keyboard(group_id))
        return
    name = message.from_user.full_name[:MAX_NAME_LENGTH]
    await state.update_data(name=name, day=parsed.day, month=parsed.month, year=parsed.year)
    await state.set_state(SelfBirthday.confirm)
    await message.answer(
        add_preview(name, parsed.day, parsed.month, parsed.year),
        reply_markup=self_confirm_keyboard(group_id),
    )


@router.callback_query(SelfBirthday.confirm, SelfAction.filter(F.action == "save"))
async def cb_self_save(callback: CallbackQuery, bot: Bot, db: Database, config: Config, state: FSMContext):
    data = await state.get_data()
    await state.clear()
    group_id, user_id = data["group_id"], callback.from_user.id
    role = await ensure_role(callback, bot, db, group_id, Role.MEMBER)
    if role is None:
        return
    own = await db.get_birthday_by_user(group_id, user_id)
    if own:
        await db.update_birthday(group_id, own.id, own.name, data["day"], data["month"], data["year"])
    else:
        await db.add_birthday(
            group_id=group_id,
            name=data["name"],
            day=data["day"],
            month=data["month"],
            year=data["year"],
            added_by=user_id,
            user_id=user_id,
        )
    await _show_menu(callback, db, config, group_id, role, OWN_SAVED_TEXT)


@router.callback_query(SelfAction.filter(F.action == "save"))
async def cb_self_save_stale(callback: CallbackQuery):
    await callback.answer(STALE_TEXT, show_alert=True)


@router.callback_query(SelfAction.filter(F.action == "del"))
async def cb_self_delete(callback: CallbackQuery, callback_data: SelfAction, bot: Bot, db: Database):
    group_id = callback_data.group_id
    if await ensure_role(callback, bot, db, group_id, Role.MEMBER) is not None:
        await show(callback, OWN_DELETE_CONFIRM_TEXT, self_delete_keyboard(group_id))


@router.callback_query(SelfAction.filter(F.action == "delyes"))
async def cb_self_delete_yes(
    callback: CallbackQuery, callback_data: SelfAction, bot: Bot, db: Database, config: Config
):
    group_id = callback_data.group_id
    role = await ensure_role(callback, bot, db, group_id, Role.MEMBER)
    if role is None:
        return
    own = await db.get_birthday_by_user(group_id, callback.from_user.id)
    if own:
        await db.remove_birthday(group_id, own.id)
    await _show_menu(callback, db, config, group_id, role, OWN_DELETED_TEXT if own else "")
