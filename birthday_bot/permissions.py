"""
permissions.py — Qaysi guruh bilan ishlanayotganini aniqlash va
foydalanuvchining guruhdagi rolini tekshirish.
"""

import logging
from enum import IntEnum
from typing import Optional

from aiogram import Bot
from aiogram.enums import ChatMemberStatus, ChatType
from aiogram.exceptions import TelegramAPIError, TelegramMigrateToChat
from aiogram.types import Chat, Message

from birthday_bot.config import Config
from birthday_bot.database import Database

logger = logging.getLogger(__name__)

ADMIN_STATUSES = {ChatMemberStatus.CREATOR, ChatMemberStatus.ADMINISTRATOR}


class Role(IntEnum):
    NONE = 0      # guruhda emas yoki tekshirib bo'lmadi
    MEMBER = 1    # faqat o'z yozuvi
    MANAGER = 2   # botni qo'shgan yoki admin tayinlagan
    ADMIN = 3     # guruh admini — boshqaruvchilarni ham tayinlaydi


def target_group_id(chat: Chat, config: Config) -> int:
    """Shaxsiy chatda DEFAULT_GROUP_ID (agar bor bo'lsa), aks holda shu chat ID'si."""
    if chat.type == ChatType.PRIVATE and config.default_group_id:
        return config.default_group_id
    return chat.id


async def get_role(bot: Bot, db: Database, group_id: int, user_id: int) -> Role:
    """Foydalanuvchining guruhdagi roli (bitta get_chat_member so'rovi)."""
    try:
        member = await bot.get_chat_member(group_id, user_id)
    except TelegramAPIError as exc:
        logger.warning("Rolni tekshirib bo'lmadi (guruh=%s, user=%s): %s", group_id, user_id, exc)
        return Role.NONE

    status = member.status
    if status in ADMIN_STATUSES:
        return Role.ADMIN
    in_chat = status == ChatMemberStatus.MEMBER or (
        status == ChatMemberStatus.RESTRICTED and getattr(member, "is_member", False)
    )
    if not in_chat:
        logger.info("Guruhda emas: guruh=%s, user=%s, status=%s", group_id, user_id, status)
        return Role.NONE
    return Role.MANAGER if await db.is_manager(group_id, user_id) else Role.MEMBER


async def resolve_group(bot: Bot, db: Database, group_id: int) -> Optional[int]:
    """
    Guruhning amaldagi ID'si. Guruh supergroupga aylangan bo'lsa — yozuvlar yangi
    ID ga ko'chiriladi; bot guruhga kira olmasa — None.
    """
    try:
        await bot.get_chat(group_id)
    except TelegramMigrateToChat as exc:
        await db.migrate_group(group_id, exc.migrate_to_chat_id)
        logger.info("Guruh ko'chirildi: %s -> %s", group_id, exc.migrate_to_chat_id)
        return exc.migrate_to_chat_id
    except TelegramAPIError as exc:
        logger.warning("Guruhga kirib bo'lmadi (guruh=%s): %s", group_id, exc)
        return None
    return group_id


async def editable_group_id(
    message: Message, bot: Bot, db: Database, config: Config
) -> Optional[int]:
    """
    Foydalanuvchi o'zgartira oladigan guruh ID'si, ruxsat bo'lmasa None.
    Guruhda — shu guruh admini yoki boshqaruvchisi; shaxsiy chatda —
    DEFAULT_GROUP_ID guruhiniki.
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
    role = await get_role(bot, db, group_id, message.from_user.id)
    return group_id if role >= Role.MANAGER else None
