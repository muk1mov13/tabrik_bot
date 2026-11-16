"""
database.py — SQLite (aiosqlite) orqali tug'ilgan kunlar va guruh
sozlamalarini saqlash.

Sxema PRAGMA user_version bilan versiyalanadi: yangi o'zgarish kerak bo'lsa,
MIGRATIONS ro'yxati oxiriga yangi skript qo'shiladi (eskilarini o'zgartirmang).
Sanalar 'YYYY-MM-DD', vaqtlar 'HH:MM' matn ko'rinishida saqlanadi — bu
formatlarda matnli taqqoslash xronologik taqqoslash bilan bir xil.
"""

import secrets
from contextlib import asynccontextmanager
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any, Optional, Union

import aiosqlite

from birthday_bot.dates import birthday_keys_for, format_time, next_birthday, parse_time
from birthday_bot.models import Birthday, Group, GroupSettings, Upcoming

MIGRATIONS = [
    # 1 — boshlang'ich sxema
    """
    CREATE TABLE birthdays (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        group_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        day INTEGER NOT NULL,
        month INTEGER NOT NULL,
        year INTEGER,
        user_id INTEGER,
        added_by INTEGER,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        last_notified TEXT,
        last_reminded TEXT
    );
    CREATE INDEX birthdays_group_idx ON birthdays (group_id);
    CREATE INDEX birthdays_date_idx ON birthdays (month, day);
    CREATE TABLE group_settings (
        group_id INTEGER PRIMARY KEY,
        notify_time TEXT,
        remind_days INTEGER NOT NULL DEFAULT 0,
        upcoming_days INTEGER NOT NULL DEFAULT 7,
        sticker_file_id TEXT
    );
    """,
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
    # 3 — bog'lanish endi har qanday rol uchun; qo'shgan/tayinlangan boshqaruvchilar
    """
    ALTER TABLE group_admins RENAME TO group_links;
    CREATE TABLE group_managers (
        group_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        added_by INTEGER,
        PRIMARY KEY (group_id, user_id)
    );
    """,
    # 4 — ertalabki xabar, o'z tabrik matni, boshqaruvchi taklif havolalari
    """
    ALTER TABLE groups ADD COLUMN last_digest TEXT;
    ALTER TABLE group_links ADD COLUMN digest INTEGER NOT NULL DEFAULT 1;
    ALTER TABLE group_settings ADD COLUMN greeting_template TEXT;
    CREATE TABLE manager_invites (
        token TEXT PRIMARY KEY,
        group_id INTEGER NOT NULL,
        created_by INTEGER,
        created_at TEXT NOT NULL,
        used_by INTEGER
    );
    """,
]

SETTING_FIELDS = {
    "notify_time", "remind_days", "upcoming_days", "sticker_file_id", "greeting_template",
}
INVITE_LIFETIME = timedelta(days=7)
DIGEST_LEAD = timedelta(hours=1)  # ertalabki xabar tabrikdan shuncha oldin


def _to_birthday(row: aiosqlite.Row) -> Birthday:
    return Birthday(
        id=row["id"],
        group_id=row["group_id"],
        name=row["name"],
        day=row["day"],
        month=row["month"],
        year=row["year"],
        user_id=row["user_id"],
    )


def _to_group(row: aiosqlite.Row) -> Group:
    return Group(group_id=row["group_id"], title=row["title"], active=bool(row["active"]))


def _date_condition(d: date) -> tuple[str, list[int]]:
    """Shu sanada nishonlanadigan yozuvlar uchun WHERE sharti (29.02 ni hisobga olgan holda)."""
    keys = birthday_keys_for(d)
    condition = " OR ".join("(b.day = ? AND b.month = ?)" for _ in keys)
    return f"({condition})", [value for key in keys for value in key]


