"""
commands.py — Telegram'dagi "/" menyusida ko'rinadigan buyruqlar ro'yxati
va botning tavsifi ("What can this bot do?" hamda profildagi qisqa matn).

Shaxsiy chat va guruh uchun alohida: guruhda hamma uchun ko'rish buyruqlari,
shaxsiy chatda — tugmali menyu.
"""

import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import BotCommand, BotCommandScopeAllGroupChats, BotCommandScopeAllPrivateChats

from birthday_bot.texts import BOT_DESCRIPTION, BOT_SHORT_DESCRIPTION

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


async def set_bot_description(bot: Bot):
    """Bot tavsifini o'rnatadi; Telegram xatosi botni to'xtatmaydi."""
    try:
        await bot.set_my_description(BOT_DESCRIPTION)
        await bot.set_my_short_description(BOT_SHORT_DESCRIPTION)
    except TelegramAPIError as exc:
        logger.warning("Bot tavsifini o'rnatib bo'lmadi: %s", exc)
