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
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.methods import (
    AnswerCallbackQuery,
    EditMessageText,
    GetChat,
    GetChatMember,
    GetMe,
    SendMessage,
    TelegramMethod,
)
from aiogram.types import (
    CallbackQuery,
    Chat,
    ChatFullInfo,
    ChatMemberLeft,
    ChatMemberMember,
    ChatMemberOwner,
    ChatMemberUpdated,
    InlineKeyboardMarkup,
    Message,
    Sticker,
    Update,
    User,
)

from birthday_bot.config import Config
from birthday_bot.handlers import build_router
from birthday_bot.keyboards import (
    Cancel,
    Menu,
    RecordAction,
    SaveNew,
    SetRemind,
)
from birthday_bot.models import Group

G, G2 = -100123, -100456
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
        if isinstance(method, GetChat):
            return ChatFullInfo(
                id=method.chat_id, type="supergroup", title="Oila",
                accent_color_id=0, max_reaction_count=0,
            )
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

    def last_markup(self) -> Optional[InlineKeyboardMarkup]:
        for r in reversed(self.requests):
            if isinstance(r, (SendMessage, EditMessageText)):
                return r.reply_markup
        return None

    def last_alert(self) -> Optional[AnswerCallbackQuery]:
        alerts = [r for r in self.requests if isinstance(r, AnswerCallbackQuery)]
        return alerts[-1] if alerts else None


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
    chat_type: str = "supergroup",
    **kw,
) -> Message:
    chat_id = from_id if chat_type == "private" else G
    return Message(
        message_id=next(_ids),
        date=datetime.now(),
        chat=Chat(id=chat_id, type=chat_type),
        from_user=user(from_id, from_name),
        text=text,
        reply_to_message=reply_to,
        **kw,
    )


def callback_update(data: str, from_id: int = ADMIN) -> Update:
    """Shaxsiy chatdagi menyu xabarida tugma bosilishi."""
    return Update(
        update_id=next(_ids),
        callback_query=CallbackQuery(
            id=str(next(_ids)),
            from_user=user(from_id),
            chat_instance="ci",
            message=message("menyu", from_id=from_id, chat_type="private"),
            data=data,
        ),
    )


def membership_update(old: str, new: str) -> Update:
    """Botning guruhdagi holati o'zgarishi ("left" yoki "member")."""
    bot_user = User(id=42, is_bot=True, first_name="Bot")

    def member(status: str):
        return ChatMemberLeft(user=bot_user) if status == "left" else ChatMemberMember(user=bot_user)

    return Update(
        update_id=next(_ids),
        my_chat_member=ChatMemberUpdated(
            chat=Chat(id=G, type="supergroup", title="Oila"),
            from_user=user(ADMIN),
            date=datetime.now(),
            old_chat_member=member(old),
            new_chat_member=member(new),
        ),
    )


def buttons(markup: Optional[InlineKeyboardMarkup]) -> dict[str, str]:
    """Tugma matni → callback_data (yoki URL)."""
    if markup is None:
        return {}
    return {b.text: b.callback_data or b.url for row in markup.inline_keyboard for b in row}


async def admin_in_group(db):
    await db.upsert_group(G, "Oila")
    await db.link_admin(ADMIN, G)


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
    # Savol-javob holati testlar orasida o'tib ketmasligi uchun
    dispatcher.fsm.storage = MemoryStorage()

    async def _send(text=None, update: Optional[Update] = None, **kw) -> list[str]:
        session.requests.clear()
        update = update or Update(update_id=next(_ids), message=message(text, **kw))
        await dispatcher.feed_update(bot, update)
        return session.sent_texts()

    async def _click(data: str, from_id: int = ADMIN) -> list[str]:
        return await _send(update=callback_update(data, from_id))

    _send.session = session
    _send.click = _click
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


# ---------- Tugmali menyu ----------


async def test_bot_added_to_group_greets_and_registers(send, db):
    (reply,) = await send(update=membership_update("left", "member"))
    assert "Salom" in reply
    assert buttons(send.session.last_markup()) == {
        "➕ Tug'ilgan kun qo'shish": f"https://t.me/MyBot?start=g_{G}"
    }
    assert await db.get_group(G) == Group(group_id=G, title="Oila", active=True)

    # Holat o'zgarsa-yu, bot guruhda qolsa — qayta salomlashmaydi
    assert await send(update=membership_update("member", "member")) == []

    assert await send(update=membership_update("member", "left")) == []
    assert (await db.get_group(G)).active is False


async def test_group_menu_command(send, db):
    (reply,) = await send("/menu")
    assert "Salom" in reply
    assert "➕ Tug'ilgan kun qo'shish" in buttons(send.session.last_markup())
    assert await db.get_group(G) is not None
    (reply,) = await send("/start")
    assert "Salom" in reply


