from datetime import date

import pytest

from birthday_bot.parsing import (
    ParsedBirthday,
    ParseError,
    parse_birthday,
    parse_bulk,
    parse_date,
    parse_edit,
    parse_group_payload,
    parse_invite_payload,
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


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Adolatxon 27 may 2021", ParsedBirthday("Adolatxon", 27, 5, 2021)),
        ("Usmonbek 29 noyabr 2022", ParsedBirthday("Usmonbek", 29, 11, 2022)),
        ("Hamdamov Muqim bobom 24 mart", ParsedBirthday("Hamdamov Muqim bobom", 24, 3)),
        ("Ali 29-noyabr 2022-yil", ParsedBirthday("Ali", 29, 11, 2022)),
        ("Ali 1 Sentyabr 1990 yil", ParsedBirthday("Ali", 1, 9, 1990)),
        ("Алишер 1 февраль 2000", ParsedBirthday("Алишер", 1, 2, 2000)),
        ("Вали 9 мая", ParsedBirthday("Вали", 9, 5)),
        ("15 mart", ParsedBirthday(None, 15, 3)),
    ],
)
def test_parse_birthday_month_names(text, expected):
    assert parse_birthday(text, TODAY) == expected


def test_parse_birthday_unknown_month():
    with pytest.raises(ParseError, match="Oy"):
        parse_birthday("Ali 15 martobr", TODAY)
    with pytest.raises(ParseError, match="mavjud emas"):
        parse_birthday("Ali 31 iyun", TODAY)


def test_parse_bulk():
    text = """
    Adolatxon 27 may 2021
    • Usmonbek 29 noyabr 2022
    2) Alibek 19.12.2022

    Salimaxon 31 fevral 2025
    Faqat ism
    """
    result = parse_bulk(text, TODAY)
    assert [e.name for e in result.entries] == ["Adolatxon", "Usmonbek", "Alibek"]
    assert [line for line, _ in result.errors] == ["Salimaxon 31 fevral 2025", "Faqat ism"]
    # Sanasiz qator ism bo'lishi kerak — bunda ism yo'q
    assert parse_bulk("27 may 2021", TODAY).errors[0][1] == "Ism ko'rsatilmagan."


def test_parse_invite_payload():
    assert parse_invite_payload("m_AbC-d_12345") == "AbC-d_12345"
    for bad in ["m_", "m_short", "g_-100", "m_bad token!", ""]:
        assert parse_invite_payload(bad) is None
