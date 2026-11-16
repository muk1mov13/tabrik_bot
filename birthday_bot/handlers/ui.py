"""
ui.py — Tugmali menyu handlerlari uchun umumiy yordamchilar.
"""

from typing import Any, Awaitable, Callable, Optional, Union

from aiogram import BaseMiddleware, Bot, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message, TelegramObject

from birthday_bot.database import Database
from birthday_bot.permissions import Role, get_role
from birthday_bot.texts import NOT_ADMIN_ALERT

# Savol-javobga javob: oddiy matn, buyruq emas
TEXT_INPUT = F.text & ~F.text.startswith("/")


async def ensure_role(
    event: Union[Message, CallbackQuery], bot: Bot, db: Database, group_id: int, minimum: Role
) -> Optional[Role]:
    """
    Rolni qayta tekshiradi (callback ma'lumotiga ishonilmaydi). Ruxsat bo'lmasa —
    foydalanuvchiga aytiladi va None qaytadi; guruhda umuman bo'lmasa bog'lanish
    ham o'chiriladi.
    """
    user_id = event.from_user.id
    role = await get_role(bot, db, group_id, user_id)
    if role >= minimum:
        return role
    if role == Role.NONE:
        await db.unlink_user(user_id, group_id)
    if isinstance(event, CallbackQuery):
        await event.answer(NOT_ADMIN_ALERT, show_alert=True)
    else:
        await event.answer(NOT_ADMIN_ALERT)
    return None


async def ensure_manager(
    event: Union[Message, CallbackQuery], bot: Bot, db: Database, group_id: int
) -> bool:
    return await ensure_role(event, bot, db, group_id, Role.MANAGER) is not None


async def show(callback: CallbackQuery, text: str, keyboard: Optional[InlineKeyboardMarkup] = None):
    """Menyu xabarini yangilaydi (eski xabarga kirib bo'lmasa — yangisini yuboradi)."""
    if isinstance(callback.message, Message):
        try:
            await callback.message.edit_text(text, reply_markup=keyboard)
        except TelegramBadRequest as exc:
            # Xuddi shu tugma qayta bosilganda matn o'zgarmaydi — bu xato emas
            if "message is not modified" not in str(exc):
                raise
    else:
        await callback.bot.send_message(callback.from_user.id, text, reply_markup=keyboard)
    await callback.answer()


class ClearStateOnCommand(BaseMiddleware):
    """Savol-javob paytida buyruq yozilsa — savol-javob bekor qilinadi."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        state: Optional[FSMContext] = data.get("state")
        text = getattr(event, "text", None)
        if state is not None and data.get("raw_state") and text and text.startswith("/"):
            await state.clear()
            # StateFilter data["raw_state"] ni o'qiydi — uni ham yangilaymiz
            data["raw_state"] = None
        return await handler(event, data)
