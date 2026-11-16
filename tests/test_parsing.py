from datetime import date

import pytest

from birthday_bot.parsing import (
    ParsedBirthday,
    ParseError,
    parse_birthday,
    parse_date,
    parse_edit,
    parse_group_payload,
    parse_name,
)

TODAY = date(2026, 11, 16)


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Ali 15.03", ParsedBirthday("Ali", 15, 3)),
        ("Ali  Valiyev   5.3.1998", ParsedBirthday("Ali Valiyev", 5, 3, 1998)),
        ("15.03", ParsedBirthday(None, 15, 3)),
        ("  15.03.1998 ", ParsedBirthday(None, 15, 3, 1998)),
        ("Алишер 29.02", ParsedBirthday("Алишер", 29, 2)),
    ],
)
def test_parse_birthday(text, expected):
    assert parse_birthday(text, TODAY) == expected


@pytest.mark.parametrize(
    "text",
    ["", "Ali", "Ali15.03", "Ali 15/03", "Ali 15.03.98", "Ali 31.02", "x" * 65 + " 01.01", "Ali 01.01.2030"],
)
def test_parse_birthday_rejects(text):
    with pytest.raises(ParseError):
        parse_birthday(text, TODAY)


def test_parse_edit():
    assert parse_edit("3 Vali 01.02.2000", TODAY) == (3, ParsedBirthday("Vali", 1, 2, 2000))
    assert parse_edit("12 01.02", TODAY) == (12, ParsedBirthday(None, 1, 2))
    for bad in ["", "3", "abc 01.02", "3 31.02"]:
        with pytest.raises(ParseError):
            parse_edit(bad, TODAY)


def test_parse_name():
    assert parse_name("  Karim   aka ") == "Karim aka"
    with pytest.raises(ParseError, match="bo'sh"):
        parse_name("   ")
    with pytest.raises(ParseError, match="64"):
        parse_name("a" * 65)


def test_parse_date():
    assert parse_date("15.03.1980", TODAY) == ParsedBirthday(None, 15, 3, 1980)
    assert parse_date(" 1.1 ", TODAY) == ParsedBirthday(None, 1, 1)
    for bad in ["Ali 15.03", "15/03", "", "31.02", "bugun"]:
        with pytest.raises(ParseError):
            parse_date(bad, TODAY)


def test_parse_group_payload():
    assert parse_group_payload("g_-100123") == -100123
    assert parse_group_payload("g_5") == 5
    for bad in ["x_1", "g_", "g_1a", "", "-100123"]:
        assert parse_group_payload(bad) is None
