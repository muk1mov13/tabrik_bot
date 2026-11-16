"""
database.py — PostgreSQL (asyncpg) orqali tug'ilgan kunlar ma'lumotlarini
saqlash va boshqarish.
"""

import os
from datetime import date
from typing import Optional

import asyncpg
from dotenv import load_dotenv

from utils import birthday_in_year, birthday_keys_for, today

load_dotenv()

_pool: Optional[asyncpg.Pool] = None


async def init_db():
    """Connection pool ochadi va kerakli jadvalni yaratadi (agar mavjud bo'lmasa)."""
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
            "ALTER TABLE birthdays ADD COLUMN IF NOT EXISTS last_notified DATE"
        )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS birthdays_group_idx ON birthdays (group_id)"
        )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS birthdays_date_idx ON birthdays (month, day)"
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


async def add_birthday(
    group_id: int,
    name: str,
    day: int,
    month: int,
    year: Optional[int] = None,
    added_by: Optional[int] = None,
) -> int:
    query = """
        INSERT INTO birthdays (group_id, name, day, month, year, added_by)
        VALUES ($1, $2, $3, $4, $5, $6)
        RETURNING id
    """
    async with get_pool().acquire() as conn:
        return await conn.fetchval(query, group_id, name, day, month, year, added_by)


async def remove_birthday(group_id: int, record_id: int) -> bool:
    query = "DELETE FROM birthdays WHERE group_id = $1 AND id = $2"
    async with get_pool().acquire() as conn:
        result = await conn.execute(query, group_id, record_id)
        # result format: "DELETE <n>"
        return result.endswith(" 1")


async def list_birthdays(group_id: int) -> list[asyncpg.Record]:
    query = """
        SELECT * FROM birthdays
        WHERE group_id = $1
        ORDER BY month, day, name
    """
    async with get_pool().acquire() as conn:
        return await conn.fetch(query, group_id)


async def get_pending_birthdays(on_date: date) -> list[asyncpg.Record]:
    """
    Barcha guruhlar bo'yicha shu sanada nishonlanadigan va hali tabrik
    yuborilmagan yozuvlar. Kabisa bo'lmagan yilda 29.02 lar 28.02 da qaytadi.
    """
    keys = birthday_keys_for(on_date)
    days = [k[0] for k in keys]
    months = [k[1] for k in keys]
    query = """
        SELECT b.* FROM birthdays b
        JOIN unnest($1::smallint[], $2::smallint[]) AS k(day, month)
          ON b.day = k.day AND b.month = k.month
        WHERE b.last_notified IS DISTINCT FROM $3
    """
    async with get_pool().acquire() as conn:
        return await conn.fetch(query, days, months, on_date)


async def mark_notified(record_id: int, on_date: date):
    query = "UPDATE birthdays SET last_notified = $2 WHERE id = $1"
    async with get_pool().acquire() as conn:
        await conn.execute(query, record_id, on_date)


async def get_upcoming(group_id: int, days_ahead: int = 7) -> list[dict]:
    """Kelasi N kun ichidagi tug'ilgan kunlarni (necha kun qolganini hisoblab) qaytaradi."""
    current = today()
    rows = await list_birthdays(group_id)
    result = []
    for row in rows:
        bday = birthday_in_year(row["day"], row["month"], current.year)
        if bday < current:
            bday = birthday_in_year(row["day"], row["month"], current.year + 1)
        delta = (bday - current).days
        if 0 <= delta <= days_ahead:
            result.append({"row": row, "days_left": delta, "date": bday})
    result.sort(key=lambda x: x["days_left"])
    return result
