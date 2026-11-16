"""
group_events.py — Bot guruhga qo'shilganda/chiqarilganda, guruhdagi /menu va
/manager (boshqaruvchi tayinlash).
"""

import logging
from typing import Optional

from aiogram import Bot, F, Router
from aiogram.enums import ChatMemberStatus, ChatType
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, CommandObject
from aiogram.types import ChatMemberUpdated, Message, User

from birthday_bot.database import Database
from birthday_bot.keyboards import group_invite_keyboard
from birthday_bot.permissions import Role, get_role
from birthday_bot.texts import (
    MANAGER_ADMIN_ONLY_TEXT,
    MANAGER_USAGE,
    manager_added_text,
    manager_removed_text,
    welcome_text,
)

logger = logging.getLogger(__name__)

GROUP_TYPES = {ChatType.GROUP, ChatType.SUPERGROUP}
IN_CHAT = {ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR}

router = Router(name="group_events")
router.message.filter(F.chat.type.in_(GROUP_TYPES))
router.my_chat_member.filter(F.chat.type.in_(GROUP_TYPES))


async def send_welcome(bot: Bot, chat_id: int, adder: Optional[User] = None):
    me = await bot.me()
    text = welcome_text(adder.full_name, adder.id) if adder else welcome_text()
    try:
        await bot.send_message(chat_id, text, reply_markup=group_invite_keyboard(me.username, chat_id))
    except TelegramAPIError as exc:
        logger.warning("Salomlashish yuborilmadi (guruh=%s): %s", chat_id, exc)


@router.my_chat_member()
async def on_bot_membership(event: ChatMemberUpdated, bot: Bot, db: Database):
    group_id = event.chat.id
    was_in = event.old_chat_member.status in IN_CHAT
    is_in = event.new_chat_member.status in IN_CHAT
    if not is_in:
        await db.set_group_active(group_id, False)
        logger.info("Bot guruhdan chiqarildi: %s", group_id)
        return

    await db.upsert_group(group_id, event.chat.title or "")
    if was_in:
        return
    logger.info("Bot guruhga qo'shildi: %s", group_id)
    # Botni qo'shgan odam admin bo'lmasa ham tug'ilgan kunlarni boshqaradi
    adder = event.from_user if not event.from_user.is_bot else None
    if adder:
        await db.add_manager(group_id, adder.id, added_by=adder.id)
        await db.link_user(adder.id, group_id)
    await send_welcome(bot, group_id, adder)


@router.message(Command("menu", "start"))
async def cmd_group_menu(message: Message, bot: Bot, db: Database):
    # Bu yangilanishdan oldin qo'shilgan guruhlar ham shu yerda ro'yxatga olinadi
    await db.upsert_group(message.chat.id, message.chat.title or "")
    await send_welcome(bot, message.chat.id)


@router.message(Command("manager"))
async def cmd_manager(message: Message, command: CommandObject, bot: Bot, db: Database):
    group_id = message.chat.id
    # Anonim admin guruh nomidan yozadi
    anonymous_admin = message.sender_chat is not None and message.sender_chat.id == group_id
    if not anonymous_admin and (
        message.from_user is None
        or await get_role(bot, db, group_id, message.from_user.id) < Role.ADMIN
    ):
        await message.answer(MANAGER_ADMIN_ONLY_TEXT)
        return

    replied = message.reply_to_message
    target = replied.from_user if replied else None
    if target is None or target.is_bot:
        await message.answer(MANAGER_USAGE)
        return

    if (command.args or "").strip().lower() == "off":
        await db.remove_manager(group_id, target.id)
        await message.answer(manager_removed_text(target.full_name, target.id))
        return

    await db.upsert_group(group_id, message.chat.title or "")
    added_by = message.from_user.id if message.from_user and not anonymous_admin else None
    await db.add_manager(group_id, target.id, added_by=added_by)
    await db.link_user(target.id, group_id)
    await message.answer(manager_added_text(target.full_name, target.id))
