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

- `bot.py` — entry point: `db.init_db()` → `Bot`/`Dispatcher` (HTML parse mode) → `handlers.router` → `setup_scheduler(bot)` → `notify_if_missed` → long polling; shuts everything down in `finally`.
- `utils.py` — shared, DB-free logic: `TZ`/`today()` (always use these, never `date.today()` — server runs in UTC), `MONTH_NAMES`, `ADD_ARGS_PATTERN`, `validate_date`, Feb-29 handling (`birthday_in_year`, `birthday_keys_for`). Tests cover this module only.
- `database.py` — module-level asyncpg pool via `get_pool()`. No migration system: schema changes go into `init_db()` and must be idempotent (`ADD COLUMN IF NOT EXISTS`, etc.). Table `birthdays(id, group_id, name, day, month, year NULL, added_by, created_at, last_notified DATE)`.
- `handlers.py` — single aiogram `Router`. `/add` and `/remove` are admin-only via `can_edit()` (`bot.get_chat_member`; in private chat checks admin of `DEFAULT_GROUP_ID`). Command args come from `CommandObject.args` so `/cmd@BotName` works. All user-supplied text must be `html.escape`d because parse mode is HTML. Long replies go through `answer_long()`.
- `scheduler.py` — one daily cron job at `NOTIFICATION_TIME` in `TZ`. Duplicate greetings are prevented by `last_notified`: `get_pending_birthdays()` skips rows already notified today and `mark_notified()` is called only after a successful send, so restarts / `notify_if_missed` at startup are safe.
