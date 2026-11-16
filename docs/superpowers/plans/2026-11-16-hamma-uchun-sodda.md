# Botni hamma uchun sodda qilish — amalga oshirish rejasi

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Guruh adminlari buyruq yodlamasdan, botning shaxsiy chatidagi tugmalar va savol-javob orqali tug'ilgan kunlarni qo'shishi, tahrirlashi, o'chirishi va sozlamalarni o'zgartirishi; bot har qanday guruhga qo'shilganda o'zini tanishtirishi.

**Architecture:** Bot guruhga qo'shilganda (`my_chat_member`) guruhni `groups` jadvaliga yozadi va deep-link tugma (`t.me/<bot>?start=g_<id>`) yuboradi. Admin tugmani bossa, shaxsiy chatda adminlik tekshiriladi va `group_admins` ga bog'lanish yoziladi. Menyu `CallbackData` tugmalari bilan ishlaydi (har bir bosishda adminlik qayta tekshiriladi), matn kiritish aiogram FSM (`MemoryStorage`) orqali. Eski buyruqlar o'zgarmaydi.

**Tech Stack:** Python 3.12, aiogram 3.13 (Router, CallbackData, FSM, BaseMiddleware), aiosqlite, pytest + pytest-asyncio (`asyncio_mode=auto`).

**Spec:** `docs/superpowers/specs/2026-11-16-hamma-uchun-sodda-design.md`

**Qoidalar (CLAUDE.md):** barcha foydalanuvchi matnlari, izohlar va docstringlar o'zbekcha (lotin). Foydalanuvchi matni HTML'da `mention()`/`escape()` orqali. "Bugun" faqat `dates.now(config.timezone)` orqali. Migratsiyalar faqat `MIGRATIONS` oxiriga qo'shiladi. `build_router()` bir jarayonda bir marta chaqiriladi.

---

## Fayllar xaritasi

