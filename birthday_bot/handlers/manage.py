"""
manage.py — Tugmali ro'yxat: yozuv kartasi, ism/sanani tahrirlash, o'chirish.
"""

from typing import Optional, Union

from aiogram import Bot, F, Router
from aiogram.enums import ChatType
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BufferedInputFile, CallbackQuery, InlineKeyboardMarkup, Message

from birthday_bot.config import Config
from birthday_bot.database import Database
from birthday_bot.dates import now
from birthday_bot.handlers.ui import TEXT_INPUT, ensure_manager, show
from birthday_bot.keyboards import (
    RECORDS_PAGE_SIZE,
    ListTool,
    Menu,
    RecordAction,
    RecordPage,
    cancel_keyboard,
    confirm_delete_keyboard,
    empty_list_keyboard,
    record_keyboard,
    records_keyboard,
    search_results_keyboard,
)
from birthday_bot.models import Birthday
from birthday_bot.parsing import ParseError, parse_date, parse_name
from birthday_bot.texts import (
    ASK_NEW_DATE_TEXT,
    ASK_NEW_NAME_TEXT,
    ASK_SEARCH_TEXT,
    EMPTY_LIST_TEXT,
    EXPORT_CAPTION,
    RECORD_GONE_TEXT,
    SAVED_TEXT,
    confirm_delete_text,
    deleted_text,
    export_text,
    record_card,
    records_title,
    search_results_text,
)

router = Router(name="manage")
router.message.filter(F.chat.type == ChatType.PRIVATE)


SEARCH_LIMIT = 20
EXPORT_FILENAME = "tugilgan_kunlar.txt"


class EditBirthday(StatesGroup):
    name = State()
    date = State()


class ManageSearch(StatesGroup):
    query = State()


async def records_view(db: Database, group_id: int, page: int) -> tuple[str, InlineKeyboardMarkup]:
    total = await db.count_birthdays(group_id)
    if total == 0:
        return EMPTY_LIST_TEXT, empty_list_keyboard(group_id)
    pages = (total + RECORDS_PAGE_SIZE - 1) // RECORDS_PAGE_SIZE
    page = max(0, min(page, pages - 1))
    items = await db.list_birthdays(group_id, limit=RECORDS_PAGE_SIZE, offset=page * RECORDS_PAGE_SIZE)
    return records_title(total), records_keyboard(group_id, items, page, pages)


@router.callback_query(Menu.filter(F.action == "list"))
@router.callback_query(RecordPage.filter())
async def cb_records(
    callback: CallbackQuery, callback_data: Union[Menu, RecordPage], bot: Bot, db: Database
):
    if not await ensure_manager(callback, bot, db, callback_data.group_id):
        return
    page = getattr(callback_data, "page", 0)
    text, keyboard = await records_view(db, callback_data.group_id, page)
    await show(callback, text, keyboard)


@router.callback_query(ListTool.filter(F.action == "search"))
async def cb_search(
    callback: CallbackQuery, callback_data: ListTool, bot: Bot, db: Database, state: FSMContext
):
    group_id = callback_data.group_id
    if not await ensure_manager(callback, bot, db, group_id):
        return
    await state.set_state(ManageSearch.query)
    await state.set_data({"group_id": group_id})
    await show(callback, ASK_SEARCH_TEXT, cancel_keyboard(group_id))


@router.message(ManageSearch.query, TEXT_INPUT)
async def got_search(message: Message, bot: Bot, db: Database, state: FSMContext):
    group_id = (await state.get_data())["group_id"]
    await state.clear()
    if not await ensure_manager(message, bot, db, group_id):
        return
    query = " ".join(message.text.split())
    found = await db.find_birthdays(group_id, query, limit=SEARCH_LIMIT)
    await message.answer(
        search_results_text(query, len(found)),
        reply_markup=search_results_keyboard(group_id, found),
    )


@router.callback_query(ListTool.filter(F.action == "export"))
async def cb_export(callback: CallbackQuery, callback_data: ListTool, bot: Bot, db: Database):
    group_id = callback_data.group_id
    if not await ensure_manager(callback, bot, db, group_id):
        return
    birthdays = await db.list_birthdays(group_id)
    if not birthdays:
        await callback.answer(EMPTY_LIST_TEXT, show_alert=True)
        return
    document = BufferedInputFile(export_text(birthdays).encode("utf-8"), filename=EXPORT_FILENAME)
    await bot.send_document(callback.from_user.id, document, caption=EXPORT_CAPTION)
    await callback.answer()


