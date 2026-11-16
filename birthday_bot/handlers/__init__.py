"""
handlers — Bot buyruqlari. Har bir handler `db: Database` va `config: Config`
ni Dispatcher workflow_data orqali oladi (__main__.py ga qarang).
"""

from aiogram import Router

from birthday_bot.handlers import birthdays, common, settings


def build_router() -> Router:
    root = Router(name="root")
    root.include_routers(common.router, birthdays.router, settings.router)
    return root
