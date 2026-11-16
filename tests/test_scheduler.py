from datetime import date, datetime, time
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramForbiddenError, TelegramNetworkError
from aiogram.methods import SendMessage

from birthday_bot.scheduler import check_and_notify

TZ = ZoneInfo("Asia/Tashkent")
G = -100


class FakeBot:
    def __init__(self, fail_chats=(), admins=(), error=TelegramForbiddenError):
        self.messages: list[tuple[int, str]] = []
        self.stickers: list[tuple[int, str]] = []
        self.fail_chats = set(fail_chats)
        self.admins = set(admins)
        self.error = error

    async def get_chat_member(self, chat_id, user_id):
        status = ChatMemberStatus.CREATOR if user_id in self.admins else ChatMemberStatus.MEMBER
        return SimpleNamespace(status=status, is_member=True)

    async def send_message(self, chat_id, text):
        if chat_id in self.fail_chats:
            raise self.error(method=SendMessage(chat_id=chat_id, text=text), message="Forbidden")
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


async def test_failed_send_notifies_managers_once_a_day(db):
    await db.upsert_group(G, "Oila")
    await db.add_birthday(G, "Ali", 1, 5)
    await db.add_manager(G, 5)
    await db.link_user(1, G)  # admin — xabar oladi
    await db.link_user(7, G)  # oddiy a'zo — xabar olmaydi
    # Bu test xato haqidagi xabarni tekshiradi — ertalabki xabar aralashmasin
    await db.mark_digest_sent(G, date(2026, 5, 1))
    bot = FakeBot(fail_chats={G}, admins={1})
    failures = set()
    for minute in range(3):
        await check_and_notify(bot, db, datetime(2026, 5, 1, 8, minute, tzinfo=TZ), failures)
    assert sorted(chat for chat, _ in bot.messages) == [1, 5]
    assert "Oila" in bot.messages[0][1] and "⚠️" in bot.messages[0][1]

    # Ertasi kuni yana muammo bo'lsa — yana bir marta xabar beriladi
    await db.add_birthday(G, "Vali", 2, 5)
    await db.mark_digest_sent(G, date(2026, 5, 2))
    await check_and_notify(bot, db, datetime(2026, 5, 2, 8, 0, tzinfo=TZ), failures)
    assert len(bot.messages) == 4


async def test_network_error_is_retried_without_alarming_managers(db):
    # Internet uzilishi guruh muammosi emas — keyingi daqiqada qayta uriniladi
    await db.upsert_group(G, "Oila")
    await db.add_birthday(G, "Ali", 1, 5)
    await db.add_manager(G, 5)
    await db.mark_digest_sent(G, date(2026, 5, 1))
    failures = set()
    offline = FakeBot(fail_chats={G}, error=TelegramNetworkError)
    await check_and_notify(offline, db, datetime(2026, 5, 1, 8, 0, tzinfo=TZ), failures)
    assert offline.messages == []

    online = FakeBot()
    await check_and_notify(online, db, datetime(2026, 5, 1, 8, 1, tzinfo=TZ), failures)
    assert [chat for chat, _ in online.messages] == [G]


async def test_custom_greeting_template_is_used(db):
    await db.add_birthday(G, "Ali", 1, 5)
    await db.set_setting(G, "greeting_template", "Muborak bo'lsin, {ism}!")
    bot = FakeBot()
    await check_and_notify(bot, db, datetime(2026, 5, 1, 8, 0, tzinfo=TZ))
    assert bot.messages == [(G, "Muborak bo'lsin, <b>Ali</b>!")]


async def test_morning_digest_an_hour_before_greeting(db):
    await db.upsert_group(G, "Oila")
    await db.add_birthday(G, "Ali", 1, 5, 1970)  # bugun
    await db.add_birthday(G, "Vali", 2, 5)       # ertaga
    await db.add_manager(G, 5)
    await db.add_manager(G, 6)
    await db.set_digest_enabled(6, G, False)     # o'chirib qo'ygan
    bot = FakeBot()

    await check_and_notify(bot, db, datetime(2026, 5, 1, 6, 59, tzinfo=TZ))
    assert bot.messages == []
    await check_and_notify(bot, db, datetime(2026, 5, 1, 7, 0, tzinfo=TZ))
    assert [chat for chat, _ in bot.messages] == [5]
    text = bot.messages[0][1]
    assert "Oila" in text and "Ali" in text and "56 yosh" in text and "08:00" in text
    assert "Ertaga" in text and "Vali" in text

    await check_and_notify(bot, db, datetime(2026, 5, 1, 7, 1, tzinfo=TZ))
    assert len(bot.messages) == 1  # kuniga bir marta


async def test_no_digest_on_quiet_day(db):
    await db.upsert_group(G, "Oila")
    await db.add_birthday(G, "Ali", 20, 5)
    await db.add_manager(G, 5)
    bot = FakeBot()
    await check_and_notify(bot, db, datetime(2026, 5, 1, 7, 0, tzinfo=TZ))
    assert bot.messages == []
