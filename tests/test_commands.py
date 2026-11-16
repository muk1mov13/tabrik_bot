from aiogram.exceptions import TelegramNetworkError
from aiogram.methods import SetMyCommands
from aiogram.types import BotCommandScopeAllGroupChats, BotCommandScopeAllPrivateChats

from birthday_bot.commands import set_bot_commands


class FakeBot:
    def __init__(self, fail=False):
        self.calls = []
        self.fail = fail

    async def set_my_commands(self, commands, scope):
        if self.fail:
            raise TelegramNetworkError(method=SetMyCommands(commands=commands), message="offline")
        self.calls.append(([c.command for c in commands], type(scope)))


async def test_set_bot_commands():
    bot = FakeBot()
    await set_bot_commands(bot)
    assert bot.calls == [
        (["menu", "help"], BotCommandScopeAllPrivateChats),
        (["upcoming", "list", "find", "menu", "help"], BotCommandScopeAllGroupChats),
    ]


async def test_set_bot_commands_survives_network_error():
    await set_bot_commands(FakeBot(fail=True))  # xato tashlamaydi
