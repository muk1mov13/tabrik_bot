"""
permissions.py — Qaysi guruh bilan ishlanayotganini aniqlash va
foydalanuvchi adminligini tekshirish.
"""

import logging
from typing import Optional

from aiogram import Bot
from aiogram.enums import ChatMemberStatus, ChatType
from aiogram.exceptions import TelegramAPIError
from aiogram.types import Chat, Message

from birthday_bot.config import Config

logger = logging.getLogger(__name__)

ADMIN_STATUSES = {ChatMemberStatus.CREATOR, ChatMemberStatus.ADMINISTRATOR}


def target_group_id(chat: Chat, config: Config) -> int:
    """Shaxsiy chatda DEFAULT_GROUP_ID (agar bor bo'lsa), aks holda shu chat ID'si."""
    if chat.type == ChatType.PRIVATE and config.default_group_id:
        return config.default_group_id
    return chat.id


async def is_admin(bot: Bot, group_id: int, user_id: int) -> bool:
    """Foydalanuvchi guruh admini yoki egasimi. Tekshirib bo'lmasa — False."""
    try:
        member = await bot.get_chat_member(group_id, user_id)
    except TelegramAPIError as exc:
        logger.warning("Adminlikni tekshirib bo'lmadi (guruh=%s): %s", group_id, exc)
        return False
    return member.status in ADMIN_STATUSES


async def editable_group_id(message: Message, bot: Bot, config: Config) -> Optional[int]:
    """
    Foydalanuvchi o'zgartira oladigan guruh ID'si, ruxsat bo'lmasa None.
    Guruhda — shu guruh admini; shaxsiy chatda — DEFAULT_GROUP_ID guruhining admini.
    """
    if message.chat.type == ChatType.PRIVATE:
        group_id = config.default_group_id
        if group_id is None:
            return None
    else:
        group_id = message.chat.id
        # Anonim admin guruh nomidan yozadi
        if message.sender_chat and message.sender_chat.id == group_id:
            return group_id

    if message.from_user is None:
        return None
    return group_id if await is_admin(bot, group_id, message.from_user.id) else None
