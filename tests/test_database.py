from datetime import date, time

from birthday_bot.database import Database
from birthday_bot.models import Group, GroupSettings

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
    await db.upsert_group(G, "Oila")
    await db.link_user(1, G)
    await db.add_manager(G, 5)
    await db.migrate_group(G, -1009)
    assert await db.count_birthdays(G) == 0
    assert await db.count_birthdays(-1009) == 1
    assert (await db.get_settings(-1009)).remind_days == 5
    assert (await db.get_group(-1009)).title == "Oila"
    assert [g.group_id for g in await db.linked_groups(1)] == [-1009]
    assert await db.list_managers(-1009) == [5]


async def test_groups_and_admins(db):
    assert await db.get_group(G) is None
    await db.upsert_group(G, "Oila")
    await db.upsert_group(-200, "Boshqa")
    await db.upsert_group(G, "Oila 2")
    assert await db.get_group(G) == Group(group_id=G, title="Oila 2", active=True)

    await db.link_user(1, G)
    await db.link_user(1, G)  # takror — xato bermaydi
    await db.link_user(1, -200)
    await db.link_user(2, G)
    assert [g.title for g in await db.linked_groups(1)] == ["Boshqa", "Oila 2"]

    await db.set_group_active(-200, False)
    assert [g.group_id for g in await db.linked_groups(1)] == [G]
    await db.unlink_user(1, G)
    assert await db.linked_groups(1) == []
    assert [g.group_id for g in await db.linked_groups(2)] == [G]


async def test_set_group_active_for_unknown_group(db):
    await db.set_group_active(-300, False)
    assert await db.get_group(-300) == Group(group_id=-300, title="", active=False)


async def test_inactive_groups_are_skipped(db):
    d = date(2027, 5, 1)
    await db.add_birthday(G, "Ali", 1, 5)
    await db.add_birthday(G, "Vali", 4, 5)
    await db.set_setting(G, "remind_days", 3)
    await db.set_group_active(G, False)
    assert await db.get_pending_greetings(d, time(8, 0)) == []
    assert await db.get_pending_reminders(d, time(8, 0)) == []

    await db.upsert_group(G, "Oila")
    assert len(await db.get_pending_greetings(d, time(8, 0))) == 1
    assert len(await db.get_pending_reminders(d, time(8, 0))) == 1


async def test_managers(db):
    assert not await db.is_manager(G, 5)
    await db.add_manager(G, 5, added_by=1)
    await db.add_manager(G, 5, added_by=1)  # takror — xato bermaydi
    await db.add_manager(G, 6)
    await db.add_manager(-200, 7)
    assert await db.is_manager(G, 5)
    assert await db.list_managers(G) == [5, 6]
    assert await db.remove_manager(G, 5)
    assert not await db.remove_manager(G, 5)
    assert await db.list_managers(G) == [6]


async def test_linked_users(db):
    await db.link_user(5, G)
    await db.link_user(3, G)
    await db.link_user(5, -200)
    assert await db.linked_users(G) == [3, 5]


async def test_birthday_by_user_and_same_name(db):
    await db.add_birthday(G, "Karim Aka", 1, 1)
    b = await db.add_birthday(G, "Sardor", 2, 2, user_id=77)
    await db.add_birthday(-200, "Sardor", 2, 2, user_id=77)
    assert (await db.get_birthday_by_user(G, 77)).id == b
    assert await db.get_birthday_by_user(G, 78) is None
    assert [x.name for x in await db.find_same_name(G, "  karim   aka ")] == ["Karim Aka"]
    assert await db.find_same_name(G, "Karim") == []


async def test_greeting_template_setting(db):
    assert (await db.get_settings(G)).greeting_template is None
    await db.set_setting(G, "greeting_template", "Tabriklaymiz, {ism}!")
    assert (await db.get_settings(G)).greeting_template == "Tabriklaymiz, {ism}!"


async def test_set_birthday_user(db):
    a = await db.add_birthday(G, "Ali", 1, 1)
    assert await db.set_birthday_user(G, a, 77)
    assert (await db.get_birthday(G, a)).user_id == 77
    assert not await db.set_birthday_user(-200, a, 78)  # boshqa guruh


async def test_manager_invites(db):
    d = date(2026, 11, 16)
    token = await db.create_invite(G, created_by=1, today=d)
    other = await db.create_invite(G, created_by=1, today=d)
    assert token != other and len(token) >= 10

    assert await db.use_invite("yo'q", 5, d) is None
    assert await db.use_invite(token, 5, d) == (G, 1)
    assert await db.use_invite(token, 6, d) is None  # bir martalik
    # 7 kundan keyin eskiradi
    assert await db.use_invite(other, 6, date(2026, 11, 24)) is None


async def test_digest_settings_and_due(db):
    d = date(2026, 5, 1)
    await db.upsert_group(G, "Oila")                 # tabrik 08:00 (default) → xabar 07:00
    await db.upsert_group(-200, "Ish")
    await db.set_setting(-200, "notify_time", time(10, 0))
    await db.upsert_group(-300, "Eski")
    await db.set_group_active(-300, False)
    await db.set_setting(-400, "notify_time", time(0, 30))  # 00:30 → 00:00 (kun boshidan oldin emas)
    await db.upsert_group(-400, "Tun")

    assert [g.group_id for g in await db.get_digest_due(d, time(6, 59))] == [-400]
    assert [g.group_id for g in await db.get_digest_due(d, time(7, 0))] == [-400, G]
    await db.mark_digest_sent(G, d)
    assert [g.group_id for g in await db.get_digest_due(d, time(9, 0))] == [-400, -200]
    assert G in [g.group_id for g in await db.get_digest_due(date(2026, 5, 2), time(7, 0))]

    await db.link_user(5, G)
    assert await db.get_digest_enabled(5, G)
    await db.set_digest_enabled(5, G, False)
    assert not await db.get_digest_enabled(5, G)
    assert await db.get_digest_enabled(99, G)  # bog'lanmagan — standart yoqilgan


async def test_peek_invite_does_not_consume(db):
    d = date(2026, 11, 16)
    token = await db.create_invite(G, created_by=1, today=d)
    assert await db.peek_invite(token, d) == G
    assert await db.peek_invite(token, d) == G
    await db.use_invite(token, 5, d)
    assert await db.peek_invite(token, d) is None
    assert await db.peek_invite("yo'q", d) is None
