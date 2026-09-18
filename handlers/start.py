# handlers/start.py
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.filters import CommandStart, CommandObject
from database import get_or_create_user, get_user, get_statistics, get_setting, is_admin_user
from keyboards.user_kb import main_menu_keyboard, subscription_keyboard, webapp_inline_keyboard
from middlewares.subscription import get_unsubscribed_channels
from config import ADMINS, DEFAULT_REFERRAL_BONUS, WEBAPP_URL, DEFAULT_COIN_TO_SUM_RATE
import os

router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject, bot: Bot):
    user_id = message.from_user.id
    username = message.from_user.username
    full_name = message.from_user.full_name

    referrer_id = None
    if command.args and command.args.isdigit():
        referrer_id = int(command.args)

    user = await get_or_create_user(user_id, username, full_name, referrer_id)
    
    # Majburiy kanallarni tekshirish
    unsubscribed = await get_unsubscribed_channels(bot, user_id)
    if unsubscribed:
        kb = subscription_keyboard(unsubscribed)
        await message.answer(
            "👋 <b>Assalomu alaykum!</b>\n\n"
            "Botdan to'liq foydalanish va tangalar yig'ish uchun quyidagi homiy kanallarga a'zo bo'ling:",
            reply_markup=kb,
            parse_mode="HTML"
        )
        return

    is_admin = await is_admin_user(user_id)
    ref_bonus = await get_setting("referral_bonus", DEFAULT_REFERRAL_BONUS)
    
    welcome_text = (
        f"🔥 <b>AUREX PUBG CLICKER</b> ga xush kelibsiz, <b>{full_name}</b>!\n\n"
        f"🎮 Tangalar yig'ing, kuchaytirishlarni (Upgrade) sotib oling va daromad toping!\n\n"
        f"🎁 Yig'ilgan tangalarni <b>PUBG UC</b> yoki <b>Bank Kartangizga</b> naqd pul sifatida yechib oling!\n\n"
        f"👥 Do'stlaringizni taklif qiling va har biri uchun <b>+{ref_bonus} 🪙</b> bonus oling!\n\n"
        f"👇 O'yinni boshlash uchun quyidagi tugmani bosing:"
    )
    
    await message.answer(
        welcome_text,
        reply_markup=webapp_inline_keyboard(user_id, username, full_name),
        parse_mode="HTML"
    )
    await message.answer(
        "👇 <b>Asosiy Menyu:</b>",
        reply_markup=main_menu_keyboard(is_admin, user_id, username, full_name),
        parse_mode="HTML"
    )

@router.callback_query(F.data == "check_subscription")
async def cb_check_subscription(callback: CallbackQuery, bot: Bot):
    user_id = callback.from_user.id
    unsubscribed = await get_unsubscribed_channels(bot, user_id)
    
    if unsubscribed:
        await callback.answer("❌ Hali barcha kanallarga a'zo bo'lmadingiz!", show_alert=True)
        await callback.message.edit_reply_markup(reply_markup=subscription_keyboard(unsubscribed))
        return

    await callback.answer("✅ Rahmat, a'zolik tasdiqlandi!")
    await callback.message.delete()
    is_admin = await is_admin_user(user_id)
    await callback.message.answer(
        "🎉 <b>Ajoyib! Endi botdan to'liq foydalanishingiz mumkin!</b>\n"
        "O'yinni boshlash uchun pastdagi <b>🔥 O'YNASH</b> tugmasini bosing!",
        reply_markup=main_menu_keyboard(is_admin, user_id, callback.from_user.username, callback.from_user.full_name),
        parse_mode="HTML"
    )