| Fayl | Vazifa |
|---|---|
| `birthday_bot/models.py` (o'zgartirish) | `Group` dataclass |
| `birthday_bot/database.py` (o'zgartirish) | migratsiya 2, guruh/admin metodlari, nofaol guruhlarni o'tkazish |
| `birthday_bot/parsing.py` (o'zgartirish) | `parse_name`, `parse_date`, `parse_group_payload` |
| `birthday_bot/permissions.py` (o'zgartirish) | `is_admin` ajratiladi |
| `birthday_bot/texts.py` (o'zgartirish) | menyu matnlari |
| `birthday_bot/keyboards.py` (yangi) | `CallbackData` klasslari, tugma yasovchilar |
| `birthday_bot/handlers/ui.py` (yangi) | `ensure_admin`, `show`, `TEXT_INPUT`, `ClearStateOnCommand` |
| `birthday_bot/handlers/group_events.py` (yangi) | `my_chat_member`, guruhdagi `/menu`/`/start` |
| `birthday_bot/handlers/menu.py` (yangi) | shaxsiy `/start [g_<id>]`, `/menu`, guruh tanlash, bekor qilish |
| `birthday_bot/handlers/add_flow.py` (yangi) | qo'shish savol-javobi |
| `birthday_bot/handlers/manage.py` (yangi) | ro'yxat, karta, tahrirlash, o'chirish |
| `birthday_bot/handlers/settings_menu.py` (yangi) | sozlama tugmalari, "boshqa vaqt" |
| `birthday_bot/handlers/common.py` (o'zgartirish) | faqat `/help` |
| `birthday_bot/handlers/__init__.py` (o'zgartirish) | routerlar tartibi, middleware |
| `tests/test_keyboards.py`, `tests/test_permissions.py` (yangi) | unit testlar |
| `tests/test_database.py`, `tests/test_parsing.py`, `tests/test_texts.py`, `tests/test_handlers.py` (o'zgartirish) | testlar |
| `README.md`, `CLAUDE.md` (o'zgartirish) | hujjatlar |

---

### Task 1: `Group` modeli, migratsiya 2 va guruh/admin metodlari

**Files:**
- Modify: `birthday_bot/models.py`
- Modify: `birthday_bot/database.py`
- Test: `tests/test_database.py`

- [ ] **Step 1: Failing testlarni yozing**

`tests/test_database.py` boshidagi importlarni almashtiring:

```python
from datetime import date, time

from birthday_bot.database import Database
from birthday_bot.models import Group, GroupSettings
```

Fayl oxiridagi `test_migrate_group` ni to'liq almashtiring va yangi testlarni qo'shing:

```python
async def test_migrate_group(db):
    await db.add_birthday(G, "Ali", 1, 1)
    await db.set_setting(G, "remind_days", 5)
    await db.upsert_group(G, "Oila")
    await db.link_admin(1, G)
    await db.migrate_group(G, -1009)
    assert await db.count_birthdays(G) == 0
    assert await db.count_birthdays(-1009) == 1
    assert (await db.get_settings(-1009)).remind_days == 5
    assert (await db.get_group(-1009)).title == "Oila"
    assert [g.group_id for g in await db.admin_groups(1)] == [-1009]


async def test_groups_and_admins(db):
    assert await db.get_group(G) is None
    await db.upsert_group(G, "Oila")
    await db.upsert_group(-200, "Boshqa")
    await db.upsert_group(G, "Oila 2")
    assert await db.get_group(G) == Group(group_id=G, title="Oila 2", active=True)

    await db.link_admin(1, G)
    await db.link_admin(1, G)  # takror — xato bermaydi
    await db.link_admin(1, -200)
    await db.link_admin(2, G)
    assert [g.title for g in await db.admin_groups(1)] == ["Boshqa", "Oila 2"]

    await db.set_group_active(-200, False)
    assert [g.group_id for g in await db.admin_groups(1)] == [G]
    await db.unlink_admin(1, G)
    assert await db.admin_groups(1) == []
    assert [g.group_id for g in await db.admin_groups(2)] == [G]


async def test_set_group_active_for_unknown_group(db):
    await db.set_group_active(-300, False)
    assert await db.get_group(-300) == Group(group_id=-300, title="", active=False)
```

- [ ] **Step 2: Testlar yiqilishini tekshiring**

Run: `pytest tests/test_database.py -v`
Expected: FAIL — `ImportError: cannot import name 'Group'`

- [ ] **Step 3: `Group` modelini qo'shing**

`birthday_bot/models.py` oxiriga:

```python
@dataclass(frozen=True)
class Group:
    group_id: int
    title: str
    active: bool = True
```

- [ ] **Step 4: Migratsiya va metodlarni qo'shing**

`birthday_bot/database.py`:

Import qatorini almashtiring:

```python
from birthday_bot.models import Birthday, Group, GroupSettings, Upcoming
```

`MIGRATIONS` ro'yxatida 1-skriptdan keyin (ro'yxat yopilishidan oldin) qo'shing:

```python
    # 2 — bot turgan guruhlar va ularni boshqaradigan adminlar
    """
    CREATE TABLE groups (
        group_id INTEGER PRIMARY KEY,
        title TEXT NOT NULL DEFAULT '',
        active INTEGER NOT NULL DEFAULT 1
    );
    CREATE TABLE group_admins (
        user_id INTEGER NOT NULL,
        group_id INTEGER NOT NULL,
        PRIMARY KEY (user_id, group_id)
    );
    """,
```

`_to_birthday` dan keyin:

```python
def _to_group(row: aiosqlite.Row) -> Group:
    return Group(group_id=row["group_id"], title=row["title"], active=bool(row["active"]))
```

`migrate_group` ichidagi `_transaction()` blokining oxiriga qo'shing:

```python
            await self._execute(
                "UPDATE OR IGNORE groups SET group_id = ? WHERE group_id = ?", (new_id, old_id)
            )
            await self._execute(
                "UPDATE OR IGNORE group_admins SET group_id = ? WHERE group_id = ?",
                (new_id, old_id),
            )
```

Klass oxiriga (`set_setting` dan keyin) yangi bo'lim:

```python
    # ---------- Guruhlar va adminlar ----------

    async def upsert_group(self, group_id: int, title: str):
        """Guruhni saqlaydi (yoki nomini yangilaydi) va faol deb belgilaydi."""
        await self._execute(
            """
            INSERT INTO groups (group_id, title, active) VALUES (?, ?, 1)
            ON CONFLICT (group_id) DO UPDATE SET title = excluded.title, active = 1
            """,
            (group_id, title),
        )

    async def set_group_active(self, group_id: int, active: bool):
        await self._execute(
            """
            INSERT INTO groups (group_id, active) VALUES (?, ?)
            ON CONFLICT (group_id) DO UPDATE SET active = excluded.active
            """,
            (group_id, int(active)),
        )

    async def get_group(self, group_id: int) -> Optional[Group]:
        row = await self._fetchone("SELECT * FROM groups WHERE group_id = ?", (group_id,))
        return _to_group(row) if row else None

    async def link_admin(self, user_id: int, group_id: int):
        await self._execute(
            "INSERT OR IGNORE INTO group_admins (user_id, group_id) VALUES (?, ?)",
            (user_id, group_id),
        )

    async def unlink_admin(self, user_id: int, group_id: int):
        await self._execute(
            "DELETE FROM group_admins WHERE user_id = ? AND group_id = ?", (user_id, group_id)
        )

    async def admin_groups(self, user_id: int) -> list[Group]:
        """Foydalanuvchi bog'langan faol guruhlar (adminlik bu yerda tekshirilmaydi)."""
        rows = await self._fetchall(
            """
            SELECT g.* FROM group_admins a
            JOIN groups g ON g.group_id = a.group_id
            WHERE a.user_id = ? AND g.active = 1
            ORDER BY g.title COLLATE NOCASE, g.group_id
            """,
            (user_id,),
        )
        return [_to_group(row) for row in rows]
```

- [ ] **Step 5: Testlar o'tishini tekshiring**

Run: `pytest tests/test_database.py -v`
Expected: PASS (shu jumladan `test_migrations_are_idempotent`)

- [ ] **Step 6: Commit**

```bash
git add birthday_bot/models.py birthday_bot/database.py tests/test_database.py
git commit -m "Add groups and group_admins tables (migration 2)"
```

---

### Task 2: Nofaol guruhlarga tabrik/eslatma yubormaslik

**Files:**
- Modify: `birthday_bot/database.py` (`get_pending_greetings`, `get_pending_reminders`)
- Test: `tests/test_database.py`

- [ ] **Step 1: Failing test**

`tests/test_database.py` oxiriga:

```python
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
```

- [ ] **Step 2: Yiqilishini tekshiring**

Run: `pytest tests/test_database.py::test_inactive_groups_are_skipped -v`
Expected: FAIL — birinchi `assert` da ro'yxat bo'sh emas.

- [ ] **Step 3: So'rovlarni o'zgartiring**

`get_pending_greetings` dagi SQL ni almashtiring (`groups` da yozuvi bo'lmagan eski guruhlar faol hisoblanadi):

```python
        rows = await self._fetchall(
            f"""
            SELECT b.*, s.sticker_file_id
            FROM birthdays b
            LEFT JOIN group_settings s ON s.group_id = b.group_id
            LEFT JOIN groups g ON g.group_id = b.group_id
            WHERE {condition}
              AND COALESCE(g.active, 1) = 1
              AND b.last_notified IS NOT ?
              AND COALESCE(s.notify_time, ?) <= ?
            ORDER BY b.id
            """,
            (*params, on_date.isoformat(), self._default_time, format_time(at)),
        )
```

`get_pending_reminders` ichidagi tsikldagi SQL ni almashtiring:

```python
            rows = await self._fetchall(
                f"""
                SELECT b.* FROM birthdays b
                JOIN group_settings s ON s.group_id = b.group_id
                LEFT JOIN groups g ON g.group_id = b.group_id
                WHERE {condition}
                  AND COALESCE(g.active, 1) = 1
                  AND s.remind_days = ?
                  AND COALESCE(s.notify_time, ?) <= ?
                  AND b.last_reminded IS NOT ?
                ORDER BY b.id
                """,
                (*params, remind_days, self._default_time, at_text, on_date.isoformat()),
            )
```

`get_pending_greetings` docstringiga qator qo'shing: `Bot chiqarilgan (nofaol) guruhlar o'tkazib yuboriladi.`

- [ ] **Step 4: Testlar o'tishini tekshiring**

Run: `pytest tests/test_database.py tests/test_scheduler.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add birthday_bot/database.py tests/test_database.py
git commit -m "Skip greetings and reminders for groups the bot has left"
```

---

### Task 3: Ism, sana va deep-link payloadini tahlil qilish

**Files:**
- Modify: `birthday_bot/parsing.py`
- Test: `tests/test_parsing.py`

- [ ] **Step 1: Failing testlar**

`tests/test_parsing.py` dagi import qatorini almashtiring:

```python
from birthday_bot.parsing import (
    ParsedBirthday,
    ParseError,
    parse_birthday,
    parse_date,
    parse_edit,
    parse_group_payload,
    parse_name,
)
```

Fayl oxiriga:

```python
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
```

- [ ] **Step 2: Yiqilishini tekshiring**

Run: `pytest tests/test_parsing.py -v`
Expected: FAIL — `ImportError: cannot import name 'parse_date'`

- [ ] **Step 3: Funksiyalarni yozing**

`birthday_bot/parsing.py`:

Docstringni almashtiring:

```python
"""
parsing.py — Buyruq argumentlari va savol-javob javoblarini tahlil qilish.
"""
```

`EDIT_PATTERN` dan keyin:

```python
# /start payloadi: "g_<guruh ID>" (guruhdagi "➕ Qo'shish" tugmasidan)
GROUP_PAYLOAD_PATTERN = re.compile(r"^g_(?P<id>-?\d+)$")
```

`ParsedBirthday` dan keyin `parse_name` ni qo'shing va `parse_birthday` ni u orqali ishlating:

```python
def parse_name(text: str) -> str:
    """Ismdagi ortiqcha bo'shliqlarni olib tashlaydi va uzunligini tekshiradi."""
    name = " ".join(text.split())
    if not name:
        raise ParseError("Ism bo'sh bo'lmasligi kerak.")
    if len(name) > MAX_NAME_LENGTH:
        raise ParseError(f"Ism {MAX_NAME_LENGTH} belgidan oshmasligi kerak.")
    return name


def parse_birthday(text: str, today: date) -> ParsedBirthday:
    match = BIRTHDAY_PATTERN.match(text.strip())
    if not match:
        raise ParseError("Format noto'g'ri.")

    name = parse_name(match["name"]) if match["name"] else None
    day, month = int(match["day"]), int(match["month"])
    year = int(match["year"]) if match["year"] else None

    error = validate_date(day, month, year, today)
    if error:
        raise ParseError(error)
    return ParsedBirthday(name=name, day=day, month=month, year=year)


def parse_date(text: str, today: date) -> ParsedBirthday:
    """Faqat sana: '15.03' yoki '15.03.1998' (ism bo'lmasligi kerak)."""
    parsed = parse_birthday(text, today)
    if parsed.name:
        raise ParseError("Format noto'g'ri.")
    return parsed
```

Fayl oxiriga:

```python
def parse_group_payload(payload: str) -> Optional[int]:
    """/start dagi 'g_<guruh ID>' dan guruh ID'si, noto'g'ri bo'lsa None."""
    match = GROUP_PAYLOAD_PATTERN.match(payload.strip())
    return int(match["id"]) if match else None
```

- [ ] **Step 4: Testlar o'tishini tekshiring**

Run: `pytest tests/test_parsing.py tests/test_handlers.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add birthday_bot/parsing.py tests/test_parsing.py
git commit -m "Add parse_name, parse_date and parse_group_payload"
```

---

### Task 4: `is_admin` ni ajratish

**Files:**
- Modify: `birthday_bot/permissions.py`
- Create: `tests/test_permissions.py`

- [ ] **Step 1: Failing test**

`tests/test_permissions.py`:

```python
from types import SimpleNamespace

from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import GetChatMember

from birthday_bot.permissions import is_admin

G = -100


class FakeBot:
    def __init__(self, status=None):
        self.status = status

    async def get_chat_member(self, chat_id, user_id):
        if self.status is None:
            raise TelegramBadRequest(
                method=GetChatMember(chat_id=chat_id, user_id=user_id), message="chat not found"
            )
        return SimpleNamespace(status=self.status)


async def test_is_admin():
    assert await is_admin(FakeBot(ChatMemberStatus.CREATOR), G, 1)
    assert await is_admin(FakeBot(ChatMemberStatus.ADMINISTRATOR), G, 1)
    assert not await is_admin(FakeBot(ChatMemberStatus.MEMBER), G, 1)
    assert not await is_admin(FakeBot(), G, 1)  # Telegram xatosi — ruxsat yo'q
```

- [ ] **Step 2: Yiqilishini tekshiring**

Run: `pytest tests/test_permissions.py -v`
Expected: FAIL — `ImportError: cannot import name 'is_admin'`

- [ ] **Step 3: Refaktor**

`birthday_bot/permissions.py` da `target_group_id` dan keyin:

```python
async def is_admin(bot: Bot, group_id: int, user_id: int) -> bool:
    """Foydalanuvchi guruh admini yoki egasimi. Tekshirib bo'lmasa — False."""
    try:
        member = await bot.get_chat_member(group_id, user_id)
    except TelegramAPIError as exc:
        logger.warning("Adminlikni tekshirib bo'lmadi (guruh=%s): %s", group_id, exc)
        return False
    return member.status in ADMIN_STATUSES
```

`editable_group_id` ning oxirini (`if message.from_user is None:` dan boshlab) almashtiring:

```python
    if message.from_user is None:
        return None
    return group_id if await is_admin(bot, group_id, message.from_user.id) else None
```

- [ ] **Step 4: Testlar o'tishini tekshiring**

Run: `pytest tests/test_permissions.py tests/test_handlers.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add birthday_bot/permissions.py tests/test_permissions.py
git commit -m "Extract is_admin from editable_group_id"
```

---

### Task 5: Menyu matnlari

**Files:**
- Modify: `birthday_bot/texts.py`
- Test: `tests/test_texts.py`

- [ ] **Step 1: Failing testlar**

`tests/test_texts.py` dagi `from birthday_bot.texts import ...` qatorini almashtiring:

```python
from birthday_bot.texts import (
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
```

Fayl oxiriga:

```python
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
```

- [ ] **Step 2: Yiqilishini tekshiring**

Run: `pytest tests/test_texts.py -v`
Expected: FAIL — `ImportError: cannot import name 'add_preview'`

- [ ] **Step 3: Matnlarni yozing**

`birthday_bot/texts.py`:

Import qatorini almashtiring:

```python
from birthday_bot.dates import calc_age, format_time, next_birthday
```

`HELP_TEXT` dagi `"<b>Adminlar uchun:</b>\n"` qatoridan keyin yangi qator qo'shing:

```python
    "• <code>/menu</code> — tugmali menyu: qo'shish, ro'yxat, sozlamalar (eng oson yo'l)\n"
```

`SETTINGS_USAGE` dan keyin:

```python
WELCOME_TEXT = (
    "👋 Salom! Men shu guruhdagilarning tug'ilgan kunini eslab, "
    "o'z vaqtida tabriklayman 🎉\n\n"
    "Guruh adminlari pastdagi tugma orqali tug'ilgan kunlarni qo'shadi.\n"
    "Hamma uchun: /upcoming — yaqin tug'ilgan kunlar, /list — ro'yxat."
)
NOT_ADMIN_TEXT = (
    "⛔ Qo'shish faqat guruh adminlariga ruxsat etilgan. "
    "Tug'ilgan kuningizni qo'shishni admindan so'rang 🙂"
)
# Callback alert — oddiy matn (HTML emas), 200 belgigacha
NOT_ADMIN_ALERT = "⛔ Bu amal faqat guruh adminlariga ruxsat etilgan."
STALE_TEXT = "Bu menyu eskirgan. /menu ni bosing."
NO_GROUPS_TEXT = (
    "Hali birorta guruhingiz ulanmagan.\n\n"
    "1. Meni oila guruhingizga qo'shing.\n"
    "2. Guruhda <b>➕ Tug'ilgan kun qo'shish</b> tugmasini bosing "
    "(tugma ko'rinmasa, guruhda /menu yozing).\n\n"
    "Buni faqat guruh admini qila oladi."
)
CHOOSE_GROUP_TEXT = "Qaysi guruh bilan ishlaymiz?"
ASK_NAME_TEXT = "Kimning tug'ilgan kuni? Ismini yozing.\nMasalan: <i>Karim aka</i>"
ASK_DATE_TEXT = (
    "Sanasi? Masalan: <code>15.03</code> yoki <code>15.03.1980</code> (yili ixtiyoriy)"
)
ASK_NEW_NAME_TEXT = "Yangi ismni yozing:"
ASK_NEW_DATE_TEXT = "Yangi sanani yozing: <code>15.03</code> yoki <code>15.03.1980</code>"
ASK_TIME_TEXT = "Tabrik vaqtini yozing, masalan <code>09:30</code>"
EMPTY_LIST_TEXT = "Hali hech kim qo'shilmagan."
RECORD_GONE_TEXT = "Bu yozuv endi yo'q."
SAVED_TEXT = "✏️ Saqlandi."
```

`settings_text` dan keyin:

```python
def menu_text(title: str) -> str:
    return f"🏠 <b>{escape(title) or 'Guruh'}</b>\n\nNima qilamiz?"


def add_preview(name: str, day: int, month: int, year: Optional[int]) -> str:
    return (
        f"Tekshiring:\n<b>{escape(name)}</b> — {format_date(day, month, year)}\n\nSaqlaymizmi?"
    )


def added_text(name: str, day: int, month: int, year: Optional[int]) -> str:
    return f"✅ Qo'shildi: <b>{escape(name)}</b> — {format_date(day, month, year)}"


def deleted_text(name: str) -> str:
    return f"🗑 O'chirildi: <b>{escape(name)}</b>"


def records_title(total: int) -> str:
    return f"📋 <b>Tug'ilgan kunlar</b> ({total} ta)\nKimnidir tanlang:"


def record_button_text(b: Birthday) -> str:
    # Tugma matni HTML sifatida o'qilmaydi — escape kerak emas
    return f"{b.name} — {format_date(b.day, b.month)}"


def record_card(b: Birthday, today: date) -> str:
    nxt = next_birthday(b.day, b.month, today)
    when = "bugun" if nxt == today else f"{(nxt - today).days} kundan keyin"
    text = (
        f"👤 <b>{mention(b.name, b.user_id)}</b>\n"
        f"📅 {format_date(b.day, b.month, b.year)}\n"
        f"⏳ Keyingi tug'ilgan kun: {when}"
    )
    if b.year:
        text += f", {calc_age(b.year, nxt)} yoshga to'ladi"
    return text


def confirm_delete_text(b: Birthday) -> str:
    return f"🗑 <b>{escape(b.name)}</b> rostdan o'chirilsinmi?"


def settings_menu_text(s: GroupSettings) -> str:
    remind = f"{s.remind_days} kun oldin" if s.remind_days else "o'chirilgan"
    return (
        "⚙️ <b>Sozlamalar</b>\n\n"
        f"🕗 Tabrik vaqti: <b>{format_time(s.notify_time)}</b>\n"
        f"⏰ Oldindan eslatma: <b>{remind}</b>\n\n"
        "Yuqorida — tabrik vaqti, pastda — necha kun oldin eslatish."
    )
```

- [ ] **Step 4: Testlar o'tishini tekshiring**

Run: `pytest tests/test_texts.py tests/test_handlers.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add birthday_bot/texts.py tests/test_texts.py
git commit -m "Add texts for the button menu"
```

---

### Task 6: `keyboards.py`

**Files:**
- Create: `birthday_bot/keyboards.py`
- Create: `tests/test_keyboards.py`

- [ ] **Step 1: Failing testlar**

`tests/test_keyboards.py`:

```python
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
    assert texts(kb) == ["➕ Qo'shish", "📋 Ro'yxat", "⚙️ Sozlamalar", "🔄 Guruhni almashtirish"]
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
```

- [ ] **Step 2: Yiqilishini tekshiring**

Run: `pytest tests/test_keyboards.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'birthday_bot.keyboards'`

- [ ] **Step 3: Modulni yozing**

`birthday_bot/keyboards.py`:

```python
"""
keyboards.py — Shaxsiy chat menyusi tugmalari va guruhdagi taklif tugmasi.

Callback ma'lumotida group_id bor, lekin unga ishonilmaydi: har bir
bosishda adminlik qayta tekshiriladi (handlers/ui.py: ensure_admin).
"""

from datetime import time

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from birthday_bot.dates import format_time
from birthday_bot.models import Birthday, Group, GroupSettings
from birthday_bot.texts import record_button_text

RECORDS_PAGE_SIZE = 10
TIME_CHOICES = [time(7, 0), time(8, 0), time(9, 0), time(10, 0), time(12, 0)]
REMIND_CHOICES = [0, 1, 3, 7]
CUSTOM_TIME = -1


class Menu(CallbackData, prefix="m"):
    action: str  # home | add | list | settings | groups
    group_id: int


class PickGroup(CallbackData, prefix="pg"):
    group_id: int


class Cancel(CallbackData, prefix="x"):
    group_id: int


class SaveNew(CallbackData, prefix="sv"):
    pass


class RecordPage(CallbackData, prefix="rp"):
    group_id: int
    page: int


class RecordAction(CallbackData, prefix="r"):
    action: str  # show | name | date | del | delyes
    group_id: int
    record_id: int
    page: int = 0


class SetTime(CallbackData, prefix="st"):
    group_id: int
    minutes: int  # kun boshidan daqiqalar; CUSTOM_TIME — qo'lda kiritish


class SetRemind(CallbackData, prefix="sr"):
    group_id: int
    days: int


def _kb(*rows: list[InlineKeyboardButton]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[row for row in rows if row])


def _cb(text: str, data: CallbackData) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data.pack())


def _mark(text: str, selected: bool) -> str:
    return f"✅ {text}" if selected else text


def home_button(group_id: int) -> InlineKeyboardButton:
    return _cb("🏠 Menyu", Menu(action="home", group_id=group_id))


def group_invite_keyboard(bot_username: str, group_id: int) -> InlineKeyboardMarkup:
    url = f"https://t.me/{bot_username}?start=g_{group_id}"
    return _kb([InlineKeyboardButton(text="➕ Tug'ilgan kun qo'shish", url=url)])


def main_menu_keyboard(group_id: int, many_groups: bool) -> InlineKeyboardMarkup:
    rows = [
        [
            _cb("➕ Qo'shish", Menu(action="add", group_id=group_id)),
            _cb("📋 Ro'yxat", Menu(action="list", group_id=group_id)),
        ],
        [_cb("⚙️ Sozlamalar", Menu(action="settings", group_id=group_id))],
    ]
    if many_groups:
        rows.append([_cb("🔄 Guruhni almashtirish", Menu(action="groups", group_id=group_id))])
    return _kb(*rows)


def groups_keyboard(groups: list[Group]) -> InlineKeyboardMarkup:
    return _kb(*[[_cb(g.title or str(g.group_id), PickGroup(group_id=g.group_id))] for g in groups])


def cancel_keyboard(group_id: int) -> InlineKeyboardMarkup:
    return _kb([_cb("❌ Bekor qilish", Cancel(group_id=group_id))])


def add_confirm_keyboard(group_id: int) -> InlineKeyboardMarkup:
    return _kb([_cb("✅ Saqlash", SaveNew()), _cb("❌ Bekor qilish", Cancel(group_id=group_id))])


def after_add_keyboard(group_id: int) -> InlineKeyboardMarkup:
    return _kb([_cb("➕ Yana qo'shish", Menu(action="add", group_id=group_id)), home_button(group_id)])


def empty_list_keyboard(group_id: int) -> InlineKeyboardMarkup:
    return _kb([_cb("➕ Qo'shish", Menu(action="add", group_id=group_id)), home_button(group_id)])


def records_keyboard(
    group_id: int, birthdays: list[Birthday], page: int, pages: int
) -> InlineKeyboardMarkup:
    rows = [
        [_cb(record_button_text(b), RecordAction(action="show", group_id=group_id, record_id=b.id, page=page))]
        for b in birthdays
    ]
    nav = []
    if page > 0:
        nav.append(_cb("⬅️", RecordPage(group_id=group_id, page=page - 1)))
    if page < pages - 1:
        nav.append(_cb("➡️", RecordPage(group_id=group_id, page=page + 1)))
    return _kb(*rows, nav, [home_button(group_id)])


def record_keyboard(group_id: int, record_id: int, page: int) -> InlineKeyboardMarkup:
    def act(action: str) -> RecordAction:
        return RecordAction(action=action, group_id=group_id, record_id=record_id, page=page)

    return _kb(
        [_cb("✏️ Ismni o'zgartirish", act("name"))],
        [_cb("📅 Sanani o'zgartirish", act("date"))],
        [_cb("🗑 O'chirish", act("del"))],
        [_cb("⬅️ Orqaga", RecordPage(group_id=group_id, page=page))],
    )


def confirm_delete_keyboard(group_id: int, record_id: int, page: int) -> InlineKeyboardMarkup:
    def act(action: str) -> RecordAction:
        return RecordAction(action=action, group_id=group_id, record_id=record_id, page=page)

    return _kb([_cb("Ha, o'chirish", act("delyes")), _cb("Yo'q", act("show"))])


def settings_keyboard(group_id: int, s: GroupSettings) -> InlineKeyboardMarkup:
    times = [
        _cb(_mark(format_time(t), t == s.notify_time),
            SetTime(group_id=group_id, minutes=t.hour * 60 + t.minute))
        for t in TIME_CHOICES
    ]
    custom = s.notify_time not in TIME_CHOICES
    custom_label = "✍️ Boshqa vaqt" + (f" ({format_time(s.notify_time)})" if custom else "")
    remind = [
        _cb(_mark("🔕 O'chiq" if d == 0 else f"{d} kun", d == s.remind_days),
            SetRemind(group_id=group_id, days=d))
        for d in REMIND_CHOICES
    ]
    return _kb(
        times[:3],
        [*times[3:], _cb(_mark(custom_label, custom), SetTime(group_id=group_id, minutes=CUSTOM_TIME))],
        remind,
        [home_button(group_id)],
    )
```

- [ ] **Step 4: Testlar o'tishini tekshiring**

Run: `pytest tests/test_keyboards.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add birthday_bot/keyboards.py tests/test_keyboards.py
git commit -m "Add inline keyboards and callback data for the menu"
```

---

### Task 7: Handler testlari uchun yordamchilarni kengaytirish

**Files:**
- Modify: `tests/test_handlers.py`

Barcha yangi handler testlari shu faylga qo'shiladi — modul darajasidagi `dispatcher` bir marta yaratilishi kerak (CLAUDE.md).

- [ ] **Step 1: Importlar**

`tests/test_handlers.py` dagi importlarni almashtiring:

```python
from datetime import datetime, time
from itertools import count
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

import pytest
from aiogram import Bot, Dispatcher
from aiogram.client.session.base import BaseSession
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.methods import (
    AnswerCallbackQuery,
    EditMessageText,
    GetChat,
    GetChatMember,
    GetMe,
    SendMessage,
    TelegramMethod,
)
from aiogram.types import (
    CallbackQuery,
    Chat,
    ChatFullInfo,
    ChatMemberLeft,
    ChatMemberMember,
    ChatMemberOwner,
    ChatMemberUpdated,
    InlineKeyboardMarkup,
    Message,
    Sticker,
    Update,
    User,
)

from birthday_bot.config import Config
from birthday_bot.handlers import build_router
from birthday_bot.models import Group

G, G2 = -100123, -100456
ADMIN, MEMBER = 1, 2
_ids = count(1)
```

(`Group` va boshqa importlar keyingi tasklardagi testlarda ishlatiladi.)

- [ ] **Step 2: `MockSession` ga `GetChat` va `last_markup`**

`make_request` da `GetChatMember` blokidan keyin:

```python
        if isinstance(method, GetChat):
            return ChatFullInfo(
                id=method.chat_id, type="supergroup", title="Oila",
                accent_color_id=0, max_reaction_count=0,
            )
```

`sent_texts` dan keyin:

```python
    def last_markup(self) -> Optional[InlineKeyboardMarkup]:
        for r in reversed(self.requests):
            if isinstance(r, (SendMessage, EditMessageText)):
                return r.reply_markup
        return None

    def last_alert(self) -> Optional[AnswerCallbackQuery]:
        alerts = [r for r in self.requests if isinstance(r, AnswerCallbackQuery)]
        return alerts[-1] if alerts else None
```

- [ ] **Step 3: Xabar/callback yasovchilar**

`message()` ni almashtiring (shaxsiy chatda chat ID = foydalanuvchi ID):

```python
def message(
    text: Optional[str],
    from_id: int = ADMIN,
    reply_to: Optional[Message] = None,
    from_name: str = "User",
    chat_type: str = "supergroup",
    **kw,
) -> Message:
    chat_id = from_id if chat_type == "private" else G
    return Message(
        message_id=next(_ids),
        date=datetime.now(),
        chat=Chat(id=chat_id, type=chat_type),
        from_user=user(from_id, from_name),
        text=text,
        reply_to_message=reply_to,
        **kw,
    )


def callback_update(data: str, from_id: int = ADMIN) -> Update:
    """Shaxsiy chatdagi menyu xabarida tugma bosilishi."""
    return Update(
        update_id=next(_ids),
        callback_query=CallbackQuery(
            id=str(next(_ids)),
            from_user=user(from_id),
            chat_instance="ci",
            message=message("menyu", from_id=from_id, chat_type="private"),
            data=data,
        ),
    )


def membership_update(old: str, new: str) -> Update:
    """Botning guruhdagi holati o'zgarishi ("left" yoki "member")."""
    bot_user = User(id=42, is_bot=True, first_name="Bot")

    def member(status: str):
        return ChatMemberLeft(user=bot_user) if status == "left" else ChatMemberMember(user=bot_user)

    return Update(
        update_id=next(_ids),
        my_chat_member=ChatMemberUpdated(
            chat=Chat(id=G, type="supergroup", title="Oila"),
            from_user=user(ADMIN),
            date=datetime.now(),
            old_chat_member=member(old),
            new_chat_member=member(new),
        ),
    )


def buttons(markup: Optional[InlineKeyboardMarkup]) -> dict[str, str]:
    """Tugma matni → callback_data (yoki URL)."""
    if markup is None:
        return {}
    return {b.text: b.callback_data or b.url for row in markup.inline_keyboard for b in row}


async def admin_in_group(db):
    await db.upsert_group(G, "Oila")
    await db.link_admin(ADMIN, G)
```

- [ ] **Step 4: `send` fixture**

`send` fixture'ni almashtiring (har test uchun toza FSM xotirasi):

```python
@pytest.fixture
async def send(db, config):
    session = MockSession()
    bot = Bot("42:TEST", session=session)
    dispatcher["db"] = db
    dispatcher["config"] = config
    # Savol-javob holati testlar orasida o'tib ketmasligi uchun
    dispatcher.fsm.storage = MemoryStorage()

    async def _send(text=None, update: Optional[Update] = None, **kw) -> list[str]:
        session.requests.clear()
        update = update or Update(update_id=next(_ids), message=message(text, **kw))
        await dispatcher.feed_update(bot, update)
        return session.sent_texts()

    async def _click(data: str, from_id: int = ADMIN) -> list[str]:
        return await _send(update=callback_update(data, from_id))

    _send.session = session
    _send.click = _click
    return _send
```

- [ ] **Step 5: Mavjud testlar o'tishini tekshiring**

Run: `pytest tests/test_handlers.py -v`
Expected: PASS (8 ta eski test)

- [ ] **Step 6: Commit**

```bash
git add tests/test_handlers.py
git commit -m "Extend handler test harness for callbacks and private chats"
```

---

### Task 8: Guruh hodisalari, `ui.py` va routerlarni ulash

**Files:**
- Create: `birthday_bot/handlers/ui.py`
- Create: `birthday_bot/handlers/group_events.py`
- Modify: `birthday_bot/handlers/common.py`
- Modify: `birthday_bot/handlers/__init__.py`
- Test: `tests/test_handlers.py`

- [ ] **Step 1: Failing testlar**

`tests/test_handlers.py` oxiriga:

```python
# ---------- Tugmali menyu ----------


async def test_bot_added_to_group_greets_and_registers(send, db):
    (reply,) = await send(update=membership_update("left", "member"))
    assert "Salom" in reply
    assert buttons(send.session.last_markup()) == {
        "➕ Tug'ilgan kun qo'shish": f"https://t.me/MyBot?start=g_{G}"
    }
    assert await db.get_group(G) == Group(group_id=G, title="Oila", active=True)

    # Holat o'zgarsa-yu, bot guruhda qolsa — qayta salomlashmaydi
    assert await send(update=membership_update("member", "member")) == []

    assert await send(update=membership_update("member", "left")) == []
    assert (await db.get_group(G)).active is False


async def test_group_menu_command(send, db):
    (reply,) = await send("/menu")
    assert "Salom" in reply
    assert "➕ Tug'ilgan kun qo'shish" in buttons(send.session.last_markup())
    assert await db.get_group(G) is not None
    (reply,) = await send("/start")
    assert "Salom" in reply
```

- [ ] **Step 2: Yiqilishini tekshiring**

Run: `pytest tests/test_handlers.py -k "group" -v`
Expected: FAIL — `my_chat_member` uchun javob yo'q (`ValueError: not enough values to unpack`).

- [ ] **Step 3: `handlers/ui.py`**

```python
"""
ui.py — Tugmali menyu handlerlari uchun umumiy yordamchilar.
"""

from typing import Any, Awaitable, Callable, Optional, Union

from aiogram import BaseMiddleware, Bot, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message, TelegramObject

from birthday_bot.database import Database
from birthday_bot.permissions import is_admin
from birthday_bot.texts import NOT_ADMIN_ALERT

# Savol-javobga javob: oddiy matn, buyruq emas
TEXT_INPUT = F.text & ~F.text.startswith("/")


async def ensure_admin(
    event: Union[Message, CallbackQuery], bot: Bot, db: Database, group_id: int
) -> bool:
    """
    Adminlikni qayta tekshiradi (callback ma'lumotiga ishonilmaydi). Ruxsat
    bo'lmasa — bog'lanish o'chiriladi va foydalanuvchiga aytiladi.
    """
    user_id = event.from_user.id
    if await is_admin(bot, group_id, user_id):
        return True
    await db.unlink_admin(user_id, group_id)
    if isinstance(event, CallbackQuery):
        await event.answer(NOT_ADMIN_ALERT, show_alert=True)
    else:
        await event.answer(NOT_ADMIN_ALERT)
    return False


async def show(callback: CallbackQuery, text: str, keyboard: Optional[InlineKeyboardMarkup] = None):
    """Menyu xabarini yangilaydi (eski xabarga kirib bo'lmasa — yangisini yuboradi)."""
    if isinstance(callback.message, Message):
        try:
            await callback.message.edit_text(text, reply_markup=keyboard)
        except TelegramBadRequest as exc:
            # Xuddi shu tugma qayta bosilganda matn o'zgarmaydi — bu xato emas
            if "message is not modified" not in str(exc):
                raise
    else:
        await callback.bot.send_message(callback.from_user.id, text, reply_markup=keyboard)
    await callback.answer()


class ClearStateOnCommand(BaseMiddleware):
    """Savol-javob paytida buyruq yozilsa — savol-javob bekor qilinadi."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        state: Optional[FSMContext] = data.get("state")
        text = getattr(event, "text", None)
        if state is not None and data.get("raw_state") and text and text.startswith("/"):
            await state.clear()
            # StateFilter data["raw_state"] ni o'qiydi — uni ham yangilaymiz
            data["raw_state"] = None
        return await handler(event, data)
```

- [ ] **Step 4: `handlers/group_events.py`**

```python
"""
group_events.py — Bot guruhga qo'shilganda/chiqarilganda va guruhdagi /menu.
"""

import logging

from aiogram import Bot, F, Router
from aiogram.enums import ChatMemberStatus, ChatType
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command
from aiogram.types import ChatMemberUpdated, Message

from birthday_bot.database import Database
from birthday_bot.keyboards import group_invite_keyboard
from birthday_bot.texts import WELCOME_TEXT

logger = logging.getLogger(__name__)

GROUP_TYPES = {ChatType.GROUP, ChatType.SUPERGROUP}
IN_CHAT = {ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR}

router = Router(name="group_events")
router.message.filter(F.chat.type.in_(GROUP_TYPES))
router.my_chat_member.filter(F.chat.type.in_(GROUP_TYPES))


async def send_welcome(bot: Bot, chat_id: int):
    me = await bot.me()
    try:
        await bot.send_message(
            chat_id, WELCOME_TEXT, reply_markup=group_invite_keyboard(me.username, chat_id)
        )
    except TelegramAPIError as exc:
        logger.warning("Salomlashish yuborilmadi (guruh=%s): %s", chat_id, exc)


@router.my_chat_member()
async def on_bot_membership(event: ChatMemberUpdated, bot: Bot, db: Database):
    was_in = event.old_chat_member.status in IN_CHAT
    is_in = event.new_chat_member.status in IN_CHAT
    if is_in:
        await db.upsert_group(event.chat.id, event.chat.title or "")
        if not was_in:
            logger.info("Bot guruhga qo'shildi: %s", event.chat.id)
            await send_welcome(bot, event.chat.id)
    else:
        await db.set_group_active(event.chat.id, False)
        logger.info("Bot guruhdan chiqarildi: %s", event.chat.id)


@router.message(Command("menu", "start"))
async def cmd_group_menu(message: Message, bot: Bot, db: Database):
    # Bu yangilanishdan oldin qo'shilgan guruhlar ham shu yerda ro'yxatga olinadi
    await db.upsert_group(message.chat.id, message.chat.title or "")
    await send_welcome(bot, message.chat.id)
```

- [ ] **Step 5: `common.py` faqat `/help`**

`birthday_bot/handlers/common.py`:

Docstringni almashtiring:

```python
"""
common.py — /help va guruh chat ID o'zgarishi.
"""
```

`@router.message(Command("start", "help"))` ni almashtiring:

```python
@router.message(Command("help"))
```

- [ ] **Step 6: Routerlarni ulash**

`birthday_bot/handlers/__init__.py`:

```python
"""
handlers — Bot buyruqlari va tugmali menyu. Har bir handler `db: Database`
va `config: Config` ni Dispatcher workflow_data orqali oladi (__main__.py ga
qarang).
"""

from aiogram import Router

from birthday_bot.handlers import birthdays, common, group_events, settings
from birthday_bot.handlers.ui import ClearStateOnCommand


def build_router() -> Router:
    root = Router(name="root")
    root.message.outer_middleware(ClearStateOnCommand())
    root.include_routers(
        group_events.router,
        common.router,
        birthdays.router,
        settings.router,
    )
    return root
```

- [ ] **Step 7: Testlar o'tishini tekshiring**

Run: `pytest -v`
Expected: PASS (barcha testlar)

- [ ] **Step 8: Commit**

```bash
git add birthday_bot/handlers tests/test_handlers.py
git commit -m "Greet new groups with an add button and register them"
```

---

### Task 9: Shaxsiy chat menyusi (`menu.py`)

**Files:**
- Create: `birthday_bot/handlers/menu.py`
- Modify: `birthday_bot/handlers/__init__.py`
- Test: `tests/test_handlers.py`

- [ ] **Step 1: Failing testlar**

`tests/test_handlers.py` dagi `from birthday_bot.models import Group` qatoridan keyin:

```python
from birthday_bot.keyboards import (
    Cancel,
    Menu,
    RecordAction,
    SaveNew,
    SetRemind,
)
```

Fayl oxiriga:

```python
async def test_deep_link_admin_gets_menu(send, db):
    await db.upsert_group(G, "Oila")
    (reply,) = await send(f"/start g_{G}", chat_type="private")
    assert "Oila" in reply
    assert list(buttons(send.session.last_markup())) == ["➕ Qo'shish", "📋 Ro'yxat", "⚙️ Sozlamalar"]
    assert [g.group_id for g in await db.admin_groups(ADMIN)] == [G]
    # Keyingi safar havolasiz ham menyu ochiladi
    (reply,) = await send("/start", chat_type="private")
    assert "Oila" in reply


async def test_deep_link_unknown_group_fetches_title(send, db):
    (reply,) = await send(f"/start g_{G}", chat_type="private")
    assert "Oila" in reply
    assert (await db.get_group(G)).title == "Oila"


async def test_deep_link_non_admin_rejected(send, db):
    await db.upsert_group(G, "Oila")
    (reply,) = await send(f"/start g_{G}", from_id=MEMBER, chat_type="private")
    assert "admindan so'rang" in reply
    assert await db.admin_groups(MEMBER) == []


async def test_start_without_groups_explains(send):
    (reply,) = await send("/start", chat_type="private")
    assert "guruhingizga qo'shing" in reply
    (reply,) = await send("/start g_xyz", chat_type="private")
    assert "guruhingizga qo'shing" in reply


async def test_many_groups_choose_and_switch(send, db):
    await db.upsert_group(G, "Oila")
    await db.upsert_group(G2, "Ish")
    await db.link_admin(ADMIN, G)
    await db.link_admin(ADMIN, G2)
    (reply,) = await send("/menu", chat_type="private")
    assert "Qaysi guruh" in reply
    kb = buttons(send.session.last_markup())
    assert list(kb) == ["Ish", "Oila"]
    (reply,) = await send.click(kb["Oila"])
    assert "Oila" in reply
    menu = buttons(send.session.last_markup())
    assert "🔄 Guruhni almashtirish" in menu
    (reply,) = await send.click(menu["🔄 Guruhni almashtirish"])
    assert "Qaysi guruh" in reply


async def test_lost_admin_rights_unlinks(send, db):
    await db.upsert_group(G, "Oila")
    await db.link_admin(MEMBER, G)
    (reply,) = await send("/start", from_id=MEMBER, chat_type="private")
    assert "guruhingizga qo'shing" in reply
    assert await db.admin_groups(MEMBER) == []


async def test_forged_callback_rejected(send, db):
    await db.upsert_group(G, "Oila")
    assert await send.click(Menu(action="home", group_id=G).pack(), from_id=MEMBER) == []
    alert = send.session.last_alert()
    assert alert.show_alert and "⛔" in alert.text
```

- [ ] **Step 2: Yiqilishini tekshiring**

Run: `pytest tests/test_handlers.py -k "deep_link or start_without or many_groups or lost_admin or forged" -v`
Expected: FAIL — shaxsiy chatdagi `/start` ga javob yo'q: `ValueError: not enough values to unpack`.

- [ ] **Step 3: `handlers/menu.py`**

```python
"""
menu.py — Shaxsiy chatdagi tugmali menyu: /start (guruh havolasi bilan),
/menu, guruh tanlash va savol-javobni bekor qilish.
"""

from typing import Optional, Union

from aiogram import Bot, F, Router
from aiogram.enums import ChatType
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from birthday_bot.database import Database
from birthday_bot.handlers.ui import ensure_admin, show
from birthday_bot.keyboards import Cancel, Menu, PickGroup, groups_keyboard, main_menu_keyboard
from birthday_bot.models import Group
from birthday_bot.parsing import parse_group_payload
from birthday_bot.permissions import is_admin
from birthday_bot.texts import CHOOSE_GROUP_TEXT, NO_GROUPS_TEXT, NOT_ADMIN_TEXT, menu_text

router = Router(name="menu")
router.message.filter(F.chat.type == ChatType.PRIVATE)


async def available_groups(bot: Bot, db: Database, user_id: int) -> list[Group]:
    """Foydalanuvchi hozir ham admini bo'lgan bog'langan guruhlar."""
    groups = []
    for group in await db.admin_groups(user_id):
        if await is_admin(bot, group.group_id, user_id):
            groups.append(group)
        else:
            await db.unlink_admin(user_id, group.group_id)
    return groups


async def main_menu_view(db: Database, user_id: int, group_id: int) -> tuple[str, InlineKeyboardMarkup]:
    group = await db.get_group(group_id)
    many_groups = len(await db.admin_groups(user_id)) > 1
    return menu_text(group.title if group else ""), main_menu_keyboard(group_id, many_groups)


async def start_view(
    bot: Bot, db: Database, user_id: int
) -> tuple[str, Optional[InlineKeyboardMarkup]]:
    """Guruh bitta bo'lsa — uning menyusi, bir nechta bo'lsa — tanlash."""
    groups = await available_groups(bot, db, user_id)
    if not groups:
        return NO_GROUPS_TEXT, None
    if len(groups) == 1:
        return await main_menu_view(db, user_id, groups[0].group_id)
    return CHOOSE_GROUP_TEXT, groups_keyboard(groups)


@router.message(CommandStart(deep_link=True))
async def cmd_start_link(message: Message, command: CommandObject, bot: Bot, db: Database):
    user_id = message.from_user.id
    group_id = parse_group_payload(command.args or "")
    if group_id is None:
        text, keyboard = await start_view(bot, db, user_id)
        await message.answer(text, reply_markup=keyboard)
        return

    if not await is_admin(bot, group_id, user_id):
        await db.unlink_admin(user_id, group_id)
        await message.answer(NOT_ADMIN_TEXT)
        return

    if await db.get_group(group_id) is None:
        # Bot guruhga bu yangilanishdan oldin qo'shilgan — nomini so'raymiz
        chat = await bot.get_chat(group_id)
        await db.upsert_group(group_id, chat.title or "")
    await db.link_admin(user_id, group_id)
    text, keyboard = await main_menu_view(db, user_id, group_id)
    await message.answer(text, reply_markup=keyboard)


@router.message(Command("start", "menu"))
async def cmd_start(message: Message, bot: Bot, db: Database):
    text, keyboard = await start_view(bot, db, message.from_user.id)
    await message.answer(text, reply_markup=keyboard)


@router.callback_query(Menu.filter(F.action == "home"))
@router.callback_query(Cancel.filter())
async def cb_home(
    callback: CallbackQuery,
    callback_data: Union[Menu, Cancel],
    bot: Bot,
    db: Database,
    state: FSMContext,
):
    await state.clear()
    if await ensure_admin(callback, bot, db, callback_data.group_id):
        text, keyboard = await main_menu_view(db, callback.from_user.id, callback_data.group_id)
        await show(callback, text, keyboard)


@router.callback_query(Menu.filter(F.action == "groups"))
async def cb_groups(callback: CallbackQuery, bot: Bot, db: Database):
    text, keyboard = await start_view(bot, db, callback.from_user.id)
    await show(callback, text, keyboard)


@router.callback_query(PickGroup.filter())
async def cb_pick_group(callback: CallbackQuery, callback_data: PickGroup, bot: Bot, db: Database):
    if await ensure_admin(callback, bot, db, callback_data.group_id):
        text, keyboard = await main_menu_view(db, callback.from_user.id, callback_data.group_id)
        await show(callback, text, keyboard)
```

- [ ] **Step 4: Routerni ulash**

`birthday_bot/handlers/__init__.py`:

```python
from birthday_bot.handlers import birthdays, common, group_events, menu, settings
```

va `include_routers` ichida `group_events.router` dan keyin `menu.router,` qo'shing.

- [ ] **Step 5: Testlar o'tishini tekshiring**

Run: `pytest -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add birthday_bot/handlers tests/test_handlers.py
git commit -m "Add private-chat menu with deep-link group linking"
```

---

### Task 10: Qo'shish savol-javobi (`add_flow.py`)

**Files:**
- Create: `birthday_bot/handlers/add_flow.py`
- Modify: `birthday_bot/handlers/__init__.py`
- Test: `tests/test_handlers.py`

- [ ] **Step 1: Failing testlar**

`tests/test_handlers.py` oxiriga:

```python
async def test_add_flow(send, db):
    await admin_in_group(db)
    (reply,) = await send.click(Menu(action="add", group_id=G).pack())
    assert "Ismini yozing" in reply
    (reply,) = await send("  Karim   aka ", chat_type="private")
    assert "Sanasi?" in reply
    (reply,) = await send("31.02", chat_type="private")
    assert "mavjud emas" in reply and "Sanasi?" in reply
    (reply,) = await send("15.03.1980", chat_type="private")
    assert "Karim aka</b> — 15 Mart 1980" in reply
    (reply,) = await send.click(buttons(send.session.last_markup())["✅ Saqlash"])
    assert "Qo'shildi" in reply
    assert "➕ Yana qo'shish" in buttons(send.session.last_markup())
    (b,) = await db.list_birthdays(G)
    assert (b.name, b.day, b.month, b.year) == ("Karim aka", 15, 3, 1980)

    # Saqlangandan keyin tugma qayta bosilsa — ikkinchi yozuv qo'shilmaydi
    assert await send.click(SaveNew().pack()) == []
    assert "eskirgan" in send.session.last_alert().text
    assert await db.count_birthdays(G) == 1


async def test_add_flow_cancel_and_command_interrupt(send, db):
    await admin_in_group(db)
    await send.click(Menu(action="add", group_id=G).pack())
    (reply,) = await send.click(Cancel(group_id=G).pack())
    assert "Nima qilamiz?" in reply
    assert await send("Karim", chat_type="private") == []  # holat yo'q — e'tiborsiz

    await send.click(Menu(action="add", group_id=G).pack())
    (reply,) = await send("/help", chat_type="private")
    assert "/add" in reply
    assert await send("Karim", chat_type="private") == []
    assert await db.count_birthdays(G) == 0


async def test_add_flow_rejects_non_admin(send, db):
    await db.upsert_group(G, "Oila")
    assert await send.click(Menu(action="add", group_id=G).pack(), from_id=MEMBER) == []
    assert await send("Karim", from_id=MEMBER, chat_type="private") == []
```

- [ ] **Step 2: Yiqilishini tekshiring**

Run: `pytest tests/test_handlers.py -k add_flow -v`
Expected: FAIL — `ValueError: not enough values to unpack` (handler yo'q).

- [ ] **Step 3: `handlers/add_flow.py`**

```python
"""
add_flow.py — Tug'ilgan kun qo'shish savol-javobi: ism → sana → tasdiqlash.
"""

from aiogram import Bot, F, Router
from aiogram.enums import ChatType
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from birthday_bot.config import Config
from birthday_bot.database import Database
from birthday_bot.dates import now
from birthday_bot.handlers.ui import TEXT_INPUT, ensure_admin, show
from birthday_bot.keyboards import (
    Menu,
    SaveNew,
    add_confirm_keyboard,
    after_add_keyboard,
    cancel_keyboard,
)
from birthday_bot.parsing import ParseError, parse_date, parse_name
from birthday_bot.texts import ASK_DATE_TEXT, ASK_NAME_TEXT, STALE_TEXT, add_preview, added_text

router = Router(name="add_flow")
router.message.filter(F.chat.type == ChatType.PRIVATE)


class AddBirthday(StatesGroup):
    name = State()
    date = State()
    confirm = State()


@router.callback_query(Menu.filter(F.action == "add"))
async def cb_add(callback: CallbackQuery, callback_data: Menu, bot: Bot, db: Database, state: FSMContext):
    group_id = callback_data.group_id
    if not await ensure_admin(callback, bot, db, group_id):
        return
    await state.set_state(AddBirthday.name)
    await state.set_data({"group_id": group_id})
    await show(callback, ASK_NAME_TEXT, cancel_keyboard(group_id))


@router.message(AddBirthday.name, TEXT_INPUT)
async def got_name(message: Message, state: FSMContext):
    group_id = (await state.get_data())["group_id"]
    try:
        name = parse_name(message.text)
    except ParseError as exc:
        await message.answer(f"❗ {exc}\n\n{ASK_NAME_TEXT}", reply_markup=cancel_keyboard(group_id))
        return
    await state.update_data(name=name)
    await state.set_state(AddBirthday.date)
    await message.answer(ASK_DATE_TEXT, reply_markup=cancel_keyboard(group_id))


@router.message(AddBirthday.date, TEXT_INPUT)
async def got_date(message: Message, state: FSMContext, config: Config):
    data = await state.get_data()
    try:
        parsed = parse_date(message.text, now(config.timezone).date())
    except ParseError as exc:
        await message.answer(
            f"❗ {exc}\n\n{ASK_DATE_TEXT}", reply_markup=cancel_keyboard(data["group_id"])
        )
        return
    await state.update_data(day=parsed.day, month=parsed.month, year=parsed.year)
    await state.set_state(AddBirthday.confirm)
    await message.answer(
        add_preview(data["name"], parsed.day, parsed.month, parsed.year),
        reply_markup=add_confirm_keyboard(data["group_id"]),
    )


@router.callback_query(AddBirthday.confirm, SaveNew.filter())
async def cb_save(callback: CallbackQuery, bot: Bot, db: Database, state: FSMContext):
    data = await state.get_data()
    await state.clear()
    group_id = data["group_id"]
    if not await ensure_admin(callback, bot, db, group_id):
        return
    await db.add_birthday(
        group_id=group_id,
        name=data["name"],
        day=data["day"],
        month=data["month"],
        year=data["year"],
        added_by=callback.from_user.id,
    )
    await show(
        callback,
        added_text(data["name"], data["day"], data["month"], data["year"]),
        after_add_keyboard(group_id),
    )


@router.callback_query(SaveNew.filter())
async def cb_save_stale(callback: CallbackQuery):
    # Holat yo'q: allaqachon saqlangan, bekor qilingan yoki bot qayta ishga tushgan
    await callback.answer(STALE_TEXT, show_alert=True)
```

- [ ] **Step 4: Routerni ulash**

`birthday_bot/handlers/__init__.py`:

```python
from birthday_bot.handlers import add_flow, birthdays, common, group_events, menu, settings
```

va `include_routers` oxiriga (`settings.router` dan keyin) `add_flow.router,` qo'shing.

- [ ] **Step 5: Testlar o'tishini tekshiring**

Run: `pytest -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add birthday_bot/handlers tests/test_handlers.py
git commit -m "Add step-by-step birthday adding via buttons"
```

---

### Task 11: Ro'yxat, tahrirlash, o'chirish (`manage.py`)

**Files:**
- Create: `birthday_bot/handlers/manage.py`
- Modify: `birthday_bot/handlers/__init__.py`
- Test: `tests/test_handlers.py`

- [ ] **Step 1: Failing testlar**

`tests/test_handlers.py` oxiriga:

```python
async def test_manage_list_edit_delete(send, db):
    await admin_in_group(db)
    a = await db.add_birthday(G, "Ali", 15, 3, 1990)
    (reply,) = await send.click(Menu(action="list", group_id=G).pack())
    assert "(1 ta)" in reply
    (reply,) = await send.click(buttons(send.session.last_markup())["Ali — 15 Mart"])
    assert "15 Mart 1990" in reply
    card = buttons(send.session.last_markup())

    await send.click(card["✏️ Ismni o'zgartirish"])
    (reply,) = await send("Ali aka", chat_type="private")
    assert "Saqlandi" in reply and "Ali aka" in reply

    await send.click(card["📅 Sanani o'zgartirish"])
    (reply,) = await send("bugun", chat_type="private")
    assert "❗" in reply
    (reply,) = await send("16.03", chat_type="private")
    assert "16 Mart" in reply
    b = await db.get_birthday(G, a)
    assert (b.name, b.day, b.month, b.year) == ("Ali aka", 16, 3, None)

    (reply,) = await send.click(card["🗑 O'chirish"])
    assert "rostdan" in reply
    (reply,) = await send.click(buttons(send.session.last_markup())["Ha, o'chirish"])
    assert "O'chirildi" in reply and "Hali hech kim" in reply
    assert await db.count_birthdays(G) == 0


async def test_manage_pagination_and_other_group(send, db):
    await admin_in_group(db)
    for i in range(12):
        await db.add_birthday(G, f"Odam {i:02}", 1 + i, 1)
    other = await db.add_birthday(G2, "Begona", 1, 1)
    await send.click(Menu(action="list", group_id=G).pack())
    kb = buttons(send.session.last_markup())
    assert "Odam 09 — 10 Yanvar" in kb and "Odam 10 — 11 Yanvar" not in kb
    await send.click(kb["➡️"])
    assert "Odam 11 — 12 Yanvar" in buttons(send.session.last_markup())

    # Boshqa guruh yozuviga o'z guruhi ID'si orqali tegib bo'lmaydi
    (reply,) = await send.click(
        RecordAction(action="delyes", group_id=G, record_id=other).pack()
    )
    assert "endi yo'q" in reply
    assert await db.get_birthday(G2, other) is not None
```

- [ ] **Step 2: Yiqilishini tekshiring**

Run: `pytest tests/test_handlers.py -k manage -v`
Expected: FAIL — `ValueError: not enough values to unpack`.

- [ ] **Step 3: `handlers/manage.py`**

```python
"""
manage.py — Tugmali ro'yxat: yozuv kartasi, ism/sanani tahrirlash, o'chirish.
"""

from typing import Optional, Union

from aiogram import Bot, F, Router
from aiogram.enums import ChatType
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from birthday_bot.config import Config
from birthday_bot.database import Database
from birthday_bot.dates import now
from birthday_bot.handlers.ui import TEXT_INPUT, ensure_admin, show
from birthday_bot.keyboards import (
    RECORDS_PAGE_SIZE,
    Menu,
    RecordAction,
    RecordPage,
    cancel_keyboard,
    confirm_delete_keyboard,
    empty_list_keyboard,
    record_keyboard,
    records_keyboard,
)
from birthday_bot.models import Birthday
from birthday_bot.parsing import ParseError, parse_date, parse_name
from birthday_bot.texts import (
    ASK_NEW_DATE_TEXT,
    ASK_NEW_NAME_TEXT,
    EMPTY_LIST_TEXT,
    RECORD_GONE_TEXT,
    SAVED_TEXT,
    confirm_delete_text,
    deleted_text,
    record_card,
    records_title,
)

router = Router(name="manage")
router.message.filter(F.chat.type == ChatType.PRIVATE)


class EditBirthday(StatesGroup):
    name = State()
    date = State()


async def records_view(db: Database, group_id: int, page: int) -> tuple[str, InlineKeyboardMarkup]:
    total = await db.count_birthdays(group_id)
    if total == 0:
        return EMPTY_LIST_TEXT, empty_list_keyboard(group_id)
    pages = (total + RECORDS_PAGE_SIZE - 1) // RECORDS_PAGE_SIZE
    page = max(0, min(page, pages - 1))
    items = await db.list_birthdays(group_id, limit=RECORDS_PAGE_SIZE, offset=page * RECORDS_PAGE_SIZE)
    return records_title(total), records_keyboard(group_id, items, page, pages)


@router.callback_query(Menu.filter(F.action == "list"))
@router.callback_query(RecordPage.filter())
async def cb_records(
    callback: CallbackQuery, callback_data: Union[Menu, RecordPage], bot: Bot, db: Database
):
    if not await ensure_admin(callback, bot, db, callback_data.group_id):
        return
    page = getattr(callback_data, "page", 0)
    text, keyboard = await records_view(db, callback_data.group_id, page)
    await show(callback, text, keyboard)


@router.callback_query(RecordAction.filter())
async def cb_record(
    callback: CallbackQuery,
    callback_data: RecordAction,
    bot: Bot,
    db: Database,
    config: Config,
    state: FSMContext,
):
    group_id, page = callback_data.group_id, callback_data.page
    if not await ensure_admin(callback, bot, db, group_id):
        return
    birthday = await db.get_birthday(group_id, callback_data.record_id)
    if birthday is None:
        text, keyboard = await records_view(db, group_id, page)
        await show(callback, f"{RECORD_GONE_TEXT}\n\n{text}", keyboard)
        return

    action = callback_data.action
    if action == "show":
        await show(
            callback,
            record_card(birthday, now(config.timezone).date()),
            record_keyboard(group_id, birthday.id, page),
        )
    elif action == "del":
        await show(
            callback,
            confirm_delete_text(birthday),
            confirm_delete_keyboard(group_id, birthday.id, page),
        )
    elif action == "delyes":
        await db.remove_birthday(group_id, birthday.id)
        text, keyboard = await records_view(db, group_id, page)
        await show(callback, f"{deleted_text(birthday.name)}\n\n{text}", keyboard)
    elif action in ("name", "date"):
        await state.set_state(EditBirthday.name if action == "name" else EditBirthday.date)
        await state.set_data({"group_id": group_id, "record_id": birthday.id, "page": page})
        await show(
            callback,
            ASK_NEW_NAME_TEXT if action == "name" else ASK_NEW_DATE_TEXT,
            cancel_keyboard(group_id),
        )


async def _edited_record(
    message: Message, bot: Bot, db: Database, state: FSMContext
) -> Optional[tuple[Birthday, int]]:
    """Tahrirlanayotgan yozuv va ro'yxat sahifasi; bo'lmasa None (holat tozalanadi)."""
    data = await state.get_data()
    await state.clear()
    if not await ensure_admin(message, bot, db, data["group_id"]):
        return None
    birthday = await db.get_birthday(data["group_id"], data["record_id"])
    if birthday is None:
        await message.answer(RECORD_GONE_TEXT)
        return None
    return birthday, data["page"]


async def _answer_card(message: Message, db: Database, config: Config, birthday: Birthday, page: int):
    updated = await db.get_birthday(birthday.group_id, birthday.id)
    await message.answer(
        f"{SAVED_TEXT}\n\n{record_card(updated, now(config.timezone).date())}",
        reply_markup=record_keyboard(updated.group_id, updated.id, page),
    )


@router.message(EditBirthday.name, TEXT_INPUT)
async def got_new_name(message: Message, bot: Bot, db: Database, config: Config, state: FSMContext):
    try:
        name = parse_name(message.text)
    except ParseError as exc:
        group_id = (await state.get_data())["group_id"]
        await message.answer(f"❗ {exc}\n\n{ASK_NEW_NAME_TEXT}", reply_markup=cancel_keyboard(group_id))
        return
    found = await _edited_record(message, bot, db, state)
    if found is None:
        return
    birthday, page = found
    await db.update_birthday(
        birthday.group_id, birthday.id, name, birthday.day, birthday.month, birthday.year
    )
    await _answer_card(message, db, config, birthday, page)


@router.message(EditBirthday.date, TEXT_INPUT)
async def got_new_date(message: Message, bot: Bot, db: Database, config: Config, state: FSMContext):
    try:
        parsed = parse_date(message.text, now(config.timezone).date())
    except ParseError as exc:
        group_id = (await state.get_data())["group_id"]
        await message.answer(f"❗ {exc}\n\n{ASK_NEW_DATE_TEXT}", reply_markup=cancel_keyboard(group_id))
        return
    found = await _edited_record(message, bot, db, state)
    if found is None:
        return
    birthday, page = found
    await db.update_birthday(
        birthday.group_id, birthday.id, birthday.name, parsed.day, parsed.month, parsed.year
    )
    await _answer_card(message, db, config, birthday, page)
```

- [ ] **Step 4: Routerni ulash**

`birthday_bot/handlers/__init__.py`:

```python
from birthday_bot.handlers import add_flow, birthdays, common, group_events, manage, menu, settings
```

va `include_routers` oxiriga `manage.router,` qo'shing.

- [ ] **Step 5: Testlar o'tishini tekshiring**

Run: `pytest -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add birthday_bot/handlers tests/test_handlers.py
git commit -m "Add button list with edit and delete"
```

---

### Task 12: Sozlamalar tugmalari (`settings_menu.py`)

**Files:**
- Create: `birthday_bot/handlers/settings_menu.py`
- Modify: `birthday_bot/handlers/__init__.py`
- Test: `tests/test_handlers.py`

- [ ] **Step 1: Failing testlar**

`tests/test_handlers.py` oxiriga:

```python
async def test_settings_menu(send, db):
    await admin_in_group(db)
    (reply,) = await send.click(Menu(action="settings", group_id=G).pack())
    assert "08:00" in reply
    kb = buttons(send.session.last_markup())
    assert "✅ 08:00" in kb and "✅ 🔕 O'chiq" in kb

    (reply,) = await send.click(kb["09:00"])
    assert "09:00" in reply
    assert (await db.get_settings(G)).notify_time == time(9, 0)
    await send.click(kb["3 kun"])
    assert (await db.get_settings(G)).remind_days == 3

    await send.click(kb["✍️ Boshqa vaqt"])
    (reply,) = await send("25:00", chat_type="private")
    assert "❗" in reply
    (reply,) = await send("09:30", chat_type="private")
    assert "09:30" in reply
    assert (await db.get_settings(G)).notify_time == time(9, 30)


async def test_settings_menu_forged_by_member(send, db):
    await db.upsert_group(G, "Oila")
    assert await send.click(SetRemind(group_id=G, days=7).pack(), from_id=MEMBER) == []
    assert (await db.get_settings(G)).remind_days == 0
```

- [ ] **Step 2: Yiqilishini tekshiring**

Run: `pytest tests/test_handlers.py -k settings_menu -v`
Expected: FAIL — `ValueError: not enough values to unpack`.

- [ ] **Step 3: `handlers/settings_menu.py`**

```python
"""
settings_menu.py — Sozlamalar tugmalari: tabrik vaqti va oldindan eslatma.
"""

from datetime import time

from aiogram import Bot, F, Router
from aiogram.enums import ChatType
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from birthday_bot.database import Database
from birthday_bot.dates import parse_time
from birthday_bot.handlers.ui import TEXT_INPUT, ensure_admin, show
from birthday_bot.keyboards import CUSTOM_TIME, Menu, SetRemind, SetTime, cancel_keyboard, settings_keyboard
from birthday_bot.models import MAX_REMIND_DAYS
from birthday_bot.texts import ASK_TIME_TEXT, STALE_TEXT, settings_menu_text

router = Router(name="settings_menu")
router.message.filter(F.chat.type == ChatType.PRIVATE)


class SettingsInput(StatesGroup):
    time = State()


async def settings_view(db: Database, group_id: int) -> tuple[str, InlineKeyboardMarkup]:
    settings = await db.get_settings(group_id)
    return settings_menu_text(settings), settings_keyboard(group_id, settings)


@router.callback_query(Menu.filter(F.action == "settings"))
async def cb_settings(callback: CallbackQuery, callback_data: Menu, bot: Bot, db: Database):
    if await ensure_admin(callback, bot, db, callback_data.group_id):
        text, keyboard = await settings_view(db, callback_data.group_id)
        await show(callback, text, keyboard)


@router.callback_query(SetTime.filter())
async def cb_set_time(
    callback: CallbackQuery, callback_data: SetTime, bot: Bot, db: Database, state: FSMContext
):
    group_id, minutes = callback_data.group_id, callback_data.minutes
    if not await ensure_admin(callback, bot, db, group_id):
        return
    if minutes == CUSTOM_TIME:
        await state.set_state(SettingsInput.time)
        await state.set_data({"group_id": group_id})
        await show(callback, ASK_TIME_TEXT, cancel_keyboard(group_id))
        return
    if not 0 <= minutes < 24 * 60:
        await callback.answer(STALE_TEXT, show_alert=True)
        return
    await db.set_setting(group_id, "notify_time", time(*divmod(minutes, 60)))
    text, keyboard = await settings_view(db, group_id)
    await show(callback, text, keyboard)


@router.callback_query(SetRemind.filter())
async def cb_set_remind(callback: CallbackQuery, callback_data: SetRemind, bot: Bot, db: Database):
    group_id, days = callback_data.group_id, callback_data.days
    if not await ensure_admin(callback, bot, db, group_id):
        return
    if not 0 <= days <= MAX_REMIND_DAYS:
        await callback.answer(STALE_TEXT, show_alert=True)
        return
    await db.set_setting(group_id, "remind_days", days)
    text, keyboard = await settings_view(db, group_id)
    await show(callback, text, keyboard)


@router.message(SettingsInput.time, TEXT_INPUT)
async def got_time(message: Message, bot: Bot, db: Database, state: FSMContext):
    group_id = (await state.get_data())["group_id"]
    at = parse_time(message.text)
    if at is None:
        await message.answer(
            f"❗ Vaqt formati noto'g'ri.\n\n{ASK_TIME_TEXT}", reply_markup=cancel_keyboard(group_id)
        )
        return
    await state.clear()
    if not await ensure_admin(message, bot, db, group_id):
        return
    await db.set_setting(group_id, "notify_time", at)
    text, keyboard = await settings_view(db, group_id)
    await message.answer(text, reply_markup=keyboard)
```

- [ ] **Step 4: Routerni ulash**

`birthday_bot/handlers/__init__.py` ning yakuniy ko'rinishi:

```python
"""
handlers — Bot buyruqlari va tugmali menyu. Har bir handler `db: Database`
va `config: Config` ni Dispatcher workflow_data orqali oladi (__main__.py ga
qarang).
"""

from aiogram import Router

from birthday_bot.handlers import (
    add_flow,
    birthdays,
    common,
    group_events,
    manage,
    menu,
    settings,
    settings_menu,
)
from birthday_bot.handlers.ui import ClearStateOnCommand


def build_router() -> Router:
    root = Router(name="root")
    root.message.outer_middleware(ClearStateOnCommand())
    root.include_routers(
        group_events.router,
        menu.router,
        common.router,
        birthdays.router,
        settings.router,
        # Savol-javob matnini ushlovchilar buyruqlardan keyin
        add_flow.router,
        manage.router,
        settings_menu.router,
    )
    return root
```

- [ ] **Step 5: Testlar o'tishini tekshiring**

Run: `pytest -v`
Expected: PASS (barcha testlar)

- [ ] **Step 6: Commit**

```bash
git add birthday_bot/handlers tests/test_handlers.py
git commit -m "Add settings buttons for greeting time and reminders"
```

---

### Task 13: Hujjatlar va jonli tekshiruv

**Files:**
- Modify: `README.md`
- Modify: `CLAUDE.md`

- [ ] **Step 1: README**

`README.md` da "Botni guruhga qo'shing. Xabar yuborishi uchun admin qilish shart emas, lekin `/add` va `/remove` faqat guruh adminlariga ruxsat etilgan." paragrafini almashtiring:

```markdown
## Qanday ishlatiladi

1. Botni oila guruhiga qo'shing (admin qilish shart emas). Bot salomlashadi va
   **➕ Tug'ilgan kun qo'shish** tugmasini yuboradi.
2. Guruh admini tugmani bosadi — botning shaxsiy chati ochiladi. U yerda
   **➕ Qo'shish**, **📋 Ro'yxat** va **⚙️ Sozlamalar** tugmalari bor: bot ism va
   sanani so'raydi, buyruq yodlash shart emas.
3. Tug'ilgan kun kelganda bot guruhda tabriklaydi — hamma xabardor bo'ladi.

Keyinchalik shaxsiy chatda `/menu` yozish kifoya. Bir necha guruh admini bo'lsangiz,
bot qaysi guruh bilan ishlashni so'raydi. Tugma ko'rinmay qolsa, guruhda `/menu`
yozing. Tug'ilgan kunlarni faqat guruh adminlari qo'sha oladi; boshqalar
`/list` va `/upcoming` dan foydalanadi.
```

"Buyruqlar" jadvalidagi `/start`, `/help` qatorini almashtiring:

```markdown
| `/menu`, `/start` | admin | Shaxsiy chatda — tugmali menyu; guruhda — qo'shish tugmasi |
| `/help` | hamma | Yordam matni |
```

"Fayllar tuzilishi" dagi qatorlarni yangilang:

```
│   ├── models.py        # Birthday, Group, GroupSettings, Upcoming
│   ├── parsing.py       # Buyruq argumentlari, ism/sana, /start payloadi
│   ├── keyboards.py     # Menyu tugmalari va CallbackData
│   └── handlers/        # buyruqlar (common, birthdays, settings) va menyu
│                        # (group_events, menu, add_flow, manage, settings_menu)
```

- [ ] **Step 2: CLAUDE.md**

"Architecture" bo'limidagi `permissions.py` bandidan keyin qo'shing:

```markdown
- **Tugmali menyu (shaxsiy chat):** `group_events` bot guruhga qo'shilganda (`my_chat_member`) guruhni `groups` jadvaliga yozadi va `t.me/<bot>?start=g_<id>` tugmasini yuboradi. `menu` deep link'da adminlikni tekshirib `group_admins` ga bog'laydi. `add_flow`, `manage`, `settings_menu` — aiogram FSM (`MemoryStorage`, restartda yo'qoladi). Tugmalar va `CallbackData` `keyboards.py` da; callback'dagi `group_id` ga ishonilmaydi — har bir amalda `handlers/ui.ensure_admin` qayta tekshiradi. `ClearStateOnCommand` middleware savol-javob paytida yozilgan buyruqda holatni tozalaydi. Scheduler `groups.active = 0` guruhlarni o'tkazib yuboradi.
```

"Tests" bo'limiga qo'shing:

```markdown
Menyu testlari ham `tests/test_handlers.py` da: `send.click(callback_data)` tugma bosadi, `send(..., chat_type="private")` shaxsiy chat, `buttons(send.session.last_markup())` tugmalarni o'qiydi, `membership_update()` botni guruhga qo'shadi. `send` fixture har testda FSM xotirasini yangilaydi.
```

- [ ] **Step 3: To'liq testlar**

Run: `pytest -v`
Expected: PASS — barcha testlar (66 eski + yangilari).

- [ ] **Step 4: Jonli tekshiruv**

Fondagi eski bot jarayonini to'xtating, keyin `python -m birthday_bot` ni qayta ishga tushiring. Log'da `Run polling for bot @birtdate_bot` chiqishini tekshiring. Telegram'da qo'lda tekshirish (foydalanuvchi bilan):
1. Botni sinov guruhidan chiqarib qayta qo'shish → salomlashish va tugma.
2. Tugma → shaxsiy chat → menyu → **➕ Qo'shish** → ism → sana → **✅ Saqlash**.
3. **📋 Ro'yxat** → yozuv → tahrirlash/o'chirish.
4. **⚙️ Sozlamalar** → vaqt tugmasi.

- [ ] **Step 5: Commit**

```bash
git add README.md CLAUDE.md
git commit -m "Document the button menu"
```
