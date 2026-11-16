"""
database.py — PostgreSQL (asyncpg) orqali tug'ilgan kunlar va guruh
sozlamalarini saqlash va boshqarish.
"""

import os
from datetime import date, time, timedelta
from typing import Any, Optional

import asyncpg
from dotenv import load_dotenv

from utils import DEFAULT_NOTIFY_TIME, birthday_keys_for, escape_like, next_birthday, today

load_dotenv()

_pool: Optional[asyncpg.Pool] = None

DEFAULT_SETTINGS = {
    "notify_time": DEFAULT_NOTIFY_TIME,
    "remind_days": 0,
    "upcoming_days": 7,
    "sticker_file_id": None,
}


async def init_db():
    """Connection pool ochadi va kerakli jadvallarni yaratadi (agar mavjud bo'lmasa)."""
    global _pool
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError(
            "DATABASE_URL topilmadi. .env fayliga qo'shing, masalan:\n"
            "  DATABASE_URL=postgresql://user:password@localhost:5432/dbname"
        )

    _pool = await asyncpg.create_pool(dsn=database_url, min_size=1, max_size=5)

    async with _pool.acquire() as conn:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS birthdays (
                id SERIAL PRIMARY KEY,
                group_id BIGINT NOT NULL,
                name TEXT NOT NULL,
                day SMALLINT NOT NULL,
                month SMALLINT NOT NULL,
                year SMALLINT,
                added_by BIGINT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
        # Eski bazalar uchun ham ishlaydigan (idempotent) o'zgarishlar
        await conn.execute(
            """
            ALTER TABLE birthdays
                ADD COLUMN IF NOT EXISTS last_notified DATE,
                ADD COLUMN IF NOT EXISTS last_reminded DATE,
                ADD COLUMN IF NOT EXISTS user_id BIGINT
            """
        )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS birthdays_group_idx ON birthdays (group_id)"
        )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS birthdays_date_idx ON birthdays (month, day)"
        )
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS group_settings (
                group_id BIGINT PRIMARY KEY,
                notify_time TIME,
                remind_days SMALLINT NOT NULL DEFAULT 0,
                upcoming_days SMALLINT NOT NULL DEFAULT 7,
                sticker_file_id TEXT
            )
            """
        )


async def close_db():
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("Baza hali ishga tushirilmagan. Avval init_db() ni chaqiring.")
    return _pool


# ---------- Tug'ilgan kunlar ----------

async def add_birthday(
    group_id: int,
    name: str,
    day: int,
    month: int,
    year: Optional[int] = None,
    added_by: Optional[int] = None,
    user_id: Optional[int] = None,
) -> int:
    query = """
        INSERT INTO birthdays (group_id, name, day, month, year, added_by, user_id)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        RETURNING id
    """
    async with get_pool().acquire() as conn:
        return await conn.fetchval(
            query, group_id, name, day, month, year, added_by, user_id
        )


async def get_birthday(group_id: int, record_id: int) -> Optional[asyncpg.Record]:
    query = "SELECT * FROM birthdays WHERE group_id = $1 AND id = $2"
    async with get_pool().acquire() as conn:
        return await conn.fetchrow(query, group_id, record_id)


async def update_birthday(
    group_id: int, record_id: int, name: str, day: int, month: int, year: Optional[int]
) -> bool:
    """Ism va sanani yangilaydi. Sana o'zgargani uchun yuborilgan belgilar tozalanadi."""
    query = """
        UPDATE birthdays
        SET name = $3, day = $4, month = $5, year = $6,
            last_notified = NULL, last_reminded = NULL
        WHERE group_id = $1 AND id = $2
    """
    async with get_pool().acquire() as conn:
        result = await conn.execute(query, group_id, record_id, name, day, month, year)
        return result.endswith(" 1")


async def remove_birthday(group_id: int, record_id: int) -> bool:
    query = "DELETE FROM birthdays WHERE group_id = $1 AND id = $2"
    async with get_pool().acquire() as conn:
        result = await conn.execute(query, group_id, record_id)
        # result format: "DELETE <n>"
        return result.endswith(" 1")


async def list_birthdays(
    group_id: int, limit: Optional[int] = None, offset: int = 0
) -> list[asyncpg.Record]:
    query = """
        SELECT * FROM birthdays
        WHERE group_id = $1
        ORDER BY month, day, name
        LIMIT $2 OFFSET $3
    """
    async with get_pool().acquire() as conn:
        return await conn.fetch(query, group_id, limit, offset)


async def count_birthdays(group_id: int) -> int:
    query = "SELECT count(*) FROM birthdays WHERE group_id = $1"
    async with get_pool().acquire() as conn:
        return await conn.fetchval(query, group_id)


async def find_birthdays(group_id: int, text: str, limit: int = 50) -> list[asyncpg.Record]:
    query = r"""
        SELECT * FROM birthdays
        WHERE group_id = $1 AND name ILIKE '%' || $2 || '%' ESCAPE '\'
        ORDER BY month, day, name
        LIMIT $3
    """
    async with get_pool().acquire() as conn:
        return await conn.fetch(query, group_id, escape_like(text), limit)


