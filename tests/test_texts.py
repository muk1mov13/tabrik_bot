import random
from datetime import date, time

from birthday_bot.models import Birthday, GroupSettings, Upcoming
from birthday_bot.texts import (
    GREETINGS,
    add_preview,
    added_text,
    greeting,
    mention,
    menu_text,
    record_button_text,
    record_card,
    reminder,
    settings_menu_text,
    settings_text,
    split_messages,
)


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


def test_menu_and_add_texts_escape():
    assert "&lt;b&gt;" in menu_text("<b>")
    assert menu_text("").startswith("🏠 <b>Guruh</b>")
    assert add_preview("A<", 15, 3, 1980) == (
        "Tekshiring:\n<b>A&lt;</b> — 15 Mart 1980\n\nSaqlaymizmi?"
    )
    assert added_text("Ali", 15, 3, None) == "✅ Qo'shildi: <b>Ali</b> — 15 Mart"


def test_record_card():
    today = date(2026, 3, 10)
    card = record_card(make(name="Ali", day=15, month=3, year=1980), today)
    assert "15 Mart 1980" in card and "5 kundan keyin" in card and "46 yoshga" in card
    assert "bugun" in record_card(make(day=10, month=3), today)
    assert "Ali &lt;3" in record_card(make(day=10, month=3), today)
    # Tugma matni HTML emas — escape qilinmaydi
    assert record_button_text(make(day=1, month=5)) == "Ali <3 — 1 May"


def test_settings_menu_text():
    text = settings_menu_text(GroupSettings(notify_time=time(9, 0), remind_days=3))
    assert "09:00" in text and "3 kun oldin" in text
    assert "o'chirilgan" in settings_menu_text(GroupSettings(notify_time=time(9, 0)))


def test_add_preview_warns_about_duplicates():
    existing = make(name="Karim aka", day=1, month=2, year=None)
    text = add_preview("Karim aka", 15, 3, None, [existing])
    assert "⚠️ Ro'yxatda allaqachon bor" in text and "1 Fevral" in text
    assert "Baribir saqlaymizmi?" in text


def test_greetings_use_respectful_plural():
    # Odam haqida hurmat bilan — ko'plikda gapiriladi
    for i in range(len(GREETINGS)):
        text = greeting(make(year=1960), date(2026, 5, 1), random.Random(i))
        assert "tug'ilgan kunlari" in text and "66 yoshga to'ldilar" in text
    for template in GREETINGS:
        assert "kuni!" not in template and "Uni " not in template

    item = Upcoming(birthday=make(year=1960, day=4), date=date(2026, 5, 4), days_left=3)
    text = reminder(item)
    assert "tug'ilgan kunlari" in text and "yoshga to'ladilar" in text
