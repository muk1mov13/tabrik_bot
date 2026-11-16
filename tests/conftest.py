from datetime import time

import pytest

from birthday_bot.database import Database


@pytest.fixture
async def db():
    database = Database(":memory:", default_notify_time=time(8, 0))
    await database.connect()
    yield database
    await database.close()
