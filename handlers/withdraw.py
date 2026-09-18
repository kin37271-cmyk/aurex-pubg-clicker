# handlers/withdraw.py
import aiosqlite
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.exceptions import TelegramBadRequest
from database import (
    get_user,
    get_setting,
    create_withdrawal,
    get_all_admins,
    DB_NAME
)
from keyboards.user_kb import withdraw_methods_keyboard
from keyboards.admin_kb import admin_withdrawal_action_keyboard
from config import (
    OWNER_ID,
    ADMINS,
    DEFAULT_CARD_MIN_WITHDRAW,
    DEFAULT_PUBG_MIN_WITHDRAW,
    DEFAULT_COIN_TO_SUM_RATE,
    DEFAULT_COIN_TO_UC_RATE
)

router = Router()

class CardWithdrawState(StatesGroup):
    amount = State()
    card_number = State()
    card_holder = State()

class PubgWithdrawState(StatesGroup):
    amount = State()
    player_id = State()
    player_nick = State()

@router.message(F.text == "💳 Pul Yechish (UC / Karta)")
@router.callback_query(F.data == "withdraw_menu_cb")
async def show_withdraw_menu(event: Message | CallbackQuery):
    user_id = event.from_user.id
    user = await get_user(user_id)
    if not user:
        return

    rate_sum = float(await get_setting("coin_to_sum_rate", DEFAULT_COIN_TO_SUM_RATE))
    min_card = float(await get_setting("card_min_withdraw", DEFAULT_CARD_MIN_WITHDRAW))
    min_pubg = float(await get_setting("pubg_min_withdraw", DEFAULT_PUBG_MIN_WITHDRAW))

    text = (
        f"💳 <b>Hisobdan Pul yoki UC Yechish</b> 💳\n\n"
        f"💰 Balansingiz: <b>{user['balance']:.1f} 🪙</b>\n\n"
        f"💳 <b>Bank Kartasiga (Uzcard/Humo/Visa):</b>\n"
        f"• Kurs: 10,000 🪙 = 5,000 so'm\n"
        f"• Minimal yechish: <b>{min_card:,.0f} 🪙</b> ({min_card * rate_sum:,.0f} so'm)\n\n"
        f"🎮 <b>PUBG Mobile UC:</b>\n"
        f"• Kurs: 15,000 🪙 = 60 UC\n"
        f"• Minimal yechish: <b>{min_pubg:,.0f} 🪙</b> (33 UC)\n\n"
        f"<i>Qaysi usulda yechib olmoqchisiz? Tanlang:</i>"
    )
    if isinstance(event, Message):
        await event.answer(text, reply_markup=withdraw_methods_keyboard(), parse_mode="HTML")
    else:
        await event.answer()
        await event.message.answer(text, reply_markup=withdraw_methods_keyboard(), parse_mode="HTML")

