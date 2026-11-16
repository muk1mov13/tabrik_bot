"""
Handlerlarni Dispatcher orqali soxta Telegram sessiyasi bilan tekshirish:
buyruqlar parse qilinadi, admin tekshiruvi ishlaydi, javoblar yuboriladi.
"""

from datetime import datetime, time, timedelta
from itertools import count
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

import pytest
from aiogram import Bot, Dispatcher
from aiogram.client.session.base import BaseSession
from aiogram.exceptions import TelegramBadRequest, TelegramMigrateToChat
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
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    SharedUser,
    Sticker,
    Update,
    User,
    UsersShared,
)

from birthday_bot.config import Config
from birthday_bot.handlers import build_router
from birthday_bot.keyboards import (
    Cancel,
    Menu,
    RecordAction,
    RemoveManager,
    SaveBulk,
    SaveNew,
    SelfAction,
    SetRemind,
)
from birthday_bot.models import Group

G, G2 = -100123, -100456
OLD_G = -555  # supergroupga aylangan eski guruh ID'si (yangisi — G)
GONE_G = -404  # bot chiqarilgan yoki o'chirilgan guruh
ADMIN, MEMBER, OUTSIDER = 1, 2, 3
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
            if method.user_id == OUTSIDER:
                return ChatMemberLeft(user=user)
            return ChatMemberMember(user=user)
        if isinstance(method, GetChat):
            if method.chat_id == OLD_G:
                raise TelegramMigrateToChat(
                    method=method, message="group upgraded", migrate_to_chat_id=G
                )
            if method.chat_id == GONE_G:
                raise TelegramBadRequest(method=method, message="chat not found")
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


def membership_update(old: str, new: str, by: int = ADMIN) -> Update:
    """Botning guruhdagi holati o'zgarishi ("left" yoki "member")."""
    bot_user = User(id=42, is_bot=True, first_name="Bot")

    def member(status: str):
        return ChatMemberLeft(user=bot_user) if status == "left" else ChatMemberMember(user=bot_user)

    return Update(
        update_id=next(_ids),
        my_chat_member=ChatMemberUpdated(
            chat=Chat(id=G, type="supergroup", title="Oila"),
            from_user=user(by),
            date=datetime.now(),
            old_chat_member=member(old),
            new_chat_member=member(new),
        ),
    )


def buttons(markup: Optional[InlineKeyboardMarkup]) -> dict[str, str]:
    """Tugma matni → callback_data (yoki URL)."""
    if not isinstance(markup, InlineKeyboardMarkup):
        return {}
    return {b.text: b.callback_data or b.url for row in markup.inline_keyboard for b in row}


async def admin_in_group(db):
    await db.upsert_group(G, "Oila")
    await db.link_user(ADMIN, G)


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
        "🎂 Tug'ilgan kun qo'shish": f"https://t.me/MyBot?start=g_{G}"
    }
    assert await db.get_group(G) == Group(group_id=G, title="Oila", active=True)

    # Holat o'zgarsa-yu, bot guruhda qolsa — qayta salomlashmaydi
    assert await send(update=membership_update("member", "member")) == []

    assert await send(update=membership_update("member", "left")) == []
    assert (await db.get_group(G)).active is False


async def test_group_menu_command(send, db):
    (reply,) = await send("/menu")
    assert "Salom" in reply
    assert "🎂 Tug'ilgan kun qo'shish" in buttons(send.session.last_markup())
    assert await db.get_group(G) is not None
    (reply,) = await send("/start")
    assert "Salom" in reply


async def test_deep_link_admin_gets_menu(send, db):
    await db.upsert_group(G, "Oila")
    (reply,) = await send(f"/start g_{G}", chat_type="private")
    assert "Oila" in reply
    assert list(buttons(send.session.last_markup())) == [
        "➕ Qo'shish", "📋 Ro'yxat", "⚙️ Sozlamalar", "👥 Boshqaruvchilar",
    ]
    assert [g.group_id for g in await db.linked_groups(ADMIN)] == [G]
    # Keyingi safar havolasiz ham menyu ochiladi
    (reply,) = await send("/start", chat_type="private")
    assert "Oila" in reply