async def get_upcoming(group_id: int, days_ahead: int = 7) -> list[dict]:
    """Kelasi N kun ichidagi tug'ilgan kunlarni (necha kun qolganini hisoblab) qaytaradi."""
    current = today()
    result = []
    for row in await list_birthdays(group_id):
        bday = next_birthday(row["day"], row["month"], current)
        delta = (bday - current).days
        if delta <= days_ahead:
            result.append({"row": row, "days_left": delta, "date": bday})
    result.sort(key=lambda x: x["days_left"])
    return result


async def migrate_group(old_id: int, new_id: int):
    """Guruh supergroupga aylanganda chat ID o'zgaradi — yozuvlarni ko'chiradi."""
    async with get_pool().acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                "UPDATE birthdays SET group_id = $2 WHERE group_id = $1", old_id, new_id
            )
            await conn.execute(
                """
                UPDATE group_settings SET group_id = $2
                WHERE group_id = $1
                  AND NOT EXISTS (SELECT 1 FROM group_settings WHERE group_id = $2)
                """,
                old_id,
                new_id,
            )


# ---------- Tabrik va eslatmalar ----------

def _keys_arrays(d: date) -> tuple[list[int], list[int]]:
    keys = birthday_keys_for(d)
    return [k[0] for k in keys], [k[1] for k in keys]


async def get_pending_birthdays(on_date: date, at: time) -> list[asyncpg.Record]:
    """
    Barcha guruhlar bo'yicha shu sanada nishonlanadigan, guruh tabrik vaqti
    kelgan va hali tabrik yuborilmagan yozuvlar (guruh stikeri bilan).
    Kabisa bo'lmagan yilda 29.02 lar 28.02 da qaytadi.
    """
    days, months = _keys_arrays(on_date)
    query = """
        SELECT b.*, s.sticker_file_id
        FROM birthdays b
        JOIN unnest($1::smallint[], $2::smallint[]) AS k(day, month)
          ON b.day = k.day AND b.month = k.month
        LEFT JOIN group_settings s ON s.group_id = b.group_id
        WHERE b.last_notified IS DISTINCT FROM $3
          AND COALESCE(s.notify_time, $4) <= $5
    """
    async with get_pool().acquire() as conn:
        return await conn.fetch(query, days, months, on_date, DEFAULT_NOTIFY_TIME, at)


async def get_pending_reminders(on_date: date, at: time) -> list[dict]:
    """
    Oldindan eslatma yoqilgan guruhlarda, remind_days kundan keyin
    tug'ilgan kuni bo'ladigan va bugun hali eslatilmagan yozuvlar.
    """
    result = []
    async with get_pool().acquire() as conn:
        remind_values = await conn.fetch(
            """
            SELECT DISTINCT remind_days FROM group_settings
            WHERE remind_days > 0 AND COALESCE(notify_time, $1) <= $2
            """,
            DEFAULT_NOTIFY_TIME,
            at,
        )
        for value in remind_values:
            remind_days = value["remind_days"]
            target = on_date + timedelta(days=remind_days)
            days, months = _keys_arrays(target)
            rows = await conn.fetch(
                """
                SELECT b.* FROM birthdays b
                JOIN unnest($1::smallint[], $2::smallint[]) AS k(day, month)
                  ON b.day = k.day AND b.month = k.month
                JOIN group_settings s ON s.group_id = b.group_id
                WHERE s.remind_days = $3
                  AND COALESCE(s.notify_time, $4) <= $5
                  AND b.last_reminded IS DISTINCT FROM $6
                """,
                days,
                months,
                remind_days,
                DEFAULT_NOTIFY_TIME,
                at,
                on_date,
            )
            result.extend({"row": row, "days_left": remind_days, "date": target} for row in rows)
    return result


async def mark_notified(record_id: int, on_date: date):
    query = "UPDATE birthdays SET last_notified = $2 WHERE id = $1"
    async with get_pool().acquire() as conn:
        await conn.execute(query, record_id, on_date)


async def mark_reminded(record_id: int, on_date: date):
    query = "UPDATE birthdays SET last_reminded = $2 WHERE id = $1"
    async with get_pool().acquire() as conn:
        await conn.execute(query, record_id, on_date)


# ---------- Guruh sozlamalari ----------

SETTING_FIELDS = {"notify_time", "remind_days", "upcoming_days", "sticker_file_id"}


async def get_settings(group_id: int) -> dict[str, Any]:
    """Guruh sozlamalari; saqlanmagan qiymatlar o'rniga default qaytariladi."""
    query = "SELECT * FROM group_settings WHERE group_id = $1"
    async with get_pool().acquire() as conn:
        row = await conn.fetchrow(query, group_id)
    settings = dict(DEFAULT_SETTINGS)
    if row:
        for field in SETTING_FIELDS:
            if row[field] is not None:
                settings[field] = row[field]
    return settings


async def set_setting(group_id: int, field: str, value: Any):
    if field not in SETTING_FIELDS:
        raise ValueError(f"Noma'lum sozlama: {field}")
    # field faqat oq ro'yxatdan — SQL ga qo'yish xavfsiz
    query = f"""
        INSERT INTO group_settings (group_id, {field}) VALUES ($1, $2)
        ON CONFLICT (group_id) DO UPDATE SET {field} = EXCLUDED.{field}
    """
    async with get_pool().acquire() as conn:
        await conn.execute(query, group_id, value)