@router.callback_query(RecordAction.filter())
async def cb_record(
    callback: CallbackQuery,
    callback_data: RecordAction,
    bot: Bot,
    db: Database,
    config: Config,
    state: FSMContext,
):
    group_id, page = callback_data.group_id, callback_data.page
    if not await ensure_manager(callback, bot, db, group_id):
        return
    birthday = await db.get_birthday(group_id, callback_data.record_id)
    if birthday is None:
        text, keyboard = await records_view(db, group_id, page)
        await show(callback, f"{RECORD_GONE_TEXT}\n\n{text}", keyboard)
        return

    action = callback_data.action
    if action == "show":
        await show(
            callback,
            record_card(birthday, now(config.timezone).date()),
            record_keyboard(group_id, birthday.id, page),
        )
    elif action == "del":
        await show(
            callback,
            confirm_delete_text(birthday),
            confirm_delete_keyboard(group_id, birthday.id, page),
        )
    elif action == "delyes":
        await db.remove_birthday(group_id, birthday.id)
        text, keyboard = await records_view(db, group_id, page)
        await show(callback, f"{deleted_text(birthday.name)}\n\n{text}", keyboard)
    elif action in ("name", "date"):
        await state.set_state(EditBirthday.name if action == "name" else EditBirthday.date)
        await state.set_data({"group_id": group_id, "record_id": birthday.id, "page": page})
        await show(
            callback,
            ASK_NEW_NAME_TEXT if action == "name" else ASK_NEW_DATE_TEXT,
            cancel_keyboard(group_id),
        )


async def _edited_record(
    message: Message, bot: Bot, db: Database, state: FSMContext
) -> Optional[tuple[Birthday, int]]:
    """Tahrirlanayotgan yozuv va ro'yxat sahifasi; bo'lmasa None (holat tozalanadi)."""
    data = await state.get_data()
    await state.clear()
    if not await ensure_manager(message, bot, db, data["group_id"]):
        return None
    birthday = await db.get_birthday(data["group_id"], data["record_id"])
    if birthday is None:
        await message.answer(RECORD_GONE_TEXT)
        return None
    return birthday, data["page"]


async def _answer_card(message: Message, db: Database, config: Config, birthday: Birthday, page: int):
    updated = await db.get_birthday(birthday.group_id, birthday.id)
    await message.answer(
        f"{SAVED_TEXT}\n\n{record_card(updated, now(config.timezone).date())}",
        reply_markup=record_keyboard(updated.group_id, updated.id, page),
    )


@router.message(EditBirthday.name, TEXT_INPUT)
async def got_new_name(message: Message, bot: Bot, db: Database, config: Config, state: FSMContext):
    try:
        name = parse_name(message.text)
    except ParseError as exc:
        group_id = (await state.get_data())["group_id"]
        await message.answer(f"❗ {exc}\n\n{ASK_NEW_NAME_TEXT}", reply_markup=cancel_keyboard(group_id))
        return
    found = await _edited_record(message, bot, db, state)
    if found is None:
        return
    birthday, page = found
    await db.update_birthday(
        birthday.group_id, birthday.id, name, birthday.day, birthday.month, birthday.year
    )
    await _answer_card(message, db, config, birthday, page)


@router.message(EditBirthday.date, TEXT_INPUT)
async def got_new_date(message: Message, bot: Bot, db: Database, config: Config, state: FSMContext):
    try:
        parsed = parse_date(message.text, now(config.timezone).date())
    except ParseError as exc:
        group_id = (await state.get_data())["group_id"]
        await message.answer(f"❗ {exc}\n\n{ASK_NEW_DATE_TEXT}", reply_markup=cancel_keyboard(group_id))
        return
    found = await _edited_record(message, bot, db, state)
    if found is None:
        return
    birthday, page = found
    await db.update_birthday(
        birthday.group_id, birthday.id, birthday.name, parsed.day, parsed.month, parsed.year
    )
    await _answer_card(message, db, config, birthday, page)
