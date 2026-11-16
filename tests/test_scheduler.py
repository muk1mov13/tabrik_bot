from datetime import datetime, time
from zoneinfo import ZoneInfo

from aiogram.exceptions import TelegramForbiddenError
from aiogram.methods import SendMessage

from birthday_bot.scheduler import check_and_notify

TZ = ZoneInfo("Asia/Tashkent")
G = -100


class FakeBot:
    def __init__(self, fail_chats=()):
        self.messages: list[tuple[int, str]] = []
        self.stickers: list[tuple[int, str]] = []
        self.fail_chats = set(fail_chats)

    async def send_message(self, chat_id, text):
        if chat_id in self.fail_chats:
            raise TelegramForbiddenError(method=SendMessage(chat_id=chat_id, text=text), message="Forbidden")
        self.messages.append((chat_id, text))

    async def send_sticker(self, chat_id, sticker):
        self.stickers.append((chat_id, sticker))


async def test_greets_once_with_sticker(db):
    await db.add_birthday(G, "Ali", 1, 5, 2000)
    await db.set_setting(G, "sticker_file_id", "STK")
    bot = FakeBot()

    await check_and_notify(bot, db, datetime(2026, 5, 1, 7, 59, tzinfo=TZ))
    assert bot.messages == []

    await check_and_notify(bot, db, datetime(2026, 5, 1, 8, 0, tzinfo=TZ))
    await check_and_notify(bot, db, datetime(2026, 5, 1, 8, 1, tzinfo=TZ))
    assert len(bot.messages) == 1
    assert "Ali" in bot.messages[0][1] and "26 yoshga" in bot.messages[0][1]
    assert bot.stickers == [(G, "STK")]


async def test_failed_send_is_retried(db):
    await db.add_birthday(G, "Ali", 1, 5)
    failing = FakeBot(fail_chats={G})
    await check_and_notify(failing, db, datetime(2026, 5, 1, 8, 0, tzinfo=TZ))
    assert failing.messages == []

    bot = FakeBot()
    await check_and_notify(bot, db, datetime(2026, 5, 1, 8, 1, tzinfo=TZ))
    assert len(bot.messages) == 1


async def test_reminder_sent_once(db):
    await db.add_birthday(G, "Ali", 4, 5)
    await db.set_setting(G, "remind_days", 3)
    await db.set_setting(G, "notify_time", time(9, 0))
    bot = FakeBot()

    for minute in range(3):
        await check_and_notify(bot, db, datetime(2026, 5, 1, 9, minute, tzinfo=TZ))
    assert len(bot.messages) == 1
    assert "3 kundan keyin" in bot.messages[0][1]
