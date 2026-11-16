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

- **Dependency injection, no globals.** `__main__.py` builds `Config` and `Database` and passes them as `Dispatcher(db=..., config=...)` workflow data, so handlers declare `db: Database, config: Config` parameters. The scheduler gets them explicitly. To add a handler, put it in a router under `handlers/` (`common`, `birthdays`, `settings`, plus the menu routers below); `handlers.build_router()` combines the routers.
- **Pure logic is separate from aiogram/DB:** `dates.py` (all functions take "today" as a parameter; get the current time only through `dates.now(config.timezone)`, never `date.today()`, because servers run in UTC), `parsing.py` (raises `ParseError`), `texts.py` (all messages; user input must go through `mention()`/`escape()` because parse mode is HTML), `models.py` (frozen dataclasses + limits).
- **`database.py`** wraps one aiosqlite connection (autocommit, WAL). Schema is versioned via `PRAGMA user_version`: to change it, **append** a script to `MIGRATIONS`, never edit existing ones. Dates are stored as ISO `YYYY-MM-DD` text and times as `HH:MM`, so SQL string comparison works. Feb-29 handling lives in `dates.birthday_keys_for` (non-leap Feb 28 also matches 29.02).
- **`scheduler.py`** runs `check_and_notify` every minute (and once at startup). It sends greetings for groups whose `notify_time` has passed, and reminders `remind_days` ahead. `last_notified`/`last_reminded` are set only after a successful send, which makes it idempotent across minutes and restarts. `update_birthday` clears both marks. When a send to a group fails, managers and linked admins get a private message, once per group per day (the `failures` set passed in through the job kwargs); network errors are only retried, never reported. An hour before `notify_time` the same recipients get a morning digest of today's and tomorrow's birthdays (`groups.last_digest` makes it once a day; `group_links.digest` is a per-user opt-out). A group's own `greeting_template` (`{ism}` placeholder) replaces the default `GREETINGS`.
- **Roles (`permissions.py`):** `get_role()` makes one `get_chat_member` call and returns `Role.ADMIN` (creator/administrator), `MANAGER` (in `group_managers`: whoever added the bot, or appointed by an admin with `/manager` as a reply), `MEMBER` (may only manage their own record, found by `birthdays.user_id`) or `NONE` (not in the group). `editable_group_id` accepts `>= MANAGER` and is used by every mutating command. `target_group_id` maps a private chat to `DEFAULT_GROUP_ID`. `resolve_group` follows `TelegramMigrateToChat` when a group became a supergroup.
- **Button menu (private chat):** `group_events` registers a group in the `groups` table when the bot is added (`my_chat_member`), makes the adder a manager, and posts a `t.me/<bot>?start=g_<id>` button. `menu` checks the role on that deep link, links the user in `group_links`, and shows the manager menu or the member menu. `add_flow` (with a `request_users` reply keyboard to pick the person from Telegram), `manage`, `settings_menu` and `self_flow` (members) use aiogram FSM (`MemoryStorage`, lost on restart). Buttons and `CallbackData` classes live in `keyboards.py`; the `group_id` inside callback data is never trusted — every action re-checks via `handlers/ui.ensure_role` / `ensure_manager`. The `ClearStateOnCommand` middleware drops the FSM state when a command is typed mid-dialog. Deep-link payloads: `g_<group_id>` (group button) and `m_<token>` (one-time manager invite from `manager_invites`, 7 days). `commands.set_bot_commands` registers the "/" menu and `set_bot_description` the "What can this bot do?" texts at startup. A private `/start` with no linked groups shows `texts.GUIDE_TEXT` (also behind the menus' 📖 button) with a `?startgroup=true` button. List export (`texts.export_text`) uses the same line format `parsing.parse_bulk` reads. The scheduler skips groups with `groups.active = 0`.

## Tests

`tests/conftest.py` provides an in-memory `db` fixture. `tests/test_handlers.py` drives real handlers through a module-level `Dispatcher` with a `MockSession` that fakes Telegram API responses (`GetMe`, `GetChatMember` — user id 1 is admin, 2 is a member, 3 is not in the group — `GetChat`, where `OLD_G` raises a migration and `GONE_G` "chat not found", and `SendMessage`). Routers are module singletons, so don't call `build_router()` twice in one process.

Menu tests live in `tests/test_handlers.py` too: `send.click(callback_data)` presses a button, `send(..., chat_type="private")` writes in a private chat, `buttons(send.session.last_markup())` reads the buttons, and `membership_update()` adds or removes the bot. The `send` fixture resets FSM storage for every test.
