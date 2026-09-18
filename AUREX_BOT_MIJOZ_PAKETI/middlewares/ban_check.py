# middlewares/ban_check.py
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject
from database import get_user
from config import ADMINS

class BanCheckMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        user_id = None
        if isinstance(event, Message):
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id

        if user_id and user_id not in ADMINS:
            user = await get_user(user_id)
            if user and user.get("is_banned"):
                reason = user.get("ban_reason") or "Qoidabuzarlik sababli"
                msg = f"🚫 <b>Kechirasiz, siz botdan bloklangansiz!</b>\n\n📝 Sabab: <i>{reason}</i>\nIltimos, adminlarga murojaat qiling."
                if isinstance(event, Message):
                    await event.answer(msg, parse_mode="HTML")
                elif isinstance(event, CallbackQuery):
                    await event.answer("🚫 Siz bloklangansiz!", show_alert=True)
                return

        return await handler(event, data)
