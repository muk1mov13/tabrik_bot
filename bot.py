"""
bot.py — Botning asosiy kirish nuqtasi.

Ishga tushirish:
    export BOT_TOKEN="123456:ABC-DEF..."
    python bot.py
"""

import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

import database as db
from dotenv import load_dotenv
from handlers import router
from scheduler import setup_scheduler

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


async def main():
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError(
            "BOT_TOKEN topilmadi. Avval quyidagini bajaring:\n"
            "  export BOT_TOKEN='sizning_tokeningiz'"
        )

    await db.init_db()

    bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(router)

    setup_scheduler(bot)

    logger.info("Bot ishga tushdi. To'xtatish uchun Ctrl+C bosing.")
    try:
        await dp.start_polling(bot)
    finally:
        await db.close_db()


if __name__ == "__main__":
    asyncio.run(main())
