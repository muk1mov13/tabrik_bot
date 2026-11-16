"""
handlers — Bot buyruqlari va tugmali menyu. Har bir handler `db: Database`
va `config: Config` ni Dispatcher workflow_data orqali oladi (__main__.py ga
qarang).
"""

from aiogram import Router

from birthday_bot.handlers import birthdays, common, group_events, menu, settings
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
    )
    return root
