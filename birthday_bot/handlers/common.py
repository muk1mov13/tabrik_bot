"""
common.py — /help va guruh chat ID o'zgarishi.
"""

import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message

from birthday_bot.database import Database
from birthday_bot.texts import HELP_TEXT

logger = logging.getLogger(__name__)

router = Router(name="common")


@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(HELP_TEXT)


@router.message(F.migrate_to_chat_id)
async def on_group_migrated(message: Message, db: Database):
    """Oddiy guruh supergroupga aylanganda yozuvlarni yangi chat ID ga ko'chiradi."""
    await db.migrate_group(message.chat.id, message.migrate_to_chat_id)
    logger.info("Guruh ko'chirildi: %s -> %s", message.chat.id, message.migrate_to_chat_id)
