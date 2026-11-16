from datetime import time

from birthday_bot.keyboards import (
    Menu,
    RecordAction,
    group_invite_keyboard,
    main_menu_keyboard,
    records_keyboard,
    settings_keyboard,
)
from birthday_bot.models import Birthday, GroupSettings

G = -100123


def flat(markup):
    return [b for row in markup.inline_keyboard for b in row]


def texts(markup):
    return [b.text for b in flat(markup)]


def test_group_invite_keyboard():
    (button,) = flat(group_invite_keyboard("MyBot", G))
    assert button.url == "https://t.me/MyBot?start=g_-100123"


def test_main_menu_keyboard():
    assert "🔄 Guruhni almashtirish" not in texts(main_menu_keyboard(G, False))
    kb = main_menu_keyboard(G, True)
    assert texts(kb) == [
        "➕ Qo'shish", "📋 Ro'yxat", "⚙️ Sozlamalar", "👥 Boshqaruvchilar", "🔄 Guruhni almashtirish",
    ]
    assert Menu.unpack(flat(kb)[0].callback_data) == Menu(action="add", group_id=G)


def test_records_keyboard_navigation():
    items = [Birthday(id=i, group_id=G, name=f"Odam {i}", day=1, month=1) for i in range(3)]
    assert texts(records_keyboard(G, items, 0, 2)) == [
        "Odam 0 — 1 Yanvar", "Odam 1 — 1 Yanvar", "Odam 2 — 1 Yanvar", "➡️", "🏠 Menyu",
    ]
    last = texts(records_keyboard(G, items, 1, 2))
    assert "⬅️" in last and "➡️" not in last
    single = texts(records_keyboard(G, items, 0, 1))
    assert "⬅️" not in single and "➡️" not in single
    action = RecordAction.unpack(flat(records_keyboard(G, items, 1, 2))[2].callback_data)
    assert action == RecordAction(action="show", group_id=G, record_id=2, page=1)


def test_settings_keyboard_marks_selection():
    kb = texts(settings_keyboard(G, GroupSettings(notify_time=time(9, 0), remind_days=3)))
    assert "✅ 09:00" in kb and "08:00" in kb and "✅ 3 kun" in kb and "🔕 O'chiq" in kb
    assert "✍️ Boshqa vaqt" in kb
    custom = texts(settings_keyboard(G, GroupSettings(notify_time=time(9, 30))))
    assert "✅ ✍️ Boshqa vaqt (09:30)" in custom and "✅ 🔕 O'chiq" in custom


def test_callback_data_fits_telegram_limit():
    data = RecordAction(action="delyes", group_id=-1001234567890, record_id=10**9, page=999).pack()
    assert len(data.encode()) <= 64
