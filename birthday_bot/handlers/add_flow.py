"""
add_flow.py — Tug'ilgan kun qo'shish savol-javobi: ism → sana → tasdiqlash.
"""

from aiogram import Bot, F, Router
from aiogram.enums import ChatType
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove

from birthday_bot.config import Config
from birthday_bot.database import Database
from birthday_bot.dates import now
from birthday_bot.handlers.ui import TEXT_INPUT, ensure_manager, show
from birthday_bot.keyboards import (
    PICK_USER_REQUEST,
    Menu,
    SaveNew,
    add_confirm_keyboard,
    after_add_keyboard,
    cancel_keyboard,
    pick_user_keyboard,
)
from birthday_bot.models import MAX_NAME_LENGTH
from birthday_bot.parsing import ParseError, parse_date, parse_name
from birthday_bot.texts import (
    ASK_DATE_TEXT,
    ASK_NAME_TEXT,
    PICK_USER_HINT_TEXT,
    STALE_TEXT,
    add_preview,
    added_text,
    name_accepted_text,
)

router = Router(name="add_flow")
router.message.filter(F.chat.type == ChatType.PRIVATE)


class AddBirthday(StatesGroup):
    name = State()
    date = State()
    confirm = State()


@router.callback_query(Menu.filter(F.action == "add"))
async def cb_add(callback: CallbackQuery, callback_data: Menu, bot: Bot, db: Database, state: FSMContext):
    group_id = callback_data.group_id
    if not await ensure_manager(callback, bot, db, group_id):
        return
    await state.set_state(AddBirthday.name)
    # pick_keyboard — bekor qilinganda "Telegram'dan tanlash" klaviaturasini yopish uchun
    await state.set_data({"group_id": group_id, "pick_keyboard": True})
    await show(callback, ASK_NAME_TEXT, cancel_keyboard(group_id))
    await callback.message.answer(PICK_USER_HINT_TEXT, reply_markup=pick_user_keyboard())


async def _accept_name(message: Message, state: FSMContext, name: str, user_id=None):
    group_id = (await state.get_data())["group_id"]
    await state.update_data(name=name, user_id=user_id, pick_keyboard=False)
    await state.set_state(AddBirthday.date)
    # Tanlov klaviaturasini yopamiz va kim tanlanganini ko'rsatamiz
    await message.answer(name_accepted_text(name, user_id), reply_markup=ReplyKeyboardRemove())
    await message.answer(ASK_DATE_TEXT, reply_markup=cancel_keyboard(group_id))


@router.message(AddBirthday.name, TEXT_INPUT)
async def got_name(message: Message, state: FSMContext):
    try:
        name = parse_name(message.text)
    except ParseError as exc:
        group_id = (await state.get_data())["group_id"]
        await message.answer(f"❗ {exc}\n\n{ASK_NAME_TEXT}", reply_markup=cancel_keyboard(group_id))
        return
    await _accept_name(message, state, name)


@router.message(AddBirthday.name, F.users_shared.request_id == PICK_USER_REQUEST)
async def got_shared_user(message: Message, state: FSMContext):
    shared = message.users_shared.users[0]
    full_name = " ".join(part for part in (shared.first_name, shared.last_name) if part)
    name = (full_name or shared.username or str(shared.user_id))[:MAX_NAME_LENGTH]
    await _accept_name(message, state, name, shared.user_id)


@router.message(AddBirthday.date, TEXT_INPUT)
async def got_date(message: Message, state: FSMContext, db: Database, config: Config):
    data = await state.get_data()
    group_id = data["group_id"]
    try:
        parsed = parse_date(message.text, now(config.timezone).date())
    except ParseError as exc:
        await message.answer(f"❗ {exc}\n\n{ASK_DATE_TEXT}", reply_markup=cancel_keyboard(group_id))
        return
    await state.update_data(day=parsed.day, month=parsed.month, year=parsed.year)
    await state.set_state(AddBirthday.confirm)

    # Takror yozuv: bir xil ism yoki o'sha Telegram foydalanuvchisi allaqachon bor
    duplicates = await db.find_same_name(group_id, data["name"])
    if data.get("user_id"):
        linked = await db.get_birthday_by_user(group_id, data["user_id"])
        if linked and linked not in duplicates:
            duplicates.append(linked)
    await message.answer(
        add_preview(data["name"], parsed.day, parsed.month, parsed.year, duplicates),
        reply_markup=add_confirm_keyboard(group_id),
    )


@router.callback_query(AddBirthday.confirm, SaveNew.filter())
async def cb_save(callback: CallbackQuery, bot: Bot, db: Database, state: FSMContext):
    data = await state.get_data()
    await state.clear()
    group_id = data["group_id"]
    if not await ensure_manager(callback, bot, db, group_id):
        return
    await db.add_birthday(
        group_id=group_id,
        name=data["name"],
        day=data["day"],
        month=data["month"],
        year=data["year"],
        added_by=callback.from_user.id,
        user_id=data.get("user_id"),
    )
    await show(
        callback,
        added_text(data["name"], data["day"], data["month"], data["year"]),
        after_add_keyboard(group_id),
    )


@router.callback_query(SaveNew.filter())
async def cb_save_stale(callback: CallbackQuery):
    # Holat yo'q: allaqachon saqlangan, bekor qilingan yoki bot qayta ishga tushgan
    await callback.answer(STALE_TEXT, show_alert=True)
