# handlers/clicker.py
import os
import time
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.exceptions import TelegramBadRequest
from database import get_user, tap_user
from keyboards.user_kb import clicker_inline_keyboard, shop_inline_keyboard

router = Router()

# Rate limiting / Throttling in memory to prevent Telegram edit message flood
last_tap_time = {}

def get_progress_bar(current: int, total: int, length: int = 10) -> str:
    if total <= 0:
        return "░" * length
    percent = max(0, min(1, current / total))
    filled = int(round(length * percent))
    return "🟩" * filled + "⬜" * (length - filled)

def render_clicker_text(user: dict) -> str:
    energy = user["energy"]
    max_energy = user["max_energy"]
    balance = user["balance"]
    multitap = user["multitap_level"]
    bar = get_progress_bar(energy, max_energy)

    return (
        f"🔥 <b>AUREX PUBG CLICKER (WEB APP)</b> 🔥\n\n"
        f"💰 <b>Balans:</b> <b>{balance:.1f} 🪙</b>\n"
        f"👆 <b>1 Bosishda:</b> <b>+{multitap} 🪙</b>\n"
        f"⚡️ <b>Energiya:</b> <b>{energy} / {max_energy}</b>\n"
        f"{bar}\n\n"
        f"🎮 <i>Diqqat: Tangalar yig'ish va bosish faqat <b>Telegram Web App</b> orqali ishlaydi!</i>\n\n"
        f"👇 O'yinni to'liq ekranda ochish uchun pastdagi <b>🔥 Web Appda O'ynash</b> tugmasini bosing:"
    )

async def edit_clicker_message(message: Message, text: str, kb):
    try:
        if message.photo:
            await message.edit_caption(caption=text, reply_markup=kb, parse_mode="HTML")
        else:
            await message.edit_text(text=text, reply_markup=kb, parse_mode="HTML")
    except TelegramBadRequest:
        pass

@router.message(F.text.in_(["🚀 Aurex Clicker (Web App)", "🐹 Clicker (Tanga Yig'ish)", "🎮 O'yinga Kirish (Web App)"]))
@router.callback_query(F.data == "open_chat_clicker")
async def show_clicker_menu(event: Message | CallbackQuery):
    user_id = event.from_user.id
    user = await get_user(user_id)
    if not user:
        return

    text = render_clicker_text(user)
    kb = clicker_inline_keyboard(user_id, event.from_user.username or "", event.from_user.full_name or "")
    
    if isinstance(event, Message):
        await event.answer(text, reply_markup=kb, parse_mode="HTML")
    else:
        await event.answer()
        await edit_clicker_message(event.message, text, kb)

@router.callback_query(F.data == "open_shop")
async def cb_open_shop(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = await get_user(user_id)
    if not user:
        return
    text = (
        f"⚡️ <b>Do'kon / Kuchaytirish Bo'limi</b> ⚡️\n\n"
        f"💰 Balansingiz: <b>{user['balance']:.1f} 🪙</b>\n\n"
        f"O'zingizga kerakli kuchaytirishni tanlang:"
    )
    kb = shop_inline_keyboard(user)
    await edit_clicker_message(callback.message, text, kb)
