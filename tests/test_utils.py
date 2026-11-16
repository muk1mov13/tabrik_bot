from datetime import date, time

import pytest

from utils import (
    ADD_ARGS_PATTERN,
    birthday_in_year,
    birthday_keys_for,
    calc_age,
    escape_like,
    mention,
    next_birthday,
    parse_time,
    today,
    validate_date,
)


@pytest.mark.parametrize(
    "day, month, year",
    [(15, 3, None), (15, 3, 1998), (29, 2, None), (29, 2, 2000), (31, 12, 1900)],
)
def test_validate_date_ok(day, month, year):
    assert validate_date(day, month, year) is None


@pytest.mark.parametrize(
    "day, month, year",
    [
        (31, 2, None),
        (29, 2, 2023),
        (0, 5, None),
        (15, 13, None),
        (1, 1, 1899),
        (1, 1, today().year + 1),
    ],
)
def test_validate_date_rejects(day, month, year):
    assert validate_date(day, month, year) is not None


def test_birthday_in_year_leap_day():
    assert birthday_in_year(29, 2, 2025) == date(2025, 2, 28)
    assert birthday_in_year(29, 2, 2024) == date(2024, 2, 29)
    assert birthday_in_year(15, 3, 2025) == date(2025, 3, 15)


def test_birthday_keys_for():
    assert birthday_keys_for(date(2025, 2, 28)) == [(28, 2), (29, 2)]
    assert birthday_keys_for(date(2024, 2, 28)) == [(28, 2)]
    assert birthday_keys_for(date(2024, 2, 29)) == [(29, 2)]


def test_calc_age():
    assert calc_age(1998, date(2026, 3, 15)) == 28


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Ali 15.03", ("Ali", "15", "03", None)),
        ("Ali Valiyev 5.3.1998", ("Ali Valiyev", "5", "3", "1998")),
        ("Ali  Valiyev   01.01", ("Ali  Valiyev", "01", "01", None)),
        ("15.03", (None, "15", "03", None)),
        ("15.03.1998", (None, "15", "03", "1998")),
    ],
)
def test_add_args_pattern(text, expected):
    m = ADD_ARGS_PATTERN.match(text)
    assert m is not None
    assert (m["name"], m["day"], m["month"], m["year"]) == expected


@pytest.mark.parametrize("text", ["", "Ali", "Ali15.03", "Ali 15/03", "Ali 15.03.98"])
def test_add_args_pattern_rejects(text):
    assert ADD_ARGS_PATTERN.match(text) is None


def test_next_birthday():
    assert next_birthday(15, 3, date(2026, 3, 15)) == date(2026, 3, 15)
    assert next_birthday(15, 3, date(2026, 3, 16)) == date(2027, 3, 15)
    assert next_birthday(29, 2, date(2026, 1, 1)) == date(2026, 2, 28)
    assert next_birthday(29, 2, date(2027, 3, 1)) == date(2028, 2, 29)


@pytest.mark.parametrize(
    "value, expected",
    [("08:00", time(8, 0)), ("9:30", time(9, 30)), ("23:59", time(23, 59))],
)
def test_parse_time_ok(value, expected):
    assert parse_time(value) == expected


@pytest.mark.parametrize("value", ["", "8", "24:00", "12:60", "12:5", "ab:cd"])
def test_parse_time_rejects(value):
    assert parse_time(value) is None


def test_mention():
    assert mention("<Ali>") == "&lt;Ali&gt;"
    assert mention("Ali", 42) == '<a href="tg://user?id=42">Ali</a>'


def test_escape_like():
    assert escape_like(r"50%_a\b") == r"50\%\_a\\b"
