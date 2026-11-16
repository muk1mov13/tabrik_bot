from aiogram.exceptions import TelegramNetworkError
from aiogram.methods import SetMyCommands
from aiogram.types import BotCommandScopeAllGroupChats, BotCommandScopeAllPrivateChats

from birthday_bot.commands import set_bot_commands, set_bot_description
from birthday_bot.texts import BOT_DESCRIPTION, BOT_SHORT_DESCRIPTION


class FakeBot:
    def __init__(self, fail=False):
        self.calls = []
        self.fail = fail

    async def set_my_commands(self, commands, scope):
        if self.fail:
            raise TelegramNetworkError(method=SetMyCommands(commands=commands), message="offline")
        self.calls.append(([c.command for c in commands], type(scope)))

    async def set_my_description(self, description):
        if self.fail:
            raise TelegramNetworkError(method=SetMyCommands(commands=[]), message="offline")
        self.calls.append(("description", description))

    async def set_my_short_description(self, short_description):
        self.calls.append(("short", short_description))


async def test_set_bot_commands():
    bot = FakeBot()
    await set_bot_commands(bot)
    assert bot.calls == [
        (["menu", "help"], BotCommandScopeAllPrivateChats),
        (["upcoming", "list", "find", "menu", "help"], BotCommandScopeAllGroupChats),
    ]


async def test_set_bot_commands_survives_network_error():
    await set_bot_commands(FakeBot(fail=True))  # xato tashlamaydi


async def test_set_bot_description():
    bot = FakeBot()
    await set_bot_description(bot)
    assert bot.calls == [("description", BOT_DESCRIPTION), ("short", BOT_SHORT_DESCRIPTION)]
    # Telegram chegaralari: tavsif 512, qisqa tavsif 120 belgigacha
    assert len(BOT_DESCRIPTION) <= 512
    assert len(BOT_SHORT_DESCRIPTION) <= 120


async def test_set_bot_description_survives_network_error():
    await set_bot_description(FakeBot(fail=True))  # xato tashlamaydi
