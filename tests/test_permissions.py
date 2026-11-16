from types import SimpleNamespace

from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import GetChatMember

from birthday_bot.permissions import is_admin

G = -100


class FakeBot:
    def __init__(self, status=None):
        self.status = status

    async def get_chat_member(self, chat_id, user_id):
        if self.status is None:
            raise TelegramBadRequest(
                method=GetChatMember(chat_id=chat_id, user_id=user_id), message="chat not found"
            )
        return SimpleNamespace(status=self.status)


async def test_is_admin():
    assert await is_admin(FakeBot(ChatMemberStatus.CREATOR), G, 1)
    assert await is_admin(FakeBot(ChatMemberStatus.ADMINISTRATOR), G, 1)
    assert not await is_admin(FakeBot(ChatMemberStatus.MEMBER), G, 1)
    assert not await is_admin(FakeBot(), G, 1)  # Telegram xatosi — ruxsat yo'q
