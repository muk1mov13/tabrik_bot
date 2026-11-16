"""
commands.py — Telegram'dagi "/" menyusida ko'rinadigan buyruqlar ro'yxati.

Shaxsiy chat va guruh uchun alohida: guruhda hamma uchun ko'rish buyruqlari,
shaxsiy chatda — tugmali menyu.
"""

import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import BotCommand, BotCommandScopeAllGroupChats, BotCommandScopeAllPrivateChats

logger = logging.getLogger(__name__)

PRIVATE_COMMANDS = [
    BotCommand(command="menu", description="Tugmali menyu: qo'shish, ro'yxat, sozlamalar"),
    BotCommand(command="help", description="Yordam"),
]
GROUP_COMMANDS = [
    BotCommand(command="upcoming", description="Yaqin kunlardagi tug'ilgan kunlar"),
    BotCommand(command="list", description="Saqlangan tug'ilgan kunlar"),
    BotCommand(command="find", description="Ism bo'yicha qidirish"),
    BotCommand(command="menu", description="Tug'ilgan kun qo'shish tugmasi"),
    BotCommand(command="help", description="Yordam"),
]


async def set_bot_commands(bot: Bot):
    """Buyruqlar ro'yxatini o'rnatadi; Telegram xatosi botni to'xtatmaydi."""
    try:
        await bot.set_my_commands(PRIVATE_COMMANDS, scope=BotCommandScopeAllPrivateChats())
        await bot.set_my_commands(GROUP_COMMANDS, scope=BotCommandScopeAllGroupChats())
    except TelegramAPIError as exc:
        logger.warning("Buyruqlar ro'yxatini o'rnatib bo'lmadi: %s", exc)