async def test_deep_link_admin_gets_menu(send, db):
    await db.upsert_group(G, "Oila")
    (reply,) = await send(f"/start g_{G}", chat_type="private")
    assert "Oila" in reply
    assert list(buttons(send.session.last_markup())) == ["➕ Qo'shish", "📋 Ro'yxat", "⚙️ Sozlamalar"]
    assert [g.group_id for g in await db.admin_groups(ADMIN)] == [G]
    # Keyingi safar havolasiz ham menyu ochiladi
    (reply,) = await send("/start", chat_type="private")
    assert "Oila" in reply


async def test_deep_link_unknown_group_fetches_title(send, db):
    (reply,) = await send(f"/start g_{G}", chat_type="private")
    assert "Oila" in reply
    assert (await db.get_group(G)).title == "Oila"


async def test_deep_link_non_admin_rejected(send, db):
    await db.upsert_group(G, "Oila")
    (reply,) = await send(f"/start g_{G}", from_id=MEMBER, chat_type="private")
    assert "admindan so'rang" in reply
    assert await db.admin_groups(MEMBER) == []


async def test_start_without_groups_explains(send):
    (reply,) = await send("/start", chat_type="private")
    assert "guruhingizga qo'shing" in reply
    (reply,) = await send("/start g_xyz", chat_type="private")
    assert "guruhingizga qo'shing" in reply


async def test_many_groups_choose_and_switch(send, db):
    await db.upsert_group(G, "Oila")
    await db.upsert_group(G2, "Ish")
    await db.link_admin(ADMIN, G)
    await db.link_admin(ADMIN, G2)
    (reply,) = await send("/menu", chat_type="private")
    assert "Qaysi guruh" in reply
    kb = buttons(send.session.last_markup())
    assert list(kb) == ["Ish", "Oila"]
    (reply,) = await send.click(kb["Oila"])
    assert "Oila" in reply
    menu = buttons(send.session.last_markup())
    assert "🔄 Guruhni almashtirish" in menu
    (reply,) = await send.click(menu["🔄 Guruhni almashtirish"])
    assert "Qaysi guruh" in reply


async def test_lost_admin_rights_unlinks(send, db):
    await db.upsert_group(G, "Oila")
    await db.link_admin(MEMBER, G)
    (reply,) = await send("/start", from_id=MEMBER, chat_type="private")
    assert "guruhingizga qo'shing" in reply
    assert await db.admin_groups(MEMBER) == []


async def test_forged_callback_rejected(send, db):
    await db.upsert_group(G, "Oila")
    assert await send.click(Menu(action="home", group_id=G).pack(), from_id=MEMBER) == []
    alert = send.session.last_alert()
    assert alert.show_alert and "⛔" in alert.text


async def test_add_flow(send, db):
    await admin_in_group(db)
    (reply,) = await send.click(Menu(action="add", group_id=G).pack())
    assert "Ismini yozing" in reply
    (reply,) = await send("  Karim   aka ", chat_type="private")
    assert "Sanasi?" in reply
    (reply,) = await send("31.02", chat_type="private")
    assert "mavjud emas" in reply and "Sanasi?" in reply
    (reply,) = await send("15.03.1980", chat_type="private")
    assert "Karim aka</b> — 15 Mart 1980" in reply
    (reply,) = await send.click(buttons(send.session.last_markup())["✅ Saqlash"])
    assert "Qo'shildi" in reply
    assert "➕ Yana qo'shish" in buttons(send.session.last_markup())
    (b,) = await db.list_birthdays(G)
    assert (b.name, b.day, b.month, b.year) == ("Karim aka", 15, 3, 1980)

    # Saqlangandan keyin tugma qayta bosilsa — ikkinchi yozuv qo'shilmaydi
    assert await send.click(SaveNew().pack()) == []
    assert "eskirgan" in send.session.last_alert().text
    assert await db.count_birthdays(G) == 1


async def test_add_flow_cancel_and_command_interrupt(send, db):
    await admin_in_group(db)
    await send.click(Menu(action="add", group_id=G).pack())
    (reply,) = await send.click(Cancel(group_id=G).pack())
    assert "Nima qilamiz?" in reply
    assert await send("Karim", chat_type="private") == []  # holat yo'q — e'tiborsiz

    await send.click(Menu(action="add", group_id=G).pack())
    (reply,) = await send("/help", chat_type="private")
    assert "/add" in reply
    assert await send("Karim", chat_type="private") == []
    assert await db.count_birthdays(G) == 0


async def test_add_flow_rejects_non_admin(send, db):
    await db.upsert_group(G, "Oila")
    assert await send.click(Menu(action="add", group_id=G).pack(), from_id=MEMBER) == []
    assert await send("Karim", from_id=MEMBER, chat_type="private") == []
