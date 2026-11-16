"""
menu.py — Shaxsiy chatdagi tugmali menyu: /start (guruh havolasi bilan),
/menu, guruh tanlash va savol-javobni bekor qilish.
"""

from typing import Optional, Union

from aiogram import Bot, F, Router
from aiogram.enums import ChatType
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from birthday_bot.database import Database
from birthday_bot.handlers.ui import ensure_admin, show
from birthday_bot.keyboards import Cancel, Menu, PickGroup, groups_keyboard, main_menu_keyboard
from birthday_bot.models import Group
from birthday_bot.parsing import parse_group_payload
from birthday_bot.permissions import is_admin
from birthday_bot.texts import CHOOSE_GROUP_TEXT, NO_GROUPS_TEXT, NOT_ADMIN_TEXT, menu_text

router = Router(name="menu")
router.message.filter(F.chat.type == ChatType.PRIVATE)


async def available_groups(bot: Bot, db: Database, user_id: int) -> list[Group]:
    """Foydalanuvchi hozir ham admini bo'lgan bog'langan guruhlar."""
    groups = []
    for group in await db.admin_groups(user_id):
        if await is_admin(bot, group.group_id, user_id):
            groups.append(group)
        else:
            await db.unlink_admin(user_id, group.group_id)
    return groups


async def main_menu_view(db: Database, user_id: int, group_id: int) -> tuple[str, InlineKeyboardMarkup]:
    group = await db.get_group(group_id)
    many_groups = len(await db.admin_groups(user_id)) > 1
    return menu_text(group.title if group else ""), main_menu_keyboard(group_id, many_groups)


async def start_view(
    bot: Bot, db: Database, user_id: int
) -> tuple[str, Optional[InlineKeyboardMarkup]]:
    """Guruh bitta bo'lsa — uning menyusi, bir nechta bo'lsa — tanlash."""
    groups = await available_groups(bot, db, user_id)
    if not groups:
        return NO_GROUPS_TEXT, None
    if len(groups) == 1:
        return await main_menu_view(db, user_id, groups[0].group_id)
    return CHOOSE_GROUP_TEXT, groups_keyboard(groups)


@router.message(CommandStart(deep_link=True))
async def cmd_start_link(message: Message, command: CommandObject, bot: Bot, db: Database):
    user_id = message.from_user.id
    group_id = parse_group_payload(command.args or "")
    if group_id is None:
        text, keyboard = await start_view(bot, db, user_id)
        await message.answer(text, reply_markup=keyboard)
        return

    if not await is_admin(bot, group_id, user_id):
        await db.unlink_admin(user_id, group_id)
        await message.answer(NOT_ADMIN_TEXT)
        return

    if await db.get_group(group_id) is None:
        # Bot guruhga bu yangilanishdan oldin qo'shilgan — nomini so'raymiz
        chat = await bot.get_chat(group_id)
        await db.upsert_group(group_id, chat.title or "")
    await db.link_admin(user_id, group_id)
    text, keyboard = await main_menu_view(db, user_id, group_id)
    await message.answer(text, reply_markup=keyboard)


@router.message(Command("start", "menu"))
async def cmd_start(message: Message, bot: Bot, db: Database):
    text, keyboard = await start_view(bot, db, message.from_user.id)
    await message.answer(text, reply_markup=keyboard)


@router.callback_query(Menu.filter(F.action == "home"))
@router.callback_query(Cancel.filter())
async def cb_home(
    callback: CallbackQuery,
    callback_data: Union[Menu, Cancel],
    bot: Bot,
    db: Database,
    state: FSMContext,
):
    await state.clear()
    if await ensure_admin(callback, bot, db, callback_data.group_id):
        text, keyboard = await main_menu_view(db, callback.from_user.id, callback_data.group_id)
        await show(callback, text, keyboard)


@router.callback_query(Menu.filter(F.action == "groups"))
async def cb_groups(callback: CallbackQuery, bot: Bot, db: Database):
    text, keyboard = await start_view(bot, db, callback.from_user.id)
    await show(callback, text, keyboard)


@router.callback_query(PickGroup.filter())
async def cb_pick_group(callback: CallbackQuery, callback_data: PickGroup, bot: Bot, db: Database):
    if await ensure_admin(callback, bot, db, callback_data.group_id):
        text, keyboard = await main_menu_view(db, callback.from_user.id, callback_data.group_id)
        await show(callback, text, keyboard)