async def test_deep_link_unknown_group_fetches_title(send, db):
    (reply,) = await send(f"/start g_{G}", chat_type="private")
    assert "Oila" in reply
    assert (await db.get_group(G)).title == "Oila"


async def test_deep_link_member_gets_own_menu(send, db):
    await db.upsert_group(G, "Oila")
    (reply,) = await send(f"/start g_{G}", from_id=MEMBER, chat_type="private")
    assert "Oila" in reply
    assert list(buttons(send.session.last_markup())) == ["🎂 Tug'ilgan kunimni qo'shish"]
    assert [g.group_id for g in await db.linked_groups(MEMBER)] == [G]


async def test_deep_link_outsider_rejected(send, db):
    await db.upsert_group(G, "Oila")
    (reply,) = await send(f"/start g_{G}", from_id=OUTSIDER, chat_type="private")
    assert "a'zosi emassiz" in reply
    assert await db.linked_groups(OUTSIDER) == []


async def test_start_without_groups_explains(send):
    (reply,) = await send("/start", chat_type="private")
    assert "guruhingizga qo'shing" in reply
    (reply,) = await send("/start g_xyz", chat_type="private")
    assert "guruhingizga qo'shing" in reply


async def test_many_groups_choose_and_switch(send, db):
    await db.upsert_group(G, "Oila")
    await db.upsert_group(G2, "Ish")
    await db.link_user(ADMIN, G)
    await db.link_user(ADMIN, G2)
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


async def test_left_group_unlinks(send, db):
    await db.upsert_group(G, "Oila")
    await db.link_user(OUTSIDER, G)
    (reply,) = await send("/start", from_id=OUTSIDER, chat_type="private")
    assert "guruhingizga qo'shing" in reply
    assert await db.linked_groups(OUTSIDER) == []


async def test_forged_callback_rejected(send, db):
    await db.upsert_group(G, "Oila")
    assert await send.click(Menu(action="add", group_id=G).pack(), from_id=MEMBER) == []
    alert = send.session.last_alert()
    assert alert.show_alert and "⛔" in alert.text


async def test_add_flow(send, db):
    await admin_in_group(db)
    question, hint = await send.click(Menu(action="add", group_id=G).pack())
    assert "Ismini yozing" in question and "Telegram'dan" in hint
    accepted, question = await send("  Karim   aka ", chat_type="private")
    assert "Karim aka" in accepted and "Sanasi?" in question
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
    texts = await send.click(Cancel(group_id=G).pack())
    assert "Nima qilamiz?" in texts[-1]
    # "Telegram'dan tanlash" klaviaturasi yopiladi
    assert any(
        isinstance(r, SendMessage) and isinstance(r.reply_markup, ReplyKeyboardRemove)
        for r in send.session.requests
    )
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


async def test_manage_list_edit_delete(send, db):
    await admin_in_group(db)
    a = await db.add_birthday(G, "Ali", 15, 3, 1990)
    (reply,) = await send.click(Menu(action="list", group_id=G).pack())
    assert "(1 ta)" in reply
    (reply,) = await send.click(buttons(send.session.last_markup())["Ali — 15 Mart"])
    assert "15 Mart 1990" in reply
    card = buttons(send.session.last_markup())

    await send.click(card["✏️ Ismni o'zgartirish"])
    (reply,) = await send("Ali aka", chat_type="private")
    assert "Saqlandi" in reply and "Ali aka" in reply

    await send.click(card["📅 Sanani o'zgartirish"])
    (reply,) = await send("bugun", chat_type="private")
    assert "❗" in reply
    (reply,) = await send("16.03", chat_type="private")
    assert "16 Mart" in reply
    b = await db.get_birthday(G, a)
    assert (b.name, b.day, b.month, b.year) == ("Ali aka", 16, 3, None)

    (reply,) = await send.click(card["🗑 O'chirish"])
    assert "rostdan" in reply
    (reply,) = await send.click(buttons(send.session.last_markup())["Ha, o'chirish"])
    assert "O'chirildi" in reply and "Hali hech kim" in reply
    assert await db.count_birthdays(G) == 0