class Database:
    def __init__(self, path: Union[str, Path], default_notify_time: time):
        self._path = str(path)
        self._default_time = format_time(default_notify_time)
        self._conn: Optional[aiosqlite.Connection] = None

    # ---------- Ulanish ----------

    async def connect(self):
        if self._path != ":memory:":
            Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        # isolation_level=None — autocommit; ko'p qadamli o'zgarishlar _transaction() da
        self._conn = await aiosqlite.connect(self._path, isolation_level=None)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA journal_mode = WAL")
        await self._conn.execute("PRAGMA busy_timeout = 5000")
        await self._migrate()

    async def close(self):
        if self._conn is not None:
            await self._conn.close()
            self._conn = None

    @property
    def conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("Baza ulanmagan. Avval connect() ni chaqiring.")
        return self._conn

    async def _migrate(self):
        async with self.conn.execute("PRAGMA user_version") as cursor:
            version = (await cursor.fetchone())[0]
        for number, script in enumerate(MIGRATIONS[version:], start=version + 1):
            await self.conn.executescript(
                f"BEGIN; {script} PRAGMA user_version = {number}; COMMIT;"
            )

    @asynccontextmanager
    async def _transaction(self):
        await self.conn.execute("BEGIN")
        try:
            yield
        except BaseException:
            await self.conn.execute("ROLLBACK")
            raise
        await self.conn.execute("COMMIT")

    async def _fetchall(self, query: str, params: tuple = ()) -> list[aiosqlite.Row]:
        async with self.conn.execute(query, params) as cursor:
            return list(await cursor.fetchall())

    async def _fetchone(self, query: str, params: tuple = ()) -> Optional[aiosqlite.Row]:
        async with self.conn.execute(query, params) as cursor:
            return await cursor.fetchone()

    async def _execute(self, query: str, params: tuple = ()) -> aiosqlite.Cursor:
        cursor = await self.conn.execute(query, params)
        await cursor.close()
        return cursor

    # ---------- Tug'ilgan kunlar ----------

    async def add_birthday(
        self,
        group_id: int,
        name: str,
        day: int,
        month: int,
        year: Optional[int] = None,
        added_by: Optional[int] = None,
        user_id: Optional[int] = None,
    ) -> int:
        cursor = await self._execute(
            """
            INSERT INTO birthdays (group_id, name, day, month, year, added_by, user_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (group_id, name, day, month, year, added_by, user_id),
        )
        return cursor.lastrowid

    async def get_birthday(self, group_id: int, record_id: int) -> Optional[Birthday]:
        row = await self._fetchone(
            "SELECT * FROM birthdays WHERE group_id = ? AND id = ?", (group_id, record_id)
        )
        return _to_birthday(row) if row else None

    async def set_birthday_user(self, group_id: int, record_id: int, user_id: int) -> bool:
        """Yozuvni Telegram foydalanuvchisiga bog'laydi — tabrikda u belgilanadi."""
        cursor = await self._execute(
            "UPDATE birthdays SET user_id = ? WHERE group_id = ? AND id = ?",
            (user_id, group_id, record_id),
        )
        return cursor.rowcount == 1

    async def get_birthday_by_user(self, group_id: int, user_id: int) -> Optional[Birthday]:
        """Telegram foydalanuvchisiga bog'langan yozuv (a'zo o'z yozuvini boshqaradi)."""
        row = await self._fetchone(
            "SELECT * FROM birthdays WHERE group_id = ? AND user_id = ? ORDER BY id LIMIT 1",
            (group_id, user_id),
        )
        return _to_birthday(row) if row else None

    async def update_birthday(
        self,
        group_id: int,
        record_id: int,
        name: str,
        day: int,
        month: int,
        year: Optional[int],
    ) -> bool:
        """Ism va sanani yangilaydi. Sana o'zgargani uchun yuborilgan belgilar tozalanadi."""
        cursor = await self._execute(
            """
            UPDATE birthdays
            SET name = ?, day = ?, month = ?, year = ?,
                last_notified = NULL, last_reminded = NULL
            WHERE group_id = ? AND id = ?
            """,
            (name, day, month, year, group_id, record_id),
        )
        return cursor.rowcount == 1

    async def remove_birthday(self, group_id: int, record_id: int) -> bool:
        cursor = await self._execute(
            "DELETE FROM birthdays WHERE group_id = ? AND id = ?", (group_id, record_id)
        )
        return cursor.rowcount == 1

    async def list_birthdays(
        self, group_id: int, limit: Optional[int] = None, offset: int = 0
    ) -> list[Birthday]:
        rows = await self._fetchall(
            """
            SELECT * FROM birthdays
            WHERE group_id = ?
            ORDER BY month, day, name COLLATE NOCASE
            LIMIT ? OFFSET ?
            """,
            (group_id, -1 if limit is None else limit, offset),
        )
        return [_to_birthday(row) for row in rows]

    async def count_birthdays(self, group_id: int) -> int:
        row = await self._fetchone(
            "SELECT count(*) FROM birthdays WHERE group_id = ?", (group_id,)
        )
        return row[0]

    async def find_birthdays(self, group_id: int, text: str, limit: int = 50) -> list[Birthday]:
        # SQLite LIKE faqat lotin harflarida katta-kichikni farqlamaydi —
        # kirill ismlar uchun ham ishlashi uchun Python'da qidiramiz
        needle = text.casefold()
        found = [b for b in await self.list_birthdays(group_id) if needle in b.name.casefold()]
        return found[:limit]

    async def find_same_name(self, group_id: int, name: str) -> list[Birthday]:
        """Ismi aynan shunday yozuvlar (bo'shliq va katta-kichik harf hisobga olinmaydi)."""
        key = " ".join(name.split()).casefold()
        return [b for b in await self.list_birthdays(group_id) if b.name.casefold() == key]

    async def get_upcoming(self, group_id: int, today: date, days_ahead: int) -> list[Upcoming]:
        """Kelasi N kun ichidagi tug'ilgan kunlar, eng yaqini birinchi."""
        result = []
        for birthday in await self.list_birthdays(group_id):
            bday = next_birthday(birthday.day, birthday.month, today)
            days_left = (bday - today).days
            if days_left <= days_ahead:
                result.append(Upcoming(birthday=birthday, date=bday, days_left=days_left))
        result.sort(key=lambda item: item.days_left)
        return result

    async def migrate_group(self, old_id: int, new_id: int):
        """Guruh supergroupga aylanganda chat ID o'zgaradi — yozuvlarni ko'chiradi."""
        async with self._transaction():
            await self._execute(
                "UPDATE birthdays SET group_id = ? WHERE group_id = ?", (new_id, old_id)
            )
            await self._execute(
                "UPDATE OR IGNORE group_settings SET group_id = ? WHERE group_id = ?",
                (new_id, old_id),
            )
            await self._execute(
                "UPDATE OR IGNORE groups SET group_id = ? WHERE group_id = ?", (new_id, old_id)
            )
            await self._execute(
                "UPDATE OR IGNORE group_links SET group_id = ? WHERE group_id = ?",
                (new_id, old_id),
            )
            await self._execute(
                "UPDATE OR IGNORE group_managers SET group_id = ? WHERE group_id = ?",
                (new_id, old_id),
            )
            await self._execute(
                "UPDATE manager_invites SET group_id = ? WHERE group_id = ?", (new_id, old_id)
            )

    # ---------- Tabrik va eslatmalar ----------

    async def get_pending_greetings(
        self, on_date: date, at: time
    ) -> list[tuple[Birthday, Optional[str]]]:
        """
        Shu sanada nishonlanadigan, guruh tabrik vaqti kelgan va hali tabrik
        yuborilmagan yozuvlar — guruh stikeri bilan. Kabisa bo'lmagan yilda
        29.02 lar 28.02 da qaytadi. Bot chiqarilgan (nofaol) guruhlar o'tkazib
        yuboriladi.
        """
        condition, params = _date_condition(on_date)
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
        return [(_to_birthday(row), row["sticker_file_id"]) for row in rows]

    async def get_pending_reminders(self, on_date: date, at: time) -> list[Upcoming]:
        """
        Oldindan eslatma yoqilgan guruhlarda, remind_days kundan keyin tug'ilgan
        kuni bo'ladigan va bugun hali eslatilmagan yozuvlar.
        """
        at_text = format_time(at)
        remind_values = await self._fetchall(
            """
            SELECT DISTINCT remind_days FROM group_settings
            WHERE remind_days > 0 AND COALESCE(notify_time, ?) <= ?
            """,
            (self._default_time, at_text),
        )
        result = []
        for (remind_days,) in remind_values:
            target = on_date + timedelta(days=remind_days)
            condition, params = _date_condition(target)
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
            result.extend(
                Upcoming(birthday=_to_birthday(row), date=target, days_left=remind_days)
                for row in rows
            )
        return result

    async def mark_notified(self, record_id: int, on_date: date):
        await self._execute(
            "UPDATE birthdays SET last_notified = ? WHERE id = ?",
            (on_date.isoformat(), record_id),
        )

    async def mark_reminded(self, record_id: int, on_date: date):
        await self._execute(
            "UPDATE birthdays SET last_reminded = ? WHERE id = ?",
            (on_date.isoformat(), record_id),
        )

    # ---------- Guruh sozlamalari ----------

    async def get_settings(self, group_id: int) -> GroupSettings:
        """Guruh sozlamalari; saqlanmagan qiymatlar o'rniga default qaytariladi."""
        row = await self._fetchone(
            "SELECT * FROM group_settings WHERE group_id = ?", (group_id,)
        )
        default_time = parse_time(self._default_time)
        if row is None:
            return GroupSettings(notify_time=default_time)
        return GroupSettings(
            notify_time=parse_time(row["notify_time"]) if row["notify_time"] else default_time,
            remind_days=row["remind_days"],
            upcoming_days=row["upcoming_days"],
            sticker_file_id=row["sticker_file_id"],
            greeting_template=row["greeting_template"],
        )

    async def set_setting(self, group_id: int, field: str, value: Any):
        if field not in SETTING_FIELDS:
            raise ValueError(f"Noma'lum sozlama: {field}")
        if isinstance(value, time):
            value = format_time(value)
        # field faqat oq ro'yxatdan — SQL ga qo'yish xavfsiz
        await self._execute(
            f"""
            INSERT INTO group_settings (group_id, {field}) VALUES (?, ?)
            ON CONFLICT (group_id) DO UPDATE SET {field} = excluded.{field}
            """,
            (group_id, value),
        )

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

    async def link_user(self, user_id: int, group_id: int):
        await self._execute(
            "INSERT OR IGNORE INTO group_links (user_id, group_id) VALUES (?, ?)",
            (user_id, group_id),
        )

    async def unlink_user(self, user_id: int, group_id: int):
        await self._execute(
            "DELETE FROM group_links WHERE user_id = ? AND group_id = ?", (user_id, group_id)
        )

    async def linked_users(self, group_id: int) -> list[int]:
        rows = await self._fetchall(
            "SELECT user_id FROM group_links WHERE group_id = ? ORDER BY user_id", (group_id,)
        )
        return [row[0] for row in rows]

    async def linked_groups(self, user_id: int) -> list[Group]:
        """Foydalanuvchi bog'langan faol guruhlar (rol bu yerda tekshirilmaydi)."""
        rows = await self._fetchall(
            """
            SELECT g.* FROM group_links a
            JOIN groups g ON g.group_id = a.group_id
            WHERE a.user_id = ? AND g.active = 1
            ORDER BY g.title COLLATE NOCASE, g.group_id
            """,
            (user_id,),
        )
        return [_to_group(row) for row in rows]

    async def add_manager(self, group_id: int, user_id: int, added_by: Optional[int] = None):
        await self._execute(
            "INSERT OR IGNORE INTO group_managers (group_id, user_id, added_by) VALUES (?, ?, ?)",
            (group_id, user_id, added_by),
        )

    async def remove_manager(self, group_id: int, user_id: int) -> bool:
        cursor = await self._execute(
            "DELETE FROM group_managers WHERE group_id = ? AND user_id = ?", (group_id, user_id)
        )
        return cursor.rowcount == 1

    async def is_manager(self, group_id: int, user_id: int) -> bool:
        row = await self._fetchone(
            "SELECT 1 FROM group_managers WHERE group_id = ? AND user_id = ?", (group_id, user_id)
        )
        return row is not None

    async def list_managers(self, group_id: int) -> list[int]:
        rows = await self._fetchall(
            "SELECT user_id FROM group_managers WHERE group_id = ? ORDER BY user_id", (group_id,)
        )
        return [row[0] for row in rows]

    # ---------- Boshqaruvchi taklif havolalari ----------

    async def create_invite(self, group_id: int, created_by: Optional[int], today: date) -> str:
        token = secrets.token_urlsafe(9)
        await self._execute(
            "INSERT INTO manager_invites (token, group_id, created_by, created_at) VALUES (?, ?, ?, ?)",
            (token, group_id, created_by, today.isoformat()),
        )
        return token

    async def use_invite(
        self, token: str, user_id: int, today: date
    ) -> Optional[tuple[int, Optional[int]]]:
        """
        Havolani ishlatadi: (guruh, taklif qilgan) yoki None — havola yo'q,
        ishlatilgan yoki eskirgan. UPDATE shartli, shuning uchun bir martalik.
        """
        oldest = (today - INVITE_LIFETIME).isoformat()
        cursor = await self._execute(
            """
            UPDATE manager_invites SET used_by = ?
            WHERE token = ? AND used_by IS NULL AND created_at > ?
            """,
            (user_id, token, oldest),
        )
        if cursor.rowcount != 1:
            return None
        row = await self._fetchone(
            "SELECT group_id, created_by FROM manager_invites WHERE token = ?", (token,)
        )
        return row["group_id"], row["created_by"]

    # ---------- Ertalabki xabar ----------

    async def get_digest_due(self, on_date: date, at: time) -> list[Group]:
        """Bugun hali ertalabki xabar ketmagan, vaqti (tabrikdan 1 soat oldin) kelgan guruhlar."""
        rows = await self._fetchall(
            """
            SELECT g.*, COALESCE(s.notify_time, ?) AS notify_time
            FROM groups g
            LEFT JOIN group_settings s ON s.group_id = g.group_id
            WHERE g.active = 1 AND g.last_digest IS NOT ?
            ORDER BY g.group_id
            """,
            (self._default_time, on_date.isoformat()),
        )
        due = []
        for row in rows:
            notify = datetime.combine(on_date, parse_time(row["notify_time"]))
            # Kun boshidan oldinga o'tib ketmaydi: 00:30 → 00:00
            digest_at = max(notify - DIGEST_LEAD, datetime.combine(on_date, time(0, 0)))
            if digest_at.time() <= at:
                due.append(_to_group(row))
        return due

    async def mark_digest_sent(self, group_id: int, on_date: date):
        await self._execute(
            "UPDATE groups SET last_digest = ? WHERE group_id = ?", (on_date.isoformat(), group_id)
        )

    async def get_digest_enabled(self, user_id: int, group_id: int) -> bool:
        row = await self._fetchone(
            "SELECT digest FROM group_links WHERE user_id = ? AND group_id = ?", (user_id, group_id)
        )
        return row is None or bool(row["digest"])

    async def set_digest_enabled(self, user_id: int, group_id: int, enabled: bool):
        await self._execute(
            """
            INSERT INTO group_links (user_id, group_id, digest) VALUES (?, ?, ?)
            ON CONFLICT (user_id, group_id) DO UPDATE SET digest = excluded.digest
            """,
            (user_id, group_id, int(enabled)),
        )
