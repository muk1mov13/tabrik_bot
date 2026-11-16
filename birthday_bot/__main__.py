"""
Botni ishga tushirish:
    cp .env.example .env   # va qiymatlarni to'ldiring
    python -m birthday_bot
"""

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramUnauthorizedError

from birthday_bot.config import ConfigError, load_config
from birthday_bot.database import Database
from birthday_bot.handlers import build_router
from birthday_bot.scheduler import setup_scheduler

logger = logging.getLogger("birthday_bot")


async def main():
    config = load_config()

    db = Database(config.database_path, config.notify_time)
    await db.connect()
    logger.info("Baza: %s", config.database_path.resolve())

    bot = Bot(token=config.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    # db va config har bir handlerga argument sifatida uzatiladi
    dp = Dispatcher(db=db, config=config)
    dp.include_router(build_router())

    scheduler = setup_scheduler(bot, db, config)

    logger.info("Bot ishga tushdi. To'xtatish uchun Ctrl+C bosing.")
    try:
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()
        await db.close()


def run():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    # Har daqiqalik job loglari journalni to'ldirib yubormasligi uchun
    logging.getLogger("apscheduler").setLevel(logging.WARNING)
    try:
        asyncio.run(main())
    except ConfigError as exc:
        logger.error("%s", exc)
        sys.exit(1)
    except TelegramUnauthorizedError:
        logger.error("BOT_TOKEN noto'g'ri yoki bekor qilingan — @BotFather dan tekshiring.")
        sys.exit(1)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    run()