async def test_manage_pagination_and_other_group(send, db):
    await admin_in_group(db)
    for i in range(12):
        await db.add_birthday(G, f"Odam {i:02}", 1 + i, 1)
    other = await db.add_birthday(G2, "Begona", 1, 1)
    await send.click(Menu(action="list", group_id=G).pack())
    kb = buttons(send.session.last_markup())
    assert "Odam 09 — 10 Yanvar" in kb and "Odam 10 — 11 Yanvar" not in kb
    await send.click(kb["➡️"])
    assert "Odam 11 — 12 Yanvar" in buttons(send.session.last_markup())

    # Boshqa guruh yozuviga o'z guruhi ID'si orqali tegib bo'lmaydi
    (reply,) = await send.click(
        RecordAction(action="delyes", group_id=G, record_id=other).pack()
    )
    assert "endi yo'q" in reply
    assert await db.get_birthday(G2, other) is not None


async def test_settings_menu(send, db):
    await admin_in_group(db)
    (reply,) = await send.click(Menu(action="settings", group_id=G).pack())
    assert "08:00" in reply
    kb = buttons(send.session.last_markup())
    assert "✅ 08:00" in kb and "✅ 🔕 O'chiq" in kb

    (reply,) = await send.click(kb["09:00"])
    assert "09:00" in reply
    assert (await db.get_settings(G)).notify_time == time(9, 0)
    await send.click(kb["3 kun"])
    assert (await db.get_settings(G)).remind_days == 3

    await send.click(kb["✍️ Boshqa vaqt"])
    (reply,) = await send("25:00", chat_type="private")
    assert "❗" in reply
    (reply,) = await send("09:30", chat_type="private")
    assert "09:30" in reply
    assert (await db.get_settings(G)).notify_time == time(9, 30)


async def test_settings_menu_forged_by_member(send, db):
    await db.upsert_group(G, "Oila")
    assert await send.click(SetRemind(group_id=G, days=7).pack(), from_id=MEMBER) == []
    assert (await db.get_settings(G)).remind_days == 0


async def test_manager_can_use_commands(send, db):
    await db.add_manager(G, MEMBER)
    (reply,) = await send("/add Ali 15.03", from_id=MEMBER)
    assert "Qo'shildi" in reply
    (reply,) = await send("/settings remind 3", from_id=MEMBER)
    assert "3 kun oldin" in reply


async def test_member_who_adds_bot_becomes_manager(send, db):
    (reply,) = await send(update=membership_update("left", "member", by=MEMBER))
    assert 'tg://user?id=2' in reply and "boshqaradi" in reply
    assert await db.is_manager(G, MEMBER)
    assert await db.linked_users(G) == [MEMBER]
    # Admin bo'lmasa ham menyu ochiladi
    (reply,) = await send(f"/start g_{G}", from_id=MEMBER, chat_type="private")
    assert "Nima qilamiz?" in reply


async def test_admin_appoints_and_removes_manager(send, db):
    target = message("salom", from_id=77, from_name="Sardor")
    (reply,) = await send("/manager", reply_to=target)
    assert "Sardor" in reply and "boshqaradi" in reply
    assert await db.is_manager(G, 77)

    (reply,) = await send("/manager off", reply_to=target)
    assert "boshqaruvchi emas" in reply
    assert not await db.is_manager(G, 77)

    (reply,) = await send("/manager")
    assert "reply" in reply

    (reply,) = await send("/manager", from_id=MEMBER, reply_to=target)
    assert "⛔" in reply
    assert not await db.is_manager(G, 77)


