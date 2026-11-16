"""
permissions.py — Qaysi guruh bilan ishlanayotganini aniqlash va
foydalanuvchi adminligini tekshirish.
"""

import logging
import os
from typing import Optional

from aiogram import Bot
from aiogram.enums import ChatMemberStatus, ChatType
from aiogram.exceptions import TelegramAPIError
from aiogram.types import Chat, Message

logger = logging.getLogger(__name__)

ADMIN_STATUSES = {ChatMemberStatus.CREATOR, ChatMemberStatus.ADMINISTRATOR}


def get_default_group_id() -> Optional[int]:
    value = os.getenv("DEFAULT_GROUP_ID")
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        logger.warning("DEFAULT_GROUP_ID noto'g'ri: %r", value)
        return None


def get_target_group_id(chat: Chat) -> int:
    """
    Agar shaxsiy chat bo'lsa va DEFAULT_GROUP_ID mavjud bo'lsa, o'sha guruh
    ID'sini qaytaradi. Aks holda shu chat ID'sini qaytaradi.
    """
    default_gid = get_default_group_id()
    if chat.type == ChatType.PRIVATE and default_gid:
        return default_gid
    return chat.id


async def can_edit(message: Message, bot: Bot) -> tuple[bool, Optional[int]]:
    """
    Foydalanuvchi yozuvlarni/sozlamalarni o'zgartira oladimi? (ruxsat, guruh_id).
    Guruhda — shu guruh admini; shaxsiy chatda — DEFAULT_GROUP_ID guruhining admini.
    """
    if message.chat.type == ChatType.PRIVATE:
        group_id = get_default_group_id()
        if group_id is None:
            return False, None
    else:
        group_id = message.chat.id
        # Anonim admin guruh nomidan yozadi
        if message.sender_chat and message.sender_chat.id == group_id:
            return True, group_id

    if message.from_user is None:
        return False, group_id
    try:
        member = await bot.get_chat_member(group_id, message.from_user.id)
    except TelegramAPIError as exc:
        logger.warning("Adminlikni tekshirib bo'lmadi (guruh=%s): %s", group_id, exc)
        return False, group_id
    return member.status in ADMIN_STATUSES, group_id
