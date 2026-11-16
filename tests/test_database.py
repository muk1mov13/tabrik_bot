from datetime import date, time

from birthday_bot.database import Database
from birthday_bot.models import GroupSettings

G = -100


async def test_migrations_are_idempotent(tmp_path):
    path = tmp_path / "sub" / "bot.db"
    for _ in range(2):
        database = Database(path, time(8, 0))
        await database.connect()
        await database.add_birthday(G, "Ali", 1, 1)
        await database.close()
    database = Database(path, time(8, 0))
    await database.connect()
    assert await database.count_birthdays(G) == 2
    await database.close()


async def test_crud(db):
    a = await db.add_birthday(G, "Ali", 15, 3, 1998, added_by=1)
    b = await db.add_birthday(G, "vali", 1, 1)
    await db.add_birthday(-200, "Boshqa", 1, 1)

    assert [x.name for x in await db.list_birthdays(G)] == ["vali", "Ali"]
    assert await db.count_birthdays(G) == 2
    assert [x.id for x in await db.list_birthdays(G, limit=1, offset=1)] == [a]

    assert await db.update_birthday(G, a, "Ali V", 16, 3, None)
    assert not await db.update_birthday(-200, a, "x", 1, 1, None)  # boshqa guruh
    updated = await db.get_birthday(G, a)
    assert (updated.name, updated.day, updated.year) == ("Ali V", 16, None)

    assert await db.remove_birthday(G, b)
    assert not await db.remove_birthday(G, b)
    assert await db.get_birthday(G, b) is None


async def test_find_is_case_insensitive_and_literal(db):
    await db.add_birthday(G, "Алишер", 1, 1)
    await db.add_birthday(G, "ALI", 2, 1)
    await db.add_birthday(G, "50% chegirma", 3, 1)
    assert [b.name for b in await db.find_birthdays(G, "али")] == ["Алишер"]
    assert [b.name for b in await db.find_birthdays(G, "ali")] == ["ALI"]
    assert [b.name for b in await db.find_birthdays(G, "%")] == ["50% chegirma"]


async def test_upcoming_wraps_year_and_leap_day(db):
    await db.add_birthday(G, "Yangi yil", 2, 1)
    await db.add_birthday(G, "Kabisa", 29, 2)
    await db.add_birthday(G, "Uzoq", 1, 6)
    items = await db.get_upcoming(G, date(2026, 12, 30), 7)
    assert [(i.birthday.name, i.days_left) for i in items] == [("Yangi yil", 3)]
    items = await db.get_upcoming(G, date(2027, 2, 27), 3)
    assert [(i.birthday.name, i.date) for i in items] == [("Kabisa", date(2027, 2, 28))]


async def test_pending_greetings_respect_time_and_mark(db):
    d = date(2027, 2, 28)
    await db.add_birthday(G, "Ali", 28, 2)
    await db.add_birthday(G, "Kabisa", 29, 2)
    await db.add_birthday(G, "Ertaga", 1, 3)
    other = await db.add_birthday(-200, "Boshqa", 28, 2)
    await db.set_setting(-200, "notify_time", time(10, 0))
    await db.set_setting(G, "sticker_file_id", "STK")

    assert await db.get_pending_greetings(d, time(7, 59)) == []
    pending = await db.get_pending_greetings(d, time(8, 0))
    assert sorted((b.name, s) for b, s in pending) == [("Ali", "STK"), ("Kabisa", "STK")]

    for b, _ in pending:
        await db.mark_notified(b.id, d)
    assert await db.get_pending_greetings(d, time(9, 0)) == []
    assert [b.id for b, _ in await db.get_pending_greetings(d, time(10, 0))] == [other]
    # Ertasi kuni yana yuboriladi
    assert await db.get_pending_greetings(date(2028, 2, 28), time(8, 0))


async def test_pending_reminders(db):
    await db.add_birthday(G, "Ali", 1, 3)
    await db.add_birthday(-200, "O'chiq", 1, 3)  # bu guruhda eslatma yoqilmagan
    assert await db.get_pending_reminders(date(2027, 2, 26), time(8, 0)) == []

    await db.set_setting(G, "remind_days", 3)
    items = await db.get_pending_reminders(date(2027, 2, 26), time(8, 0))
    assert [(i.birthday.name, i.date, i.days_left) for i in items] == [("Ali", date(2027, 3, 1), 3)]

    await db.mark_reminded(items[0].birthday.id, date(2027, 2, 26))
    assert await db.get_pending_reminders(date(2027, 2, 26), time(8, 0)) == []
    assert await db.get_pending_reminders(date(2027, 2, 26), time(7, 0)) == []


async def test_edit_clears_marks(db):
    d = date(2027, 5, 1)
    a = await db.add_birthday(G, "Ali", 1, 5)
    await db.mark_notified(a, d)
    await db.update_birthday(G, a, "Ali", 1, 5, None)
    assert len(await db.get_pending_greetings(d, time(8, 0))) == 1


async def test_settings_defaults_and_upsert(db):
    assert await db.get_settings(G) == GroupSettings(notify_time=time(8, 0))
    await db.set_setting(G, "remind_days", 3)
    await db.set_setting(G, "notify_time", time(9, 30))
    await db.set_setting(G, "sticker_file_id", "STK")
    await db.set_setting(G, "sticker_file_id", None)
    assert await db.get_settings(G) == GroupSettings(
        notify_time=time(9, 30), remind_days=3, upcoming_days=7, sticker_file_id=None
    )


async def test_migrate_group(db):
    await db.add_birthday(G, "Ali", 1, 1)
    await db.set_setting(G, "remind_days", 5)
    await db.migrate_group(G, -1009)
    assert await db.count_birthdays(G) == 0
    assert await db.count_birthdays(-1009) == 1
    assert (await db.get_settings(-1009)).remind_days == 5
