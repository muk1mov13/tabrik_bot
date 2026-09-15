"""
database.py — PostgreSQL (asyncpg) orqali tug'ilgan kunlar ma'lumotlarini
saqlash va boshqarish.
"""

import os
from datetime import date
from typing import Optional

import asyncpg

from dotenv import load_dotenv

load_dotenv()

_pool: Optional[asyncpg.Pool] = None


async def init_db():
    """Connection pool ochadi va kerakli jadvalni yaratadi (agar mavjud bo'lmasa)."""
    global _pool
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError(
            "DATABASE_URL topilmadi. Masalan:\n"
            "  export DATABASE_URL='postgresql://user:password@localhost:5432/dbname'"
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

        default_group_id = os.getenv("DEFAULT_GROUP_ID")
        if default_group_id:
            try:
                target_gid = int(default_group_id)
                # Shaxsiy chatlarda kiritilgan yozuvlarni (group_id > 0) default guruhga o'tkazish
                updated = await conn.execute(
                    "UPDATE birthdays SET group_id = $1 WHERE group_id > 0",
                    target_gid,
                )
            except ValueError:
                pass


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
        record_id = await conn.fetchval(query, group_id, name, day, month, year, added_by)
        return record_id


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
        ORDER BY month, day
    """
    async with get_pool().acquire() as conn:
        return await conn.fetch(query, group_id)


async def get_birthdays_for_date(day: int, month: int) -> list[asyncpg.Record]:
    """Barcha guruhlar bo'yicha, berilgan kun/oyga to'g'ri keladigan yozuvlar."""
    query = "SELECT * FROM birthdays WHERE day = $1 AND month = $2"
    async with get_pool().acquire() as conn:
        return await conn.fetch(query, day, month)


async def get_upcoming(group_id: int, days_ahead: int = 7) -> list[dict]:
    """Kelasi N kun ichidagi tug'ilgan kunlarni (necha kun qolganini hisoblab) qaytaradi."""
    today = date.today()
    rows = await list_birthdays(group_id)
    result = []
    for row in rows:
        this_year = today.year
        try:
            bday_this_year = date(this_year, row["month"], row["day"])
        except ValueError:
            continue
        if bday_this_year < today:
            bday_this_year = date(this_year + 1, row["month"], row["day"])
        delta = (bday_this_year - today).days
        if 0 <= delta <= days_ahead:
            result.append({"row": row, "days_left": delta})
    result.sort(key=lambda x: x["days_left"])
    return result
