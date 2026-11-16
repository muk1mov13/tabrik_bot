from types import SimpleNamespace

from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramBadRequest, TelegramMigrateToChat
from aiogram.methods import GetChat, GetChatMember

from birthday_bot.permissions import Role, get_role, resolve_group

G = -100


class FakeBot:
    def __init__(self, status=None, is_member=True, chat_error=None):
        self.status = status
        self.is_member = is_member
        self.chat_error = chat_error

    async def get_chat_member(self, chat_id, user_id):
        if self.status is None:
            raise TelegramBadRequest(
                method=GetChatMember(chat_id=chat_id, user_id=user_id), message="chat not found"
            )
        return SimpleNamespace(status=self.status, is_member=self.is_member)

    async def get_chat(self, chat_id):
        if self.chat_error:
            raise self.chat_error
        return SimpleNamespace(id=chat_id, title="Oila")


async def test_get_role(db):
    assert await get_role(FakeBot(ChatMemberStatus.CREATOR), db, G, 1) == Role.ADMIN
    assert await get_role(FakeBot(ChatMemberStatus.ADMINISTRATOR), db, G, 1) == Role.ADMIN
    assert await get_role(FakeBot(ChatMemberStatus.MEMBER), db, G, 1) == Role.MEMBER
    assert await get_role(FakeBot(ChatMemberStatus.LEFT), db, G, 1) == Role.NONE
    assert await get_role(FakeBot(ChatMemberStatus.KICKED), db, G, 1) == Role.NONE
    assert await get_role(FakeBot(), db, G, 1) == Role.NONE  # Telegram xatosi

    restricted = ChatMemberStatus.RESTRICTED
    assert await get_role(FakeBot(restricted, is_member=True), db, G, 1) == Role.MEMBER
    assert await get_role(FakeBot(restricted, is_member=False), db, G, 1) == Role.NONE

    await db.add_manager(G, 1)
    assert await get_role(FakeBot(ChatMemberStatus.MEMBER), db, G, 1) == Role.MANAGER
    # Guruhdan chiqqan boshqaruvchi — ruxsat yo'q
    assert await get_role(FakeBot(ChatMemberStatus.LEFT), db, G, 1) == Role.NONE


async def test_resolve_group(db):
    assert await resolve_group(FakeBot(), db, G) == G

    await db.add_birthday(G, "Ali", 1, 1)
    migrated = TelegramMigrateToChat(
        method=GetChat(chat_id=G), message="group upgraded", migrate_to_chat_id=-1009
    )
    assert await resolve_group(FakeBot(chat_error=migrated), db, G) == -1009
    assert await db.count_birthdays(-1009) == 1

    missing = TelegramBadRequest(method=GetChat(chat_id=G), message="chat not found")
    assert await resolve_group(FakeBot(chat_error=missing), db, G) is None