@router.message(F.text == "👤 Profil & Balans")
async def show_profile(message: Message):
    user = await get_user(message.from_user.id)
    if not user:
        return

    profile_text = (
        f"👤 <b>Foydalanuvchi Profili:</b>\n\n"
        f"🆔 <b>ID:</b> <code>{user['user_id']}</code>\n"
        f"👤 <b>Ism:</b> {user['full_name']}\n"
        f"🔹 <b>Username:</b> @{user['username'] if user['username'] else 'Mavjud emas'}\n\n"
        f"💰 <b>Joriy Balans:</b> <b>{user['balance']:.1f} 🪙</b>\n"
        f"🏆 <b>Jami ishlangan:</b> {user['total_earned']:.1f} 🪙\n"
        f"⚡️ <b>Energiya:</b> {user['energy']} / {user['max_energy']}\n\n"
        f"🚀 <b>Kuchaytirishlar (Darajalar):</b>\n"
        f"• Multitap: <b>{user['multitap_level']} Lvl</b> (+{user['multitap_level']} coin/tap)\n"
        f"• Limit: <b>{user['energy_level']} Lvl</b> ({user['max_energy']} max)\n"
        f"• Tiklanish tezligi: <b>{user['regen_level']} Lvl</b>\n"
        f"• Auto-Bot: <b>{user['autobot_level']} Lvl</b> ({user['autobot_level'] * 50} coin/soat)\n\n"
        f"👥 <b>Taklif qilingan do'stlar:</b> {user['referral_count']} ta"
    )
    await message.answer(profile_text, parse_mode="HTML")

@router.message(F.text == "👥 Do'stlar (Referal)")
async def show_referrals(message: Message, bot: Bot):
    user_id = message.from_user.id
    user = await get_user(user_id)
    bot_info = await bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start={user_id}"
    ref_bonus = await get_setting("referral_bonus", DEFAULT_REFERRAL_BONUS)

    ref_text = (
        f"👥 <b>Do'stlarni Taklif Qilish Tizimi</b>\n\n"
        f"Do'stlaringizga o'z referal havolangizni yuboring va har bir kirgan do'stingiz uchun <b>+{ref_bonus} 🪙</b> bonus oling!\n\n"
        f"🔗 <b>Sizning taklif havolangiz:</b>\n"
        f"<code>{ref_link}</code>\n\n"
        f"📊 <b>Sizning statistikangiz:</b>\n"
        f"• Taklif qilgan do'stlaringiz: <b>{user['referral_count']} ta</b>\n"
        f"• Referaldan ishlangan tangalar: <b>{user['referral_count'] * float(ref_bonus):.1f} 🪙</b>"
    )
    await message.answer(ref_text, parse_mode="HTML")

@router.message(F.text == "📊 Bot Statistikasi")
async def show_bot_statistics(message: Message):
    stats = await get_statistics()
    text = (
        f"📊 <b>Botning Umumiy Statistikasi:</b>\n\n"
        f"👥 <b>Jami foydalanuvchilar:</b> {stats['total_users']} ta\n"
        f"🪙 <b>Foydalanuvchilar balansi:</b> {stats['total_balance']:.1f} 🪙\n"
        f"💎 <b>Jami ishlangan tangalar:</b> {stats['total_earned']:.1f} 🪙\n\n"
        f"💳 <b>To'langan kartaga:</b> {stats['approved_card_sum'] or 0:,.0f} so'm ({stats['approved_card_count']} ta)\n"
        f"🎮 <b>To'langan PUBG UC:</b> {stats['approved_pubg_uc'] or 0:,.0f} UC ({stats['approved_pubg_count']} ta)"
    )
    await message.answer(text, parse_mode="HTML")

@router.message(F.text == "ℹ️ Qo'llanma")
async def show_guide(message: Message):
    max_energy = await get_setting("initial_max_energy", 100)

    text = (
        f"ℹ️ <b>Qo'llanma & Qoidalar:</b>\n\n"
        f"1. Pastdagi <b>🔥 O'YNASH</b> tugmasini bosing va o'yinni oching.\n"
        f"2. O'rtadagi AUREX olovli bannerini bosib tangalarni yig'ing.\n"
        f"3. Limit <b>{int(max_energy):,} ta</b> bo'lib, avtomatik to'liq tiklanadi.\n"
        f"4. <b>⚡️ Do'kon</b> bo'limida Multitap, Limit va Auto-Botni kuchaytirib ko'proq tanga ishlang.\n\n"
        f"💰 <b>Almashuv Kurslari:</b>\n"
        f"• 💳 <b>Bank Kartasiga:</b> 10,000 🪙 = 5,000 so'm (Minimal: <b>10,000 🪙</b>)\n"
        f"• 🎮 <b>PUBG UC:</b> 15,000 🪙 = 60 UC (Minimal: <b>8,000 🪙 = 33 UC</b>)\n\n"
        f"Savollar bo'lsa adminga murojaat qiling."
    )
    await message.answer(text, parse_mode="HTML")
