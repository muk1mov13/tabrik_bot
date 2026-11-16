# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Telegram bot (aiogram 3.x + APScheduler + PostgreSQL via asyncpg) that stores people's birthdays per Telegram group and posts a greeting to the group once on the day. All user-facing text, comments and docstrings are in Uzbek (Latin script) — keep new strings and comments consistent with that.

## Commands

```bash
pip install -r requirements-dev.txt   # runtime deps + pytest
python bot.py                         # reads .env via python-dotenv (see .env.example)
pytest                                # all tests (pytest.ini sets pythonpath=.)
pytest tests/test_utils.py::test_calc_age   # single test
```

No Docker. Production runs on Ubuntu as a systemd service (`deploy/birthdate-bot.service`, instructions in `deploy/DEPLOY.md`); logs via `journalctl -u birthdate-bot`.

## Configuration (env vars)

`BOT_TOKEN`, `DATABASE_URL` (required); `DEFAULT_GROUP_ID`, `NOTIFICATION_TIME` (HH:MM, default 08:00), `TIMEZONE` (default Asia/Tashkent). `DEFAULT_GROUP_ID` makes commands in a private chat operate on that group.

## Architecture

Flat module layout, no packages:

- `bot.py` — entry point: `db.init_db()` → `Bot`/`Dispatcher` (HTML parse mode) → `handlers.router` + `group_settings.router` → `setup_scheduler(bot)` → long polling; shuts everything down in `finally`.
- `utils.py` — shared, DB-free logic: `TZ`/`now()`/`today()` (always use these, never `date.today()` — server runs in UTC), `MONTH_NAMES`, `ADD_ARGS_PATTERN` (name is optional), `validate_date`, `parse_time`, `mention()` (escapes the name; links to `tg://user?id=` when a Telegram user is attached), Feb-29 handling (`birthday_in_year`, `next_birthday`, `birthday_keys_for`).
- `permissions.py` — `get_target_group_id(chat)` (private chat → `DEFAULT_GROUP_ID`) and `can_edit(message, bot)` admin check used by every mutating command.
- `database.py` — module-level asyncpg pool via `get_pool()`. No migration system: schema changes go into `init_db()` and must be idempotent (`ADD COLUMN IF NOT EXISTS`, etc.). Tables: `birthdays(..., user_id, last_notified, last_reminded)` and `group_settings(group_id PK, notify_time, remind_days, upcoming_days, sticker_file_id)`. A group with no settings row uses `DEFAULT_SETTINGS`; `set_setting` upserts one whitelisted column.
- `handlers.py` — birthday commands (`/add`, `/edit`, `/list` with `ListPage` callback pagination, `/find`, `/upcoming`, `/remove`) and supergroup migration (`migrate_to_chat_id`). `group_settings.py` — `/settings`, `/setsticker`. Command args come from `CommandObject.args` so `/cmd@BotName` works. All user-supplied text must go through `escape`/`mention` because parse mode is HTML.
- `scheduler.py` — a single job runs every minute (and once at startup). It sends greetings for groups whose `notify_time` has passed and reminders `remind_days` ahead. `last_notified` / `last_reminded` are set only after a successful send, so each one goes out at most once per day, including across restarts. `update_birthday` clears both marks.

Tests (`tests/`) cover pure logic only (utils, arg parsing, message builders); SQL in `database.py` is not covered by tests.
