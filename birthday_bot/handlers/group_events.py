"""
group_events.py — Bot guruhga qo'shilganda/chiqarilganda va guruhdagi /menu.
"""

import logging

from aiogram import Bot, F, Router
from aiogram.enums import ChatMemberStatus, ChatType
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command
from aiogram.types import ChatMemberUpdated, Message

from birthday_bot.database import Database
from birthday_bot.keyboards import group_invite_keyboard
from birthday_bot.texts import WELCOME_TEXT

logger = logging.getLogger(__name__)

GROUP_TYPES = {ChatType.GROUP, ChatType.SUPERGROUP}
IN_CHAT = {ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR}

router = Router(name="group_events")
router.message.filter(F.chat.type.in_(GROUP_TYPES))
router.my_chat_member.filter(F.chat.type.in_(GROUP_TYPES))


async def send_welcome(bot: Bot, chat_id: int):
    me = await bot.me()
    try:
        await bot.send_message(
            chat_id, WELCOME_TEXT, reply_markup=group_invite_keyboard(me.username, chat_id)
        )
    except TelegramAPIError as exc:
        logger.warning("Salomlashish yuborilmadi (guruh=%s): %s", chat_id, exc)


@router.my_chat_member()
async def on_bot_membership(event: ChatMemberUpdated, bot: Bot, db: Database):
    was_in = event.old_chat_member.status in IN_CHAT
    is_in = event.new_chat_member.status in IN_CHAT
    if is_in:
        await db.upsert_group(event.chat.id, event.chat.title or "")
        if not was_in:
            logger.info("Bot guruhga qo'shildi: %s", event.chat.id)
            await send_welcome(bot, event.chat.id)
    else:
        await db.set_group_active(event.chat.id, False)
        logger.info("Bot guruhdan chiqarildi: %s", event.chat.id)


@router.message(Command("menu", "start"))
async def cmd_group_menu(message: Message, bot: Bot, db: Database):
    # Bu yangilanishdan oldin qo'shilgan guruhlar ham shu yerda ro'yxatga olinadi
    await db.upsert_group(message.chat.id, message.chat.title or "")
    await send_welcome(bot, message.chat.id)
