from datetime import date, time

import pytest

from birthday_bot.dates import (
    birthday_in_year,
    birthday_keys_for,
    calc_age,
    next_birthday,
    parse_time,
    validate_date,
)

TODAY = date(2026, 11, 16)


@pytest.mark.parametrize(
    "day, month, year",
    [(15, 3, None), (15, 3, 1998), (29, 2, None), (29, 2, 2000), (31, 12, 1900), (16, 11, 2026)],
)
def test_validate_date_ok(day, month, year):
    assert validate_date(day, month, year, TODAY) is None


@pytest.mark.parametrize(
    "day, month, year",
    [(31, 2, None), (29, 2, 2023), (0, 5, None), (15, 13, None), (1, 1, 1899), (1, 1, 2027), (17, 11, 2026)],
)
def test_validate_date_rejects(day, month, year):
    assert validate_date(day, month, year, TODAY) is not None


def test_birthday_in_year_leap_day():
    assert birthday_in_year(29, 2, 2025) == date(2025, 2, 28)
    assert birthday_in_year(29, 2, 2024) == date(2024, 2, 29)
    assert birthday_in_year(15, 3, 2025) == date(2025, 3, 15)


def test_next_birthday():
    assert next_birthday(15, 3, date(2026, 3, 15)) == date(2026, 3, 15)
    assert next_birthday(15, 3, date(2026, 3, 16)) == date(2027, 3, 15)
    assert next_birthday(29, 2, date(2026, 1, 1)) == date(2026, 2, 28)
    assert next_birthday(29, 2, date(2027, 3, 1)) == date(2028, 2, 29)


def test_birthday_keys_for():
    assert birthday_keys_for(date(2025, 2, 28)) == [(28, 2), (29, 2)]
    assert birthday_keys_for(date(2024, 2, 28)) == [(28, 2)]
    assert birthday_keys_for(date(2024, 2, 29)) == [(29, 2)]


def test_calc_age():
    assert calc_age(1998, date(2026, 3, 15)) == 28


@pytest.mark.parametrize(
    "value, expected",
    [("08:00", time(8, 0)), ("9:30", time(9, 30)), ("23:59", time(23, 59))],
)
def test_parse_time_ok(value, expected):
    assert parse_time(value) == expected


@pytest.mark.parametrize("value", ["", "8", "24:00", "12:60", "12:5", "ab:cd"])
def test_parse_time_rejects(value):
    assert parse_time(value) is None