async def test_managers_list_admin_removes(send, db):
    await admin_in_group(db)
    await db.add_manager(G, MEMBER)
    (reply,) = await send.click(Menu(action="home", group_id=G).pack())
    menu = buttons(send.session.last_markup())
    (reply,) = await send.click(menu["👥 Boshqaruvchilar"])
    assert 'tg://user?id=2' in reply and "/manager" in reply
    (reply,) = await send.click(buttons(send.session.last_markup())["🗑 U"])
    assert not await db.is_manager(G, MEMBER)
    assert "Hali boshqaruvchi yo'q" in reply


async def test_manager_sees_list_but_cannot_remove(send, db):
    await db.upsert_group(G, "Oila")
    await db.add_manager(G, MEMBER)
    await db.add_manager(G, 77)
    (reply,) = await send.click(Menu(action="managers", group_id=G).pack(), from_id=MEMBER)
    assert 'tg://user?id=77' in reply
    assert not any(t.startswith("🗑") for t in buttons(send.session.last_markup()))
    assert await send.click(RemoveManager(group_id=G, user_id=77).pack(), from_id=MEMBER) == []
    assert await db.is_manager(G, 77)


async def test_member_adds_and_manages_own_birthday(send, db):
    await db.upsert_group(G, "Oila")
    (reply,) = await send.click(SelfAction(action="add", group_id=G).pack(), from_id=MEMBER)
    assert "Tug'ilgan kuningiz qachon?" in reply
    (reply,) = await send("15.03.1990", from_id=MEMBER, chat_type="private")
    assert "15 Mart 1990" in reply
    (reply,) = await send.click(buttons(send.session.last_markup())["✅ Saqlash"], from_id=MEMBER)
    assert "Saqlandi" in reply
    assert "📅 Sanani o'zgartirish" in buttons(send.session.last_markup())
    b = await db.get_birthday_by_user(G, MEMBER)
    assert (b.name, b.day, b.month, b.year) == ("User", 15, 3, 1990)

    # Sanani o'zgartirish yangi yozuv qo'shmaydi
    await send.click(SelfAction(action="date", group_id=G).pack(), from_id=MEMBER)
    await send("16.03", from_id=MEMBER, chat_type="private")
    await send.click(SelfAction(action="save", group_id=G).pack(), from_id=MEMBER)
    assert await db.count_birthdays(G) == 1
    assert (await db.get_birthday_by_user(G, MEMBER)).day == 16

    (reply,) = await send.click(SelfAction(action="del", group_id=G).pack(), from_id=MEMBER)
    assert "o'chirilsinmi" in reply
    (reply,) = await send.click(SelfAction(action="delyes", group_id=G).pack(), from_id=MEMBER)
    assert "o'chirildi" in reply
    assert await db.count_birthdays(G) == 0


async def test_member_cannot_touch_others(send, db):
    await db.upsert_group(G, "Oila")
    other = await db.add_birthday(G, "Boshqa", 1, 1, user_id=77)
    await send.click(SelfAction(action="delyes", group_id=G).pack(), from_id=MEMBER)
    assert await db.get_birthday(G, other) is not None
    assert await send.click(SelfAction(action="add", group_id=G).pack(), from_id=OUTSIDER) == []


async def test_add_flow_pick_telegram_user(send, db):
    await admin_in_group(db)
    await send.click(Menu(action="add", group_id=G).pack())
    markup = send.session.last_markup()
    assert isinstance(markup, ReplyKeyboardMarkup)
    (button,) = [b for row in markup.keyboard for b in row]
    assert button.request_users.max_quantity == 1 and not button.request_users.user_is_bot

    shared = UsersShared(
        request_id=1, users=[SharedUser(user_id=77, first_name="Sardor", last_name="Aka")]
    )
    accepted, question = await send(None, users_shared=shared, chat_type="private")
    assert 'tg://user?id=77' in accepted and "Sanasi?" in question
    await send("05.05", chat_type="private")
    await send.click(SaveNew().pack())
    (b,) = await db.list_birthdays(G)
    assert (b.name, b.user_id) == ("Sardor Aka", 77)