@router.callback_query(F.data == "cancel_withdraw")
async def cancel_withdraw_cb(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.delete()
    await callback.answer("Bekor qilindi!")

# --- BANK KARTASIGA YECHISH ---

@router.callback_query(F.data == "withdraw_card")
async def start_card_withdraw(callback: CallbackQuery, state: FSMContext):
    user = await get_user(callback.from_user.id)
    min_card = float(await get_setting("card_min_withdraw", DEFAULT_CARD_MIN_WITHDRAW))
    rate_sum = float(await get_setting("coin_to_sum_rate", DEFAULT_COIN_TO_SUM_RATE))
    
    if user["balance"] < min_card:
        await callback.answer(f"❌ Balansingizda kamida {min_card:,.0f} 🪙 ({min_card * rate_sum:,.0f} so'm) bo'lishi kerak!", show_alert=True)
        return

    await state.set_state(CardWithdrawState.amount)
    await callback.message.answer(
        f"💳 <b>Bank kartasiga pul yechish</b>\n\n"
        f"Qancha tanga yechmoqchisiz? (Minimal: <b>{min_card:,.0f} 🪙 = {min_card * rate_sum:,.0f} so'm</b>, Sizda: <b>{user['balance']:.1f} 🪙</b>)\n"
        f"Tangalar miqdorini raqamda yozing (masalan: 12000):",
        parse_mode="HTML"
    )
    await callback.answer()

@router.message(CardWithdrawState.amount)
async def process_card_amount(message: Message, state: FSMContext):
    user = await get_user(message.from_user.id)
    min_card = float(await get_setting("card_min_withdraw", DEFAULT_CARD_MIN_WITHDRAW))

    try:
        amount = float(message.text.replace(" ", "").replace(",", "."))
    except ValueError:
        await message.answer("❌ Iltimos, faqat musbat raqam kiriting!")
        return

    if amount < min_card:
        await message.answer(f"❌ Minimal yechish miqdori: <b>{min_card:,.0f} 🪙</b>!", parse_mode="HTML")
        return

    if amount > user["balance"]:
        await message.answer(f"❌ Sizning balansingizda bunday miqdorda tanga yo'q! (Balans: {user['balance']:.1f} 🪙)")
        return

    rate_sum = float(await get_setting("coin_to_sum_rate", DEFAULT_COIN_TO_SUM_RATE))
    payout_sum = amount * rate_sum
    await state.update_data(amount=amount, payout_sum=payout_sum)
    await state.set_state(CardWithdrawState.card_number)

    await message.answer(
        f"💵 Yechiladigan summa: <b>{payout_sum:,.0f} so'm</b>\n\n"
        f"Endi 16 talik <b>Karta raqamingizni</b> kiriting (masalan: 8600 1234 5678 9012):",
        parse_mode="HTML"
    )

@router.message(CardWithdrawState.card_number)
async def process_card_number(message: Message, state: FSMContext):
    card_num = message.text.replace(" ", "").strip()
    if len(card_num) < 16 or not card_num.isdigit():
        await message.answer("❌ Karta raqami noto'g'ri kiritildi! 16 ta raqamdan iborat bo'lishi kerak.")
        return

    await state.update_data(card_number=card_num)
    await state.set_state(CardWithdrawState.card_holder)
    await message.answer("👤 Karta egasining <b>Ism Familiyasini</b> kiriting (masalan: Rustam Karimov):", parse_mode="HTML")

@router.message(CardWithdrawState.card_holder)
async def process_card_holder(message: Message, state: FSMContext, bot: Bot):
    holder = message.text.strip()
    data = await state.get_data()
    await state.clear()

    user_id = message.from_user.id
    user = await get_user(user_id)
    amount_coins = data["amount"]
    payout_sum = data["payout_sum"]
    card_num = data["card_number"]

    # Oxirgi tekshirish
    if user["balance"] < amount_coins:
        await message.answer("❌ Balansingizda yetarli mablag' mavjud emas!")
        return

    w_id = await create_withdrawal(
        user_id=user_id,
        w_type="CARD",
        amount_coins=amount_coins,
        amount_target=payout_sum,
        target_val=card_num,
        target_details=holder
    )

    await message.answer(
        f"✅ <b>Zayafkangiz qabul qilindi! (ID: #{w_id})</b>\n\n"
        f"💵 Summa: <b>{payout_sum:,.0f} so'm</b> ({amount_coins:,.0f} 🪙)\n"
        f"💳 Karta: <code>{card_num}</code>\n"
        f"👤 Egasi: {holder}\n\n"
        f"⏳ Adminlar tez orada zayafkani ko'rib chiqib, to'lovni amalga oshiradi.",
        parse_mode="HTML"
    )

    # Adminlarga va Zayafka kanaliga xabar yuborish
    admin_text = (
        f"🆕 <b>YANGI PUL YECHISH SO'ROVI (#{w_id})</b>\n\n"
        f"👤 Foydalanuvchi: <a href='tg://user?id={user_id}'>{message.from_user.full_name}</a> (<code>{user_id}</code>)\n"
        f"💎 Yechilayotgan tanga: <b>{amount_coins:,.0f} 🪙</b>\n"
        f"💵 To'lanadigan summa: <b>{payout_sum:,.0f} so'm</b>\n"
        f"💳 Karta: <code>{card_num}</code>\n"
        f"👤 Egasi: {holder}\n"
        f"📅 Holat: ⏳ Kutilmoqda"
    )

    kb = admin_withdrawal_action_keyboard(w_id)
    active_admins = await get_all_admins()
    admin_ids = {OWNER_ID} | {a["user_id"] for a in active_admins}
    for admin_id in admin_ids:
        try:
            await bot.send_message(admin_id, admin_text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            pass

    zayafka_ch = await get_setting("zayafka_channel_id")
    if zayafka_ch:
        try:
            await bot.send_message(zayafka_ch, admin_text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            pass

# --- PUBG UC GA YECHISH ---

@router.callback_query(F.data == "withdraw_pubg")
async def start_pubg_withdraw(callback: CallbackQuery, state: FSMContext):
    user = await get_user(callback.from_user.id)
    min_pubg = float(await get_setting("pubg_min_withdraw", DEFAULT_PUBG_MIN_WITHDRAW))
    
    if user["balance"] < min_pubg:
        await callback.answer(f"❌ Balansingizda kamida {min_pubg:,.0f} 🪙 (33 UC) bo'lishi kerak!", show_alert=True)
        return

    await state.set_state(PubgWithdrawState.amount)
    await callback.message.answer(
        f"🎮 <b>PUBG Mobile UC yechish</b>\n\n"
        f"Qancha tanga yechmoqchisiz?\n"
        f"• Minimal: <b>8,000 🪙 = 33 UC</b>\n"
        f"• Standart: <b>15,000 🪙 = 60 UC</b>\n"
        f"• Sizda: <b>{user['balance']:.1f} 🪙</b>\n\n"
        f"Tangalar miqdorini raqamda yozing (masalan: 8000 yoki 15000):",
        parse_mode="HTML"
    )
    await callback.answer()

@router.message(PubgWithdrawState.amount)
async def process_pubg_amount(message: Message, state: FSMContext):
    user = await get_user(message.from_user.id)
    min_pubg = float(await get_setting("pubg_min_withdraw", DEFAULT_PUBG_MIN_WITHDRAW))

    try:
        amount = float(message.text.replace(" ", "").replace(",", "."))
    except ValueError:
        await message.answer("❌ Iltimos, faqat musbat raqam kiriting!")
        return

    if amount < min_pubg:
        await message.answer(f"❌ Minimal yechish miqdori: <b>{min_pubg:,.0f} 🪙</b> (33 UC)!", parse_mode="HTML")
        return

    if amount > user["balance"]:
        await message.answer(f"❌ Sizning balansingizda bunday miqdorda tanga yo'q! (Balans: {user['balance']:.1f} 🪙)")
        return

    if amount < 15000:
        payout_uc = 33 + ((amount - 8000) / 7000) * 27 if amount > 8000 else 33
    else:
        payout_uc = (amount / 15000) * 60
    payout_uc = int(round(payout_uc))

    await state.update_data(amount=amount, payout_uc=payout_uc)
    await state.set_state(PubgWithdrawState.player_id)

    await message.answer(
        f"🎁 Olinadigan UC: <b>{payout_uc:,.0f} UC</b>\n\n"
        f"Endi <b>PUBG Player ID (Raqamli ID)</b>ingizni kiriting (masalan: 5123456789):",
        parse_mode="HTML"
    )

@router.message(PubgWithdrawState.player_id)
async def process_pubg_id(message: Message, state: FSMContext):
    pid = message.text.strip()
    if not pid.isdigit() or len(pid) < 5:
        await message.answer("❌ Noto'g'ri Player ID! Faqat raqamlardan iborat bo'lishi kerak.")
        return

    await state.update_data(player_id=pid)
    await state.set_state(PubgWithdrawState.player_nick)
    await message.answer("🎮 PUBG o'yindagi <b>Nickname (Ismingiz)</b>ni kiriting:", parse_mode="HTML")

@router.message(PubgWithdrawState.player_nick)
async def process_pubg_nick(message: Message, state: FSMContext, bot: Bot):
    nick = message.text.strip()
    data = await state.get_data()
    await state.clear()

    user_id = message.from_user.id
    user = await get_user(user_id)
    amount_coins = data["amount"]
    payout_uc = data["payout_uc"]
    player_id = data["player_id"]

    if user["balance"] < amount_coins:
        await message.answer("❌ Balansingizda yetarli mablag' mavjud emas!")
        return

    w_id = await create_withdrawal(
        user_id=user_id,
        w_type="PUBG",
        amount_coins=amount_coins,
        amount_target=payout_uc,
        target_val=player_id,
        target_details=nick
    )

    await message.answer(
        f"✅ <b>PUBG UC zayafkangiz qabul qilindi! (ID: #{w_id})</b>\n\n"
        f"🎮 UC: <b>{payout_uc:,.0f} UC</b> ({amount_coins:,.0f} 🪙)\n"
        f"🆔 Player ID: <code>{player_id}</code>\n"
        f"👤 Nickname: {nick}\n\n"
        f"⏳ Adminlar tez orada UC hisobingizga tashlab beradi.",
        parse_mode="HTML"
    )

    admin_text = (
        f"🎮 <b>YANGI PUBG UC SO'ROVI (#{w_id})</b>\n\n"
        f"👤 Foydalanuvchi: <a href='tg://user?id={user_id}'>{message.from_user.full_name}</a> (<code>{user_id}</code>)\n"
        f"💎 Yechilayotgan tanga: <b>{amount_coins:,.0f} 🪙</b>\n"
        f"🎁 Olinadigan UC: <b>{payout_uc:,.0f} UC</b>\n"
        f"🆔 Player ID: <code>{player_id}</code>\n"
        f"👤 Nickname: {nick}\n"
        f"📅 Holat: ⏳ Kutilmoqda"
    )

    kb = admin_withdrawal_action_keyboard(w_id)
    active_admins = await get_all_admins()
    admin_ids = {OWNER_ID} | {a["user_id"] for a in active_admins}
    for admin_id in admin_ids:
        try:
            await bot.send_message(admin_id, admin_text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            pass

    zayafka_ch = await get_setting("zayafka_channel_id")
    if zayafka_ch:
        try:
            await bot.send_message(zayafka_ch, admin_text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            pass

# --- FOYDALANUVCHINING ZAYAFKALARI ---

@router.callback_query(F.data == "my_withdrawals")
async def show_my_withdrawals(callback: CallbackQuery):
    user_id = callback.from_user.id
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM withdrawals WHERE user_id = ? ORDER BY id DESC LIMIT 5", (user_id,)) as cur:
            rows = await cur.fetchall()

    if not rows:
        await callback.answer("Sizda hali zayafkalar mavjud emas!", show_alert=True)
        return

    text = "📜 <b>Sizning so'nggi zayafkalaringiz:</b>\n\n"
    status_map = {
        "PENDING": "⏳ Kutilmoqda",
        "APPROVED": "✅ To'lab berildi",
        "REJECTED": "❌ Rad etildi"
    }

    for r in rows:
        target_unit = "so'm" if r["type"] == "CARD" else "UC"
        status_str = status_map.get(r["status"], r["status"])
        text += (
            f"🆔 <b>#{r['id']}</b> ({r['type']}): <b>{r['amount_target']:,.0f} {target_unit}</b> ({r['amount_coins']:,.0f} 🪙)\n"
            f"📌 Holat: <b>{status_str}</b>\n"
            f"📅 Sana: {r['created_at']}\n"
        )
        if r["admin_note"]:
            text += f"💬 Izoh: <i>{r['admin_note']}</i>\n"
        text += "------------------------\n"

    try:
        await callback.message.answer(text, parse_mode="HTML")
        await callback.answer()
    except TelegramBadRequest:
        pass
