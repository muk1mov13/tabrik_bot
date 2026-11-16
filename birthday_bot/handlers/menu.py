"""
menu.py — Shaxsiy chatdagi tugmali menyu: /start (guruh havolasi bilan),
/menu, guruh tanlash, savol-javobni bekor qilish va boshqaruvchilar ro'yxati.

Menyu rolga qarab chiqadi: admin va boshqaruvchi hamma yozuvlarni boshqaradi,
oddiy a'zo faqat o'z tug'ilgan kunini (handlers/self_flow.py).
"""

from typing import Optional, Union

from aiogram import Bot, F, Router
from aiogram.enums import ChatType
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message, ReplyKeyboardRemove

from birthday_bot.config import Config
from birthday_bot.database import Database
from birthday_bot.dates import now
from birthday_bot.handlers.ui import ensure_role, show
from birthday_bot.keyboards import (
    Cancel,
    Menu,
    PickGroup,
    RemoveManager,
    groups_keyboard,
    main_menu_keyboard,
    managers_keyboard,
    member_menu_keyboard,
)
from birthday_bot.models import Group
from birthday_bot.parsing import parse_group_payload
from birthday_bot.permissions import Role, get_role, resolve_group
from birthday_bot.texts import (
    CANCELLED_TEXT,
    CHOOSE_GROUP_TEXT,
    GROUP_UNAVAILABLE_TEXT,
    NO_GROUPS_TEXT,
    NOT_IN_GROUP_TEXT,
    managers_text,
    member_menu_text,
    menu_text,
)

router = Router(name="menu")
router.message.filter(F.chat.type == ChatType.PRIVATE)


async def available_groups(bot: Bot, db: Database, user_id: int) -> list[tuple[Group, Role]]:
    """Foydalanuvchi hozir ham a'zosi bo'lgan bog'langan guruhlar va undagi roli."""
    result = []
    for group in await db.linked_groups(user_id):
        role = await get_role(bot, db, group.group_id, user_id)
        if role == Role.NONE:
            await db.unlink_user(user_id, group.group_id)
        else:
            result.append((group, role))
    return result


async def main_menu_view(
    db: Database, config: Config, user_id: int, group_id: int, role: Role
) -> tuple[str, InlineKeyboardMarkup]:
    group = await db.get_group(group_id)
    title = group.title if group else ""
    many_groups = len(await db.linked_groups(user_id)) > 1
    if role >= Role.MANAGER:
        return menu_text(title), main_menu_keyboard(group_id, many_groups)
    own = await db.get_birthday_by_user(group_id, user_id)
    return (
        member_menu_text(title, own, now(config.timezone).date()),
        member_menu_keyboard(group_id, own is not None, many_groups),
    )


async def start_view(
    bot: Bot, db: Database, config: Config, user_id: int
) -> tuple[str, Optional[InlineKeyboardMarkup]]:
    """Guruh bitta bo'lsa — uning menyusi, bir nechta bo'lsa — tanlash."""
    groups = await available_groups(bot, db, user_id)
    if not groups:
        return NO_GROUPS_TEXT, None
    if len(groups) == 1:
        group, role = groups[0]
        return await main_menu_view(db, config, user_id, group.group_id, role)
    return CHOOSE_GROUP_TEXT, groups_keyboard([group for group, _ in groups])


@router.message(CommandStart(deep_link=True))
async def cmd_start_link(
    message: Message, command: CommandObject, bot: Bot, db: Database, config: Config
):
    user_id = message.from_user.id
    group_id = parse_group_payload(command.args or "")
    if group_id is None:
        text, keyboard = await start_view(bot, db, config, user_id)
        await message.answer(text, reply_markup=keyboard)
        return

    # Eski tugma: guruh supergroupga aylangan bo'lsa yangi ID ga o'tamiz
    resolved = await resolve_group(bot, db, group_id)
    if resolved is None:
        await db.unlink_user(user_id, group_id)
        await message.answer(GROUP_UNAVAILABLE_TEXT)
        return
    group_id = resolved

    role = await get_role(bot, db, group_id, user_id)
    if role == Role.NONE:
        await db.unlink_user(user_id, group_id)
        await message.answer(NOT_IN_GROUP_TEXT)
        return

    if await db.get_group(group_id) is None:
        # Bot guruhga bu yangilanishdan oldin qo'shilgan — nomini so'raymiz
        chat = await bot.get_chat(group_id)
        await db.upsert_group(group_id, chat.title or "")
    await db.link_user(user_id, group_id)
    text, keyboard = await main_menu_view(db, config, user_id, group_id, role)
    await message.answer(text, reply_markup=keyboard)


@router.message(Command("start", "menu"))
async def cmd_start(message: Message, bot: Bot, db: Database, config: Config):
    text, keyboard = await start_view(bot, db, config, message.from_user.id)
    await message.answer(text, reply_markup=keyboard)


@router.callback_query(Menu.filter(F.action == "home"))
@router.callback_query(Cancel.filter())
@router.callback_query(PickGroup.filter())
async def cb_home(
    callback: CallbackQuery,
    callback_data: Union[Menu, Cancel, PickGroup],
    bot: Bot,
    db: Database,
    config: Config,
    state: FSMContext,
):
    if (await state.get_data()).get("pick_keyboard"):
        # Qo'shish ism bosqichida bekor qilindi — tanlov klaviaturasini yopamiz
        await bot.send_message(callback.from_user.id, CANCELLED_TEXT, reply_markup=ReplyKeyboardRemove())
    await state.clear()
    group_id = callback_data.group_id
    role = await ensure_role(callback, bot, db, group_id, Role.MEMBER)
    if role is not None:
        text, keyboard = await main_menu_view(db, config, callback.from_user.id, group_id, role)
        await show(callback, text, keyboard)


@router.callback_query(Menu.filter(F.action == "groups"))
async def cb_groups(callback: CallbackQuery, bot: Bot, db: Database, config: Config):
    text, keyboard = await start_view(bot, db, config, callback.from_user.id)
    await show(callback, text, keyboard)


async def _manager_names(bot: Bot, db: Database, group_id: int) -> list[tuple[int, str]]:
    managers = []
    for user_id in await db.list_managers(group_id):
        try:
            name = (await bot.get_chat_member(group_id, user_id)).user.full_name
        except TelegramAPIError:
            name = str(user_id)
        managers.append((user_id, name))
    return managers


async def _show_managers(callback: CallbackQuery, bot: Bot, db: Database, group_id: int, role: Role):
    managers = await _manager_names(bot, db, group_id)
    is_admin = role == Role.ADMIN
    await show(
        callback, managers_text(managers, is_admin), managers_keyboard(group_id, managers, is_admin)
    )


@router.callback_query(Menu.filter(F.action == "managers"))
async def cb_managers(callback: CallbackQuery, callback_data: Menu, bot: Bot, db: Database):
    role = await ensure_role(callback, bot, db, callback_data.group_id, Role.MANAGER)
    if role is not None:
        await _show_managers(callback, bot, db, callback_data.group_id, role)


@router.callback_query(RemoveManager.filter())
async def cb_remove_manager(
    callback: CallbackQuery, callback_data: RemoveManager, bot: Bot, db: Database
):
    group_id = callback_data.group_id
    role = await ensure_role(callback, bot, db, group_id, Role.ADMIN)
    if role is None:
        return
    await db.remove_manager(group_id, callback_data.user_id)
    await _show_managers(callback, bot, db, group_id, role)
