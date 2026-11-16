import random
from datetime import date, time

from birthday_bot.models import Birthday, GroupSettings, Upcoming
from birthday_bot.texts import greeting, mention, reminder, settings_text, split_messages


def make(**kw) -> Birthday:
    fields = {"id": 1, "group_id": -100, "name": "Ali <3", "day": 1, "month": 5}
    fields.update(kw)
    return Birthday(**fields)


def test_mention():
    assert mention("<Ali>") == "&lt;Ali&gt;"
    assert mention("Ali", 42) == '<a href="tg://user?id=42">Ali</a>'


def test_greeting_escapes_and_age():
    text = greeting(make(year=2000), date(2026, 5, 1), random.Random(0))
    assert "Ali &lt;3" in text
    assert "26 yoshga" in text


def test_greeting_mentions_user():
    assert 'href="tg://user?id=7"' in greeting(make(user_id=7), date(2026, 5, 1))


def test_reminder():
    item = Upcoming(birthday=make(year=2000, day=4), date=date(2026, 5, 4), days_left=3)
    text = reminder(item)
    assert "3 kundan keyin" in text
    assert "4 May" in text
    assert "26 yoshga" in text


def test_settings_text():
    text = settings_text(GroupSettings(notify_time=time(9, 5), remind_days=3))
    assert "09:05" in text
    assert "3 kun oldin" in text


def test_split_messages():
    lines = ["a" * 10] * 10
    chunks = split_messages(lines, limit=35)
    assert all(len(c) <= 35 for c in chunks)
    assert "\n".join(chunks).count("a") == 100
    assert split_messages([]) == []
