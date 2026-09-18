# handlers/shop.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.exceptions import TelegramBadRequest
from database import get_user, buy_upgrade, claim_autobot
from keyboards.user_kb import shop_inline_keyboard, clicker_inline_keyboard
from handlers.clicker import render_clicker_text

router = Router()

def render_shop_text(user: dict) -> str:
    return (
        f"⚡️ <b>Do'kon / Kuchaytirish Bo'limi</b> ⚡️\n\n"
        f"💰 Balansingiz: <b>{user['balance']:.1f} 🪙</b>\n\n"
        f"👆 <b>Multitap:</b> 1 bosishda olinadigan tangalarni oshirish.\n"
        f"🔋 <b>Max Limit:</b> Maksimal energiya sig'imini 100 taga oshirish.\n"
        f"⏳ <b>Tezkor Quvvat:</b> Energiyaning to'lish tezligini oshirish.\n"
        f"🤖 <b>Auto-Bot:</b> Botda bo'lmasangiz ham passiv daromad yig'ib berish (soatiga 50 tanga/daraja).\n\n"
        f"<i>Kuchaytirishni xarid qilish uchun pastdagi tugmani bosing:</i>"
    )

@router.message(F.text == "⚡️ Do'kon (Kuchaytirish)")
async def show_shop(message: Message):
    user = await get_user(message.from_user.id)
    if not user:
        return
    text = render_shop_text(user)
    kb = shop_inline_keyboard(user)
    await message.answer(text, reply_markup=kb, parse_mode="HTML")

@router.callback_query(F.data.startswith("buy_"))
async def handle_buy_upgrade(callback: CallbackQuery):
    user_id = callback.from_user.id
    upgrade_type = callback.data.replace("buy_", "")
    
    success, message_text = await buy_upgrade(user_id, upgrade_type)
    await callback.answer(message_text, show_alert=True)
    
    if success:
        user = await get_user(user_id)
        new_text = render_shop_text(user)
        new_kb = shop_inline_keyboard(user)
        try:
            await callback.message.edit_text(new_text, reply_markup=new_kb, parse_mode="HTML")
        except TelegramBadRequest:
            pass

@router.callback_query(F.data == "claim_autobot")
async def handle_claim_autobot(callback: CallbackQuery):
    user_id = callback.from_user.id
    coins, msg = await claim_autobot(user_id)
    await callback.answer(msg, show_alert=True)
    
    if coins > 0:
        user = await get_user(user_id)
        new_text = render_shop_text(user)
        new_kb = shop_inline_keyboard(user)
        try:
            await callback.message.edit_text(new_text, reply_markup=new_kb, parse_mode="HTML")
        except TelegramBadRequest:
            pass

@router.callback_query(F.data == "back_to_menu")
async def handle_back_to_menu(callback: CallbackQuery):
    user = await get_user(callback.from_user.id)
    if not user:
        await callback.answer()
        return
    text = render_clicker_text(user)
    kb = clicker_inline_keyboard(user["multitap_level"], user["energy"], user["max_energy"])
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except TelegramBadRequest:
        pass
