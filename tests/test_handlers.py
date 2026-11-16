from datetime import date

from handlers import parse_birthday_args
from scheduler import build_greeting, build_reminder


def test_parse_birthday_args():
    assert parse_birthday_args("Ali  Valiyev 15.03.1998") == ("Ali Valiyev", 15, 3, 1998)
    assert parse_birthday_args("15.03") == (None, 15, 3, None)
    assert isinstance(parse_birthday_args("Ali 31.02"), str)
    assert isinstance(parse_birthday_args("x" * 65 + " 01.01"), str)
    assert isinstance(parse_birthday_args("Ali"), str)


def _row(**kw):
    row = {"id": 1, "group_id": -100, "name": "Ali <3", "user_id": None, "year": None}
    row.update(kw)
    return row


def test_build_greeting_escapes_and_age():
    text = build_greeting(_row(year=2000), date(2026, 5, 1))
    assert "Ali &lt;3" in text
    assert "26 yoshga" in text


def test_build_greeting_mentions_user():
    text = build_greeting(_row(user_id=7), date(2026, 5, 1))
    assert 'href="tg://user?id=7"' in text


def test_build_reminder():
    item = {"row": _row(year=2000), "date": date(2026, 5, 4), "days_left": 3}
    text = build_reminder(item)
    assert "3 kundan keyin" in text
    assert "4 May" in text
    assert "26 yoshga" in text
