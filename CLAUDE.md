# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Telegram bot (aiogram 3.x + APScheduler + SQLite via aiosqlite) that stores birthdays per Telegram group, greets the person in the group once on the day, and optionally reminds N days ahead. All user-facing text, comments and docstrings are in Uzbek (Latin script) — keep new strings and comments consistent with that.

## Commands

```bash
pip install -r requirements-dev.txt          # runtime deps + pytest, pytest-asyncio
python -m birthday_bot                       # run; reads .env (see .env.example)
pytest                                       # all tests (asyncio_mode=auto in pytest.ini)
pytest tests/test_database.py::test_crud     # single test
```

No Docker. Production runs on Ubuntu as a systemd service (`deploy/birthdate-bot.service`, steps in `deploy/DEPLOY.md`); the unit uses `ProtectSystem=strict`, so the bot can only write to `/opt/birthdate-bot/data`.

Env vars: `BOT_TOKEN` (required), `DATABASE_PATH` (default `data/birthdays.db`), `DEFAULT_GROUP_ID`, `NOTIFICATION_TIME` (HH:MM default for groups without their own), `TIMEZONE` (default Asia/Tashkent). `config.load_config()` validates them and raises `ConfigError` at startup.

## Architecture

Package `birthday_bot/`:

- **Dependency injection, no globals.** `__main__.py` builds `Config` and `Database` and passes them as `Dispatcher(db=..., config=...)` workflow data, so handlers declare `db: Database, config: Config` parameters. The scheduler gets them explicitly. To add a handler, put it in a router under `handlers/` (`common`, `birthdays`, `settings`); `handlers.build_router()` combines the routers.
- **Pure logic is separate from aiogram/DB:** `dates.py` (all functions take "today" as a parameter; get the current time only through `dates.now(config.timezone)`, never `date.today()`, because servers run in UTC), `parsing.py` (raises `ParseError`), `texts.py` (all messages; user input must go through `mention()`/`escape()` because parse mode is HTML), `models.py` (frozen dataclasses + limits).
- **`database.py`** wraps one aiosqlite connection (autocommit, WAL). Schema is versioned via `PRAGMA user_version`: to change it, **append** a script to `MIGRATIONS`, never edit existing ones. Dates are stored as ISO `YYYY-MM-DD` text and times as `HH:MM`, so SQL string comparison works. Feb-29 handling lives in `dates.birthday_keys_for` (non-leap Feb 28 also matches 29.02).
- **`scheduler.py`** runs `check_and_notify` every minute (and once at startup). It sends greetings for groups whose `notify_time` has passed, and reminders `remind_days` ahead. `last_notified`/`last_reminded` are set only after a successful send, which makes it idempotent across minutes and restarts. `update_birthday` clears both marks.
- **`permissions.py`**: `target_group_id` (a private chat maps to `DEFAULT_GROUP_ID`) and `editable_group_id` (admin check via `get_chat_member`; returns `None` when not allowed). It is used by every mutating command.

## Tests

`tests/conftest.py` provides an in-memory `db` fixture. `tests/test_handlers.py` drives real handlers through a module-level `Dispatcher` with a `MockSession` that fakes Telegram API responses (`GetMe`, `GetChatMember` — user id 1 is admin, 2 is a member — and `SendMessage`). Routers are module singletons, so don't call `build_router()` twice in one process.