async def test_add_flow_warns_about_duplicate(send, db):
    await admin_in_group(db)
    await db.add_birthday(G, "Karim aka", 1, 2)
    await send.click(Menu(action="add", group_id=G).pack())
    await send("karim  AKA", chat_type="private")
    (reply,) = await send("15.03", chat_type="private")
    assert "allaqachon bor" in reply and "1 Fevral" in reply


async def test_member_warned_about_unlinked_record_with_same_name(send, db):
    await db.upsert_group(G, "Oila")
    await db.add_birthday(G, "User", 1, 2)  # admin ism bilan qo'shgan, belgilanmagan
    await send.click(SelfAction(action="add", group_id=G).pack(), from_id=MEMBER)
    (reply,) = await send("15.03", from_id=MEMBER, chat_type="private")
    assert "allaqachon bor" in reply


async def test_deep_link_old_group_id_follows_migration(send, db):
    await db.upsert_group(OLD_G, "Oila")
    await db.add_birthday(OLD_G, "Ali", 1, 1)
    (reply,) = await send(f"/start g_{OLD_G}", chat_type="private")
    assert "Nima qilamiz?" in reply
    assert await db.count_birthdays(G) == 1
    assert [g.group_id for g in await db.linked_groups(ADMIN)] == [G]


async def test_deep_link_unknown_group(send, db):
    (reply,) = await send(f"/start g_{GONE_G}", chat_type="private")
    assert "topilmadi" in reply
    assert await db.linked_groups(ADMIN) == []


async def test_add_flow_bulk_list(send, db):
    await admin_in_group(db)
    await db.add_birthday(G, "Alibek", 19, 12, 2022)
    await send.click(Menu(action="add", group_id=G).pack())
    accepted, preview = await send(
        "Adolatxon 27 may 2021\nUsmonbek 29 noyabr 2022\nAlibek 19 dekabr 2022\n"
        "Salimaxon 1 fevral 2025\nnoto'g'ri qator",
        chat_type="private",
    )
    assert "Qo'shiladi (4 ta)" in preview and "Tushunilmadi (1 ta)" in preview
    assert "allaqachon bor" in preview
    (reply,) = await send.click(buttons(send.session.last_markup())["✅ Hammasini saqlash (4)"])
    assert "4 ta" in reply
    assert await db.count_birthdays(G) == 5
    # Qayta bosish ikkinchi marta qo'shmaydi
    assert await send.click(SaveBulk().pack()) == []
    assert "eskirgan" in send.session.last_alert().text
    assert await db.count_birthdays(G) == 5
    usmon = (await db.find_same_name(G, "Usmonbek"))[0]
    assert (usmon.day, usmon.month, usmon.year) == (29, 11, 2022)


async def test_add_flow_single_line_with_date_skips_date_question(send, db):
    await admin_in_group(db)
    await send.click(Menu(action="add", group_id=G).pack())
    accepted, preview = await send("Karim aka 15 mart 1980", chat_type="private")
    assert "Qo'shiladi (1 ta)" in preview and "15 Mart 1980" in preview


async def test_add_flow_bulk_all_invalid_stays_on_name(send, db):
    await admin_in_group(db)
    await send.click(Menu(action="add", group_id=G).pack())
    (reply,) = await send("bir\nikki", chat_type="private")
    assert "Tushunilmadi (2 ta)" in reply
    accepted, question = await send("Karim", chat_type="private")
    assert "Sanasi?" in question


async def test_manager_menu_shows_upcoming(send, db, config):
    await admin_in_group(db)
    today = datetime.now(config.timezone).date()
    soon = today + timedelta(days=2)
    await db.add_birthday(G, "Karim aka", soon.day, soon.month)
    (reply,) = await send("/menu", chat_type="private")
    assert "Yaqin kunlarda" in reply and "Karim aka" in reply
