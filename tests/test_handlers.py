"""
Handlerlarni Dispatcher orqali soxta Telegram sessiyasi bilan tekshirish:
buyruqlar parse qilinadi, admin tekshiruvi ishlaydi, javoblar yuboriladi.
"""

from datetime import datetime, time
from itertools import count
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

import pytest
from aiogram import Bot, Dispatcher
from aiogram.client.session.base import BaseSession
from aiogram.methods import (
    AnswerCallbackQuery,
    EditMessageText,
    GetChatMember,
    GetMe,
    SendMessage,
    TelegramMethod,
)
from aiogram.types import (
    CallbackQuery,
    Chat,
    ChatMemberMember,
    ChatMemberOwner,
    Message,
    Sticker,
    Update,
    User,
)

from birthday_bot.config import Config
from birthday_bot.handlers import build_router

G = -100123
ADMIN, MEMBER = 1, 2
_ids = count(1)


class MockSession(BaseSession):
    """Telegram API o'rniga: so'rovlarni yozib oladi va soxta javob qaytaradi."""

    def __init__(self):
        super().__init__()
        self.requests: list[TelegramMethod] = []

    async def make_request(self, bot, method, timeout=None):
        self.requests.append(method)
        if isinstance(method, GetMe):
            return User(id=42, is_bot=True, first_name="Bot", username="MyBot")
        if isinstance(method, GetChatMember):
            user = User(id=method.user_id, is_bot=False, first_name="U")
            if method.user_id == ADMIN:
                return ChatMemberOwner(user=user, is_anonymous=False)
            return ChatMemberMember(user=user)
        if isinstance(method, (SendMessage, EditMessageText)):
            return Message(
                message_id=next(_ids),
                date=datetime.now(),
                chat=Chat(id=method.chat_id or G, type="supergroup"),
                text=method.text,
            )
        return True

    async def close(self):
        pass

    async def stream_content(self, *args, **kwargs):
        raise NotImplementedError

    def sent_texts(self) -> list[str]:
        return [r.text for r in self.requests if isinstance(r, (SendMessage, EditMessageText))]


# Routerlar modul darajasida — Dispatcher bir marta yaratiladi
dispatcher = Dispatcher()
dispatcher.include_router(build_router())


def user(user_id: int, name: str = "User") -> User:
    return User(id=user_id, is_bot=False, first_name=name)


def message(
    text: Optional[str],
    from_id: int = ADMIN,
    reply_to: Optional[Message] = None,
    from_name: str = "User",
    **kw,
) -> Message:
    return Message(
        message_id=next(_ids),
        date=datetime.now(),
        chat=Chat(id=G, type="supergroup"),
        from_user=user(from_id, from_name),
        text=text,
        reply_to_message=reply_to,
        **kw,
    )


@pytest.fixture
def config():
    return Config(
        bot_token="42:TEST",
        database_path=Path(":memory:"),
        timezone=ZoneInfo("Asia/Tashkent"),
        notify_time=time(8, 0),
    )


@pytest.fixture
async def send(db, config):
    session = MockSession()
    bot = Bot("42:TEST", session=session)
    dispatcher["db"] = db
    dispatcher["config"] = config

    async def _send(text=None, update: Optional[Update] = None, **kw) -> list[str]:
        session.requests.clear()
        update = update or Update(update_id=next(_ids), message=message(text, **kw))
        await dispatcher.feed_update(bot, update)
        return session.sent_texts()

    _send.session = session
    return _send


async def test_help(send):
    (reply,) = await send("/help")
    assert "/add" in reply


async def test_add_list_edit_remove(send, db):
    (reply,) = await send("/add Ali Valiyev 15.03.1998")
    assert "Qo'shildi" in reply and "Ali Valiyev" in reply
    (b,) = await db.list_birthdays(G)

    (reply,) = await send("/add@MyBot Vali 01.01")
    assert "Qo'shildi" in reply

    (reply,) = await send("/list")
    assert "Ali Valiyev" in reply and "Vali" in reply and "(2 ta)" in reply

    (reply,) = await send(f"/edit {b.id} 16.03")
    assert "Yangilandi" in reply
    assert (await db.get_birthday(G, b.id)).day == 16

    (reply,) = await send(f"/remove {b.id}")
    assert "O'chirildi" in reply
    assert await db.count_birthdays(G) == 1


async def test_non_admin_cannot_modify(send, db):
    (reply,) = await send("/add Ali 15.03", from_id=MEMBER)
    assert "⛔" in reply
    assert await db.count_birthdays(G) == 0
    (reply,) = await send("/settings remind 3", from_id=MEMBER)
    assert "⛔" in reply
    # Ko'rish hammaga ochiq
    (reply,) = await send("/list", from_id=MEMBER)
    assert "qo'shilmagan" in reply


async def test_add_validation_and_escaping(send, db):
    (reply,) = await send("/add Ali 31.02")
    assert "mavjud emas" in reply
    (reply,) = await send("/add <b>Ali</b> 01.01")
    assert "&lt;b&gt;Ali&lt;/b&gt;" in reply
    assert (await db.list_birthdays(G))[0].name == "<b>Ali</b>"


async def test_add_by_reply_links_user(send, db):
    target = message("salom", from_id=77, from_name="Sardor")
    (reply,) = await send("/add 05.05", reply_to=target)
    assert 'tg://user?id=77' in reply
    (b,) = await db.list_birthdays(G)
    assert (b.name, b.user_id) == ("Sardor", 77)

    (reply,) = await send("/add 05.05")
    assert "Ism ko'rsatilmagan" in reply


async def test_find_and_upcoming(send, db):
    await db.add_birthday(G, "Алишер", 1, 1)
    (reply,) = await send("/find али")
    assert "Алишер" in reply
    (reply,) = await send("/find yo'q")
    assert "topilmadi" in reply
    (reply,) = await send("/upcoming")
    assert "Keyingi 7 kun" in reply or "Yaqin 7" in reply


async def test_settings_and_sticker(send, db):
    (reply,) = await send("/settings time 09:30")
    assert "09:30" in reply
    (reply,) = await send("/settings remind 3")
    assert "3 kun oldin" in reply
    (reply,) = await send("/settings upcoming 99")
    assert "❗" in reply
    (reply,) = await send("/settings")
    assert "09:30" in reply and "3 kun oldin" in reply

    sticker_msg = message(
        None,
        sticker=Sticker(
            file_id="STK1", file_unique_id="u", type="regular",
            width=1, height=1, is_animated=False, is_video=False,
        ),
    )
    (reply,) = await send("/setsticker", reply_to=sticker_msg)
    assert "saqlandi" in reply
    assert (await db.get_settings(G)).sticker_file_id == "STK1"


async def test_list_pagination(send, db):
    for i in range(25):
        await db.add_birthday(G, f"Odam {i:02}", 1 + i, 1)
    (reply,) = await send("/list")
    assert "(25 ta)" in reply and "Odam 19" in reply and "Odam 20" not in reply

    list_msg = message("x")
    callback = CallbackQuery(
        id="cb", from_user=user(MEMBER), chat_instance="ci", message=list_msg, data="list:1"
    )
    texts = await send(update=Update(update_id=next(_ids), callback_query=callback))
    assert "Odam 20" in texts[0] and "Odam 00" not in texts[0]
    assert any(isinstance(r, AnswerCallbackQuery) for r in send.session.requests)
