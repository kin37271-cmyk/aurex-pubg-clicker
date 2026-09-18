import os
import aiosqlite
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.exceptions import TelegramBadRequest

from config import ADMINS
from database import (
    DB_NAME,
    get_detailed_statistics,
    get_all_settings,
    set_setting,
    get_user,
    search_users,
    update_user_balance,
    ban_user,
    unban_user,
    get_all_channels,
    add_channel,
    delete_channel,
    get_pending_withdrawals,
    get_withdrawal,
    resolve_withdrawal,
    is_admin_user,
    get_admin,
    get_all_admins,
    add_new_admin,
    delete_admin,
    toggle_admin_permission,
    check_admin_permission
)
from keyboards.admin_kb import (
    admin_main_keyboard,
    admin_user_control_keyboard,
    admin_withdrawal_action_keyboard,
    admin_list_keyboard,
    admin_permissions_keyboard,
    admin_back_keyboard
)
from excel_export import generate_users_excel, generate_withdrawals_excel

router = Router()

# Admin FSM States
class AdminStates(StatesGroup):
    search_user = State()
    send_msg_to_user = State()
    add_user_bal = State()
    sub_user_bal = State()
    ban_user_reason = State()
    
    # Settings
    set_coin_sum_rate = State()
    set_coin_uc_rate = State()
    set_card_min = State()
    set_pubg_min = State()
    set_init_limit = State()
    set_ref_bonus = State()
    set_zayafka_ch = State()
    
    # Channels
    add_ch_id = State()
    add_ch_title = State()
    add_ch_url = State()
    
    # Withdrawal rejection reason
    reject_reason = State()

    # Admin Management
    add_admin_input = State()

async def is_admin(user_id: int) -> bool:
    return await is_admin_user(user_id)

async def is_owner(user_id: int) -> bool:
    user_id = int(user_id)
    if user_id in ADMINS or user_id in (8825408278, OWNER_ID):
        return True
    adm = await get_admin(user_id)
    return bool(adm and adm.get("role") == "owner")

@router.message(Command("admin"))
@router.message(Command("panel"))
@router.message(F.text.in_({"👑 Admin Panel", "/admin", "admin", "Admin", "/panel", "Panel"}))
async def show_admin_panel(message: Message):
    if not await is_admin(message.from_user.id):
        return
    owner = await is_owner(message.from_user.id)
    text = (
        "👑 <b>ASOSIY ADMIN BOSHQARUV PANELI</b>\n\n"
        "Quyidagi bo'limlardan birini tanlang:"
    )
    await message.answer(text, reply_markup=admin_main_keyboard(is_owner=owner), parse_mode="HTML")

@router.callback_query(F.data == "admin_main")
async def cb_admin_main(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    await state.clear()
    owner = await is_owner(callback.from_user.id)
    text = (
        "👑 <b>ASOSIY ADMIN BOSHQARUV PANELI</b>\n\n"
        "Quyidagi bo'limlardan birini tanlang:"
    )
    try:
        await callback.message.edit_text(text, reply_markup=admin_main_keyboard(is_owner=owner), parse_mode="HTML")
    except TelegramBadRequest:
        await callback.message.answer(text, reply_markup=admin_main_keyboard(is_owner=owner), parse_mode="HTML")

@router.callback_query(F.data == "admin_exit")
async def cb_admin_exit(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.answer("Admin paneldan chiqildi!")

# --- STATISTIKA ---

@router.callback_query(F.data == "admin_stats")
async def cb_admin_stats(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    stats = await get_detailed_statistics()
    text = (
        "📊 <b>BOTNING TO'LIQ STATISTIKASI:</b>\n\n"
        f"👥 <b>Jami mijozlar (foydalanuvchilar):</b> <b>{stats['total_users']} ta</b>\n"
        f"📅 <b>Bugun qo'shilgan yangi mijozlar:</b> <b>{stats['today_users']} ta</b>\n"
        f"👮‍♂️ <b>Jami adminlar soni:</b> <b>{stats['total_admins']} ta</b>\n"
        f"🚫 <b>Bloklanganlar:</b> <b>{stats['banned_users']} ta</b>\n\n"
        f"🪙 <b>Hozirgi mijozlar balansi:</b> <b>{stats['total_balance']:.1f} 🪙</b>\n"
        f"💎 <b>Umumiy ishlangan tangalar:</b> <b>{stats['total_earned']:.1f} 🪙</b>\n\n"
        f"⏳ <b>Kutilayotgan zayafkalar:</b> <b>{stats['pending_withdrawals']} ta</b>\n"
        f"💳 <b>Kartaga to'langan:</b> <b>{stats['approved_card_sum'] or 0:,.0f} so'm</b> ({stats['approved_card_count']} ta)\n"
        f"🎮 <b>PUBG UC to'langan:</b> <b>{stats['approved_pubg_uc'] or 0:,.0f} UC</b> ({stats['approved_pubg_count']} ta)"
    )
    await callback.message.edit_text(text, reply_markup=admin_back_keyboard("admin_main"), parse_mode="HTML")

# --- ADMINLAR & RUXSATLAR BOSHQARUVI ---

@router.callback_query(F.data == "admin_manage_admins")
async def cb_manage_admins(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if not await is_admin(user_id):
        return
    
    if not (await is_owner(user_id) or await check_admin_permission(user_id, "can_manage_admins")):
        await callback.answer("⚠️ Ushbu bo'lim faqat Asosiy Egasi (Owner) uchun!", show_alert=True)
        return

    await state.clear()
    admins = await get_all_admins()
    text = (
        "👮‍♂️ <b>ADMINLAR VA RUXSATLAR BOSHQARUVI</b>\n\n"
        "Quyida barcha adminlar ro'yxati keltirilgan. Admin ustiga bosib, uning ruxsatlarini Telegram kanaldagidek "
        "alohida yoqishingiz yoki o'chirishingiz mumkin:\n\n"
        f"Jami adminlar: <b>{len(admins)} ta</b>"
    )
    await callback.message.edit_text(text, reply_markup=admin_list_keyboard(admins), parse_mode="HTML")

@router.callback_query(F.data.startswith("adm_detail_"))
async def cb_admin_detail(callback: CallbackQuery):
    user_id = callback.from_user.id
    if not await is_admin(user_id):
        return
    
    target_uid = int(callback.data.replace("adm_detail_", ""))
    adm = await get_admin(target_uid)
    if not adm:
        await callback.answer("Admin topilmadi!", show_alert=True)
        return

    owner = await is_owner(user_id)
    role_name = "👑 Asosiy Egasi (Owner - Cheksiz Ruxsat)" if adm.get("role") == "owner" else "👮‍♂️ Qo'shimcha Admin"
    text = (
        f"👮‍♂️ <b>Admin Ma'lumotlari & Ruxsatlari:</b>\n\n"
        f"🆔 <b>ID:</b> <code>{adm['user_id']}</code>\n"
        f"👤 <b>Ism:</b> {adm.get('full_name') or 'Nomalum'}\n"
        f"🔹 <b>Username:</b> @{adm.get('username') or 'Mavjud emas'}\n"
        f"🔰 <b>Maqomi:</b> {role_name}\n\n"
        f"<i>Ruxsatlarni o'zgartirish uchun quyidagi tugmalarni bosing:</i>"
    )
    await callback.message.edit_text(text, reply_markup=admin_permissions_keyboard(adm, is_current_user_owner=owner), parse_mode="HTML")

@router.callback_query(F.data.startswith("tog_perm_"))
async def cb_toggle_permission(callback: CallbackQuery):
    user_id = callback.from_user.id
    if not await is_owner(user_id):
        await callback.answer("⚠️ Faqat Asosiy Egasi ruxsatlarni o'zgartira oladi!", show_alert=True)
        return

    parts = callback.data.split("_")
    target_uid = int(parts[2])
    perm_name = "_".join(parts[3:])

    target_adm = await get_admin(target_uid)
    if not target_adm:
        await callback.answer("Admin topilmadi!")
        return
        
    if target_adm.get("role") == "owner":
        await callback.answer("👑 Asosiy Egasining ruxsatlarini o'zgartirib bo'lmaydi!", show_alert=True)
        return

    new_val = await toggle_admin_permission(target_uid, perm_name)
    status_str = "yoqildi ✅" if new_val == 1 else "o'chirildi ❌"
    await callback.answer(f"Ruxsat {status_str}!")

    updated_adm = await get_admin(target_uid)
    owner = await is_owner(user_id)
    role_name = "👮‍♂️ Qo'shimcha Admin"
    text = (
        f"👮‍♂️ <b>Admin Ma'lumotlari & Ruxsatlari:</b>\n\n"
        f"🆔 <b>ID:</b> <code>{updated_adm['user_id']}</code>\n"
        f"👤 <b>Ism:</b> {updated_adm.get('full_name') or 'Nomalum'}\n"
        f"🔹 <b>Username:</b> @{updated_adm.get('username') or 'Mavjud emas'}\n"
        f"🔰 <b>Maqomi:</b> {role_name}\n\n"
        f"<i>Ruxsatlarni o'zgartirish uchun quyidagi tugmalarni bosing:</i>"
    )
    try:
        await callback.message.edit_text(text, reply_markup=admin_permissions_keyboard(updated_adm, is_current_user_owner=owner), parse_mode="HTML")
    except TelegramBadRequest:
        pass

@router.callback_query(F.data.startswith("del_admin_"))
async def cb_delete_admin(callback: CallbackQuery):
    user_id = callback.from_user.id
    if not await is_owner(user_id):
        await callback.answer("⚠️ Faqat Asosiy Egasi adminni o'chira oladi!", show_alert=True)
        return

    target_uid = int(callback.data.replace("del_admin_", ""))
    success, msg = await delete_admin(target_uid)
    await callback.answer(msg, show_alert=True)
    await cb_manage_admins(callback, None)

@router.callback_query(F.data == "add_new_admin_btn")
async def cb_add_new_admin_start(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if not await is_owner(user_id):
        await callback.answer("⚠️ Faqat Asosiy Egasi yangi admin qo'sha oladi!", show_alert=True)
        return

    await state.set_state(AdminStates.add_admin_input)
    text = (
        "➕ <b>YANGI ADMIN QO'SHISH</b>\n\n"
        "Yangi admin qilmoqchi bo'lgan shaxsning <b>Telegram ID</b> sini yoki <b>@Username</b> ini yuboring:"
    )
    await callback.message.edit_text(text, reply_markup=admin_back_keyboard("admin_manage_admins"), parse_mode="HTML")
    await callback.answer()

@router.message(AdminStates.add_admin_input)
async def process_add_admin_input(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if not await is_owner(user_id):
        return

    query = message.text.strip()
    target_user = None
    
    if query.isdigit():
        target_uid = int(query)
        target_user = await get_user(target_uid)
        username = target_user.get("username") if target_user else None
        full_name = target_user.get("full_name") if target_user else f"Admin {target_uid}"
    else:
        found_users = await search_users(query)
        if found_users:
            target_user = found_users[0]
            target_uid = target_user["user_id"]
            username = target_user.get("username")
            full_name = target_user.get("full_name")
        else:
            await message.answer("❌ Ushbu username bo'yicha foydalanuvchi topilmadi! Qaytadan ID yoki Username yuboring:")
            return

    await add_new_admin(target_uid, username, full_name, role="admin")
    await state.clear()
    
    adm = await get_admin(target_uid)
    owner = await is_owner(user_id)
    text = (
        f"✅ <b>Yangi Admin Muvaffaqiyatli Qo'shildi!</b>\n\n"
        f"🆔 <b>ID:</b> <code>{adm['user_id']}</code>\n"
        f"👤 <b>Ism:</b> {adm.get('full_name')}\n"
        f"🔹 <b>Username:</b> @{adm.get('username') if adm.get('username') else 'Mavjud emas'}\n\n"
        f"<i>Endi ushbu admin uchun kerakli ruxsatlarni quyidagi tugmalar orqali yoqing:</i>"
    )
    await message.answer(text, reply_markup=admin_permissions_keyboard(adm, is_current_user_owner=owner), parse_mode="HTML")

# --- FOYDALANUVCHILAR BOSHQARUVI ---

@router.callback_query(F.data == "admin_users")
async def cb_admin_users(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if not await is_admin(user_id):
        return
    if not await check_admin_permission(user_id, "can_manage_users"):
        await callback.answer("⚠️ Sizda foydalanuvchilarni boshqarish ruxsati yo'q!", show_alert=True)
        return

    await state.set_state(AdminStates.search_user)
    text = (
        "👤 <b>Mijozlarni (Foydalanuvchilarni) Boshqarish</b>\n\n"
        "Mijozni topish uchun uning <b>Telegram ID</b> sini yoki <b>@Username</b> ini yuboring:"
    )
    await callback.message.edit_text(text, reply_markup=admin_back_keyboard("admin_main"), parse_mode="HTML")

@router.message(AdminStates.search_user)
async def process_search_user(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if not await is_admin(user_id) or not await check_admin_permission(user_id, "can_manage_users"):
        return

    q = message.text.strip()
    users = await search_users(q)

    if not users:
        await message.answer("❌ Foydalanuvchi topilmadi! Boshqa ID yoki Username kiritib ko'ring:", 
                             reply_markup=admin_back_keyboard("admin_main"))
        return

    await state.clear()
    for u in users[:5]: # Maksimal 5 ta chiqarish
        status = "🔴 BLOKLANGAN (BAN)" if u["is_banned"] else "🟢 FAOL"
        ban_text = f"📝 <b>Ban sababi:</b> <i>{u.get('ban_reason')}</i>\n" if u["is_banned"] else ""
        info = (
            f"👤 <b>Foydalanuvchi Ma'lumotlari:</b>\n\n"
            f"🆔 <b>ID:</b> <code>{u['user_id']}</code>\n"
            f"👤 <b>Ism:</b> {u['full_name']}\n"
            f"🔹 <b>Username:</b> @{u['username'] if u['username'] else 'Mavjud emas'}\n"
            f"📌 <b>Holat:</b> {status}\n"
            f"{ban_text}"
            f"💰 <b>Balans:</b> <b>{u['balance']:.1f} 🪙</b>\n"
            f"🏆 <b>Jami ishlangan:</b> {u['total_earned']:.1f} 🪙\n"
            f"⚡️ <b>Energiya:</b> {u['energy']} / {u['max_energy']}\n"
            f"👆 <b>Multitap:</b> {u['multitap_level']} Lvl\n"
            f"🤖 <b>Auto-bot:</b> {u['autobot_level']} Lvl\n"
            f"👥 <b>Referallari:</b> {u['referral_count']} ta\n"
            f"📅 <b>Ro'yxatdan o'tgan:</b> {u['created_at']}"
        )
        kb = admin_user_control_keyboard(u["user_id"], bool(u["is_banned"]))
        await message.answer(info, reply_markup=kb, parse_mode="HTML")

# Balans qo'shish
@router.callback_query(F.data.startswith("add_bal_"))
async def cb_add_bal_start(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if not await is_admin(user_id) or not await check_admin_permission(user_id, "can_manage_users"):
        await callback.answer("⚠️ Sizda ushbu ruxsat yo'q!", show_alert=True)
        return

    uid = int(callback.data.replace("add_bal_", ""))
    await state.update_data(target_user_id=uid)
    await state.set_state(AdminStates.add_user_bal)
    await callback.message.answer(f"➕ Foydalanuvchi (<code>{uid}</code>) hisobiga qo'shmoqchi bo'lgan <b>tangalar miqdorini</b> yozing:", parse_mode="HTML")
    await callback.answer()

@router.message(AdminStates.add_user_bal)
async def process_add_bal(message: Message, state: FSMContext, bot: Bot):
    user_id = message.from_user.id
    if not await is_admin(user_id) or not await check_admin_permission(user_id, "can_manage_users"):
        return

    data = await state.get_data()
    uid = data["target_user_id"]
    try:
        amount = float(message.text.replace(" ", "").replace(",", "."))
    except ValueError:
        await message.answer("❌ Faqat son kiriting!")
        return

    await update_user_balance(uid, amount, mode="ADD")
    await state.clear()
    await message.answer(f"✅ Foydalanuvchi (<code>{uid}</code>) hisobiga <b>+{amount:,.1f} 🪙</b> qo'shildi!", parse_mode="HTML")
    try:
        await bot.send_message(uid, f"🎁 Admin tomonidan hisobingizga <b>+{amount:,.1f} 🪙</b> tanga qo'shildi!", parse_mode="HTML")
    except Exception:
        pass

# Balans ayirish
@router.callback_query(F.data.startswith("sub_bal_"))
async def cb_sub_bal_start(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if not await is_admin(user_id) or not await check_admin_permission(user_id, "can_manage_users"):
        await callback.answer("⚠️ Sizda ushbu ruxsat yo'q!", show_alert=True)
        return

    uid = int(callback.data.replace("sub_bal_", ""))
    await state.update_data(target_user_id=uid)
    await state.set_state(AdminStates.sub_user_bal)
    await callback.message.answer(f"➖ Foydalanuvchi (<code>{uid}</code>) hisobidan ayirmoqchi bo'lgan <b>tangalar miqdorini</b> yozing:", parse_mode="HTML")
    await callback.answer()

@router.message(AdminStates.sub_user_bal)
async def process_sub_bal(message: Message, state: FSMContext, bot: Bot):
    user_id = message.from_user.id
    if not await is_admin(user_id) or not await check_admin_permission(user_id, "can_manage_users"):
        return

    data = await state.get_data()
    uid = data["target_user_id"]
    try:
        amount = float(message.text.replace(" ", "").replace(",", "."))
    except ValueError:
        await message.answer("❌ Faqat son kiriting!")
        return

    await update_user_balance(uid, amount, mode="SUB")
    await state.clear()
    await message.answer(f"✅ Foydalanuvchi (<code>{uid}</code>) hisobidan <b>-{amount:,.1f} 🪙</b> ayirildi!", parse_mode="HTML")
    try:
        await bot.send_message(uid, f"⚠️ Admin tomonidan hisobingizdan <b>-{amount:,.1f} 🪙</b> tanga olindi!", parse_mode="HTML")
    except Exception:
        pass

# Lichkaga xabar yozish
@router.callback_query(F.data.startswith("msg_user_"))
async def cb_msg_user_start(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if not await is_admin(user_id) or not await check_admin_permission(user_id, "can_manage_users"):
        await callback.answer("⚠️ Sizda ushbu ruxsat yo'q!", show_alert=True)
        return

    uid = int(callback.data.replace("msg_user_", ""))
    await state.update_data(target_user_id=uid)
    await state.set_state(AdminStates.send_msg_to_user)
    await callback.message.answer(f"✍️ Foydalanuvchiga (<code>{uid}</code>) yubormoqchi bo'lgan xabaringizni yozing:", parse_mode="HTML")
    await callback.answer()

@router.message(AdminStates.send_msg_to_user)
async def process_send_msg_to_user(message: Message, state: FSMContext, bot: Bot):
    user_id = message.from_user.id
    if not await is_admin(user_id) or not await check_admin_permission(user_id, "can_manage_users"):
        return

    data = await state.get_data()
    uid = data["target_user_id"]
    await state.clear()

    try:
        await bot.send_message(
            uid,
            f"📩 <b>Admin xabari:</b>\n\n{message.text}",
            parse_mode="HTML"
        )
        await message.answer(f"✅ Xabar muvaffaqiyatli yetkazildi (ID: <code>{uid}</code>)!", parse_mode="HTML")
    except Exception as e:
        await message.answer(f"❌ Xabar yuborishda xatolik: {e}")

# BAN & UNBAN
@router.callback_query(F.data.startswith("ban_user_"))
async def cb_ban_user_start(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if not await is_admin(user_id) or not await check_admin_permission(user_id, "can_manage_users"):
        await callback.answer("⚠️ Sizda ushbu ruxsat yo'q!", show_alert=True)
        return

    uid = int(callback.data.replace("ban_user_", ""))
    await state.update_data(target_user_id=uid)
    await state.set_state(AdminStates.ban_user_reason)
    await callback.message.answer(f"🔴 Foydalanuvchini (<code>{uid}</code>) bloklash sababini yozing:")
    await callback.answer()

@router.message(AdminStates.ban_user_reason)
async def process_ban_user(message: Message, state: FSMContext, bot: Bot):
    user_id = message.from_user.id
    if not await is_admin(user_id) or not await check_admin_permission(user_id, "can_manage_users"):
        return

    data = await state.get_data()
    uid = data["target_user_id"]
    reason = message.text.strip()
    await ban_user(uid, reason)
    await state.clear()
    await message.answer(f"🚫 Foydalanuvchi <code>{uid}</code> muvaffaqiyatli bloklandi!", parse_mode="HTML")
    try:
        await bot.send_message(uid, f"🚫 <b>Siz botdan bloklandingiz!</b>\nSabab: <i>{reason}</i>", parse_mode="HTML")
    except Exception:
        pass

@router.callback_query(F.data.startswith("unban_user_"))
async def cb_unban_user(callback: CallbackQuery, bot: Bot):
    user_id = callback.from_user.id
    if not await is_admin(user_id) or not await check_admin_permission(user_id, "can_manage_users"):
        await callback.answer("⚠️ Sizda ushbu ruxsat yo'q!", show_alert=True)
        return

    uid = int(callback.data.replace("unban_user_", ""))
    await unban_user(uid)
    await callback.answer("🟢 Foydalanuvchi blokdan chiqarildi!", show_alert=True)
    try:
        await bot.send_message(uid, "🟢 <b>Sizning hisobingiz blokdan chiqarildi!</b> Endi botdan foydalanishingiz mumkin.", parse_mode="HTML")
    except Exception:
        pass

# --- NARX & KURSLAR SOZLAMALARI ---

@router.callback_query(F.data == "admin_rates")
async def cb_admin_rates(callback: CallbackQuery):
    user_id = callback.from_user.id
    if not await is_admin(user_id):
        return
    if not await check_admin_permission(user_id, "can_change_settings"):
        await callback.answer("⚠️ Sizda narxlarni o'zgartirish ruxsati yo'q!", show_alert=True)
        return

    settings = await get_all_settings()
    rate_sum = settings.get("coin_to_sum_rate", str(5000 / 12000))
    rate_uc = settings.get("coin_to_uc_rate", str(15000 / 60))
    min_card = settings.get("card_min_withdraw", "10000")
    min_pubg = settings.get("pubg_min_withdraw", "8000")

    text = (
        "⚙️ <b>NARX VA ALMASHUV KURSLARI</b>\n\n"
        f"1. 💳 Bank kartasiga: <b>10,000 🪙 = 5,000 so'm</b>\n"
        f"2. 🎮 PUBG UC: <b>15,000 🪙 = 60 UC</b>\n"
        f"3. 💳 Minimal karta yechish: <b>{float(min_card):,.0f} 🪙</b>\n"
        f"4. 🎮 Minimal PUBG UC yechish: <b>{float(min_pubg):,.0f} 🪙</b> (33 UC)\n\n"
        "O'zgartirmoqchi bo'lgan parametrni tanlang:"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ 1 Tanga = X So'm", callback_data="set_rate_sum")],
        [InlineKeyboardButton(text="✏️ 60 UC = X Tanga", callback_data="set_rate_uc")],
        [InlineKeyboardButton(text="✏️ Min Karta Limit", callback_data="set_min_card")],
        [InlineKeyboardButton(text="✏️ Min PUBG Limit", callback_data="set_min_pubg")],
        [InlineKeyboardButton(text="◀️ Orqaga", callback_data="admin_main")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")

@router.callback_query(F.data == "set_rate_sum")
async def cb_set_rate_sum(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if not await check_admin_permission(user_id, "can_change_settings"):
        await callback.answer("⚠️ Ruxsat yo'q!", show_alert=True)
        return
    await state.set_state(AdminStates.set_coin_sum_rate)
    await callback.message.answer("1 Tanga necha so'm bo'lishini kiriting (masalan: 0.416667 yoki 12000 coin = 5000 so'm):")
    await callback.answer()

@router.message(AdminStates.set_coin_sum_rate)
async def process_set_rate_sum(message: Message, state: FSMContext):
    val = message.text.strip()
    await set_setting("coin_to_sum_rate", val)
    await state.clear()
    await message.answer(f"✅ 1 Tanga kursi <b>{val} so'm</b> qilib belgilandi!", parse_mode="HTML")

@router.callback_query(F.data == "set_rate_uc")
async def cb_set_rate_uc(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if not await check_admin_permission(user_id, "can_change_settings"):
        await callback.answer("⚠️ Ruxsat yo'q!", show_alert=True)
        return
    await state.set_state(AdminStates.set_coin_uc_rate)
    await callback.message.answer("66 UC uchun necha tanga kerakligini kiriting (masalan: 15000):")
    await callback.answer()

@router.message(AdminStates.set_coin_uc_rate)
async def process_set_rate_uc(message: Message, state: FSMContext):
    val = message.text.strip()
    await set_setting("coin_to_uc_rate", val)
    await state.clear()
    await message.answer(f"✅ 60 UC uchun <b>{val} 🪙</b> qilib belgilandi!", parse_mode="HTML")

@router.callback_query(F.data == "set_min_card")
async def cb_set_min_card(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if not await check_admin_permission(user_id, "can_change_settings"):
        await callback.answer("⚠️ Ruxsat yo'q!", show_alert=True)
        return
    await state.set_state(AdminStates.set_card_min)
    await callback.message.answer("Bank kartasiga minimal yechish tangasini kiriting (masalan: 5000):")
    await callback.answer()

@router.message(AdminStates.set_card_min)
async def process_set_min_card(message: Message, state: FSMContext):
    val = message.text.strip()
    await set_setting("card_min_withdraw", val)
    await state.clear()
    await message.answer(f"✅ Kartaga minimal yechish <b>{val} 🪙</b> qilib belgilandi!", parse_mode="HTML")

@router.callback_query(F.data == "set_min_pubg")
async def cb_set_min_pubg(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if not await check_admin_permission(user_id, "can_change_settings"):
        await callback.answer("⚠️ Ruxsat yo'q!", show_alert=True)
        return
    await state.set_state(AdminStates.set_pubg_min)
    await callback.message.answer("PUBG UC uchun minimal yechish tangasini kiriting (masalan: 1000):")
    await callback.answer()

@router.message(AdminStates.set_pubg_min)
async def process_set_min_pubg(message: Message, state: FSMContext):
    val = message.text.strip()
    await set_setting("pubg_min_withdraw", val)
    await state.clear()
    await message.answer(f"✅ PUBG UC uchun minimal yechish <b>{val} 🪙</b> qilib belgilandi!", parse_mode="HTML")

# --- LIMIT & REGEN SOZLAMALARI ---

@router.callback_query(F.data == "admin_limits")
async def cb_admin_limits(callback: CallbackQuery):
    user_id = callback.from_user.id
    if not await is_admin(user_id):
        return
    if not await check_admin_permission(user_id, "can_change_settings"):
        await callback.answer("⚠️ Sizda sozlamalarni o'zgartirish ruxsati yo'q!", show_alert=True)
        return

    settings = await get_all_settings()
    init_limit = settings.get("initial_max_energy", "100")
    ref_bonus = settings.get("referral_bonus", "50")

    text = (
        "🔋 <b>LIMIT VA ENERGIYA SOZLAMALARI</b>\n\n"
        f"1. ⚡️ Boshlang'ich energiya limiti: <b>{init_limit} ta</b>\n"
        f"2. 👥 Referal taklif bonusi: <b>{ref_bonus} 🪙</b>\n\n"
        "O'zgartirish uchun tanlang:"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Boshlang'ich Limitni O'zgartirish", callback_data="set_init_limit")],
        [InlineKeyboardButton(text="✏️ Referal Bonusini O'zgartirish", callback_data="set_ref_bonus")],
        [InlineKeyboardButton(text="◀️ Orqaga", callback_data="admin_main")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")

@router.callback_query(F.data == "set_init_limit")
async def cb_set_init_limit(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if not await check_admin_permission(user_id, "can_change_settings"):
        await callback.answer("⚠️ Ruxsat yo'q!", show_alert=True)
        return
    await state.set_state(AdminStates.set_init_limit)
    await callback.message.answer("Yangi foydalanuvchilar uchun boshlang'ich limitni kiriting (masalan: 100):")
    await callback.answer()

@router.message(AdminStates.set_init_limit)
async def process_set_init_limit(message: Message, state: FSMContext):
    val = message.text.strip()
    await set_setting("initial_max_energy", val)
    await state.clear()
    await message.answer(f"✅ Boshlang'ich limit <b>{val}</b> qilib belgilandi!", parse_mode="HTML")

@router.callback_query(F.data == "set_ref_bonus")
async def cb_set_ref_bonus(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if not await check_admin_permission(user_id, "can_change_settings"):
        await callback.answer("⚠️ Ruxsat yo'q!", show_alert=True)
        return
    await state.set_state(AdminStates.set_ref_bonus)
    await callback.message.answer("Do'st taklif qilganda beriladigan bonus tangani kiriting (masalan: 50):")
    await callback.answer()

@router.message(AdminStates.set_ref_bonus)
async def process_set_ref_bonus(message: Message, state: FSMContext):
    val = message.text.strip()
    await set_setting("referral_bonus", val)
    await state.clear()
    await message.answer(f"✅ Referal bonusi <b>{val} 🪙</b> qilib belgilandi!", parse_mode="HTML")

# --- MAJBURIY KANALLAR BOSHQARUVI ---

@router.callback_query(F.data == "admin_channels")
async def cb_admin_channels(callback: CallbackQuery):
    user_id = callback.from_user.id
    if not await is_admin(user_id):
        return
    if not await check_admin_permission(user_id, "can_manage_channels"):
        await callback.answer("⚠️ Sizda majburiy kanallarni boshqarish ruxsati yo'q!", show_alert=True)
        return

    channels = await get_all_channels()
    text = "📢 <b>MAJBURIY OBUNA KANALLARI</b>\n\n"
    kb = []
    
    if channels:
        text += "Ulangan homiy kanallar ro'yxati:\n"
        for i, ch in enumerate(channels, 1):
            text += f"{i}. <b>{ch['channel_title']}</b> (<code>{ch['channel_id']}</code>)\n"
            kb.append([InlineKeyboardButton(text=f"🗑 O'chirish: {ch['channel_title']}", callback_data=f"del_ch_{ch['channel_id']}")])
    else:
        text += "<i>Hozircha hech qanday majburiy kanal ulanmagan.</i>\n"

    kb.append([InlineKeyboardButton(text="➕ Yangi Kanal Qo'shish", callback_data="add_new_channel")])
    kb.append([InlineKeyboardButton(text="◀️ Orqaga", callback_data="admin_main")])
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="HTML")

@router.callback_query(F.data == "add_new_channel")
async def cb_add_channel_start(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if not await check_admin_permission(user_id, "can_manage_channels"):
        await callback.answer("⚠️ Ruxsat yo'q!", show_alert=True)
        return
    await state.set_state(AdminStates.add_ch_id)
    await callback.message.answer(
        "📢 Kanal ID yoki @username kiriting (masalan: <code>@kanalim</code> yoki <code>-1001234567890</code>):\n\n"
        "<i>⚠️ DIQQAT: Bot ushbu kanalda administrator bo'lishi shart!</i>",
        parse_mode="HTML"
    )
    await callback.answer()

@router.message(AdminStates.add_ch_id)
async def process_add_ch_id(message: Message, state: FSMContext):
    cid = message.text.strip()
    await state.update_data(channel_id=cid)
    await state.set_state(AdminStates.add_ch_title)
    await message.answer("Kanal nomini kiriting (masalan: Rasmiy Kanal):")

@router.message(AdminStates.add_ch_title)
async def process_add_ch_title(message: Message, state: FSMContext):
    title = message.text.strip()
    await state.update_data(channel_title=title)
    await state.set_state(AdminStates.add_ch_url)
    await message.answer("Kanalga ulanish havolasini (Link) kiriting (masalan: https://t.me/kanalim):")

@router.message(AdminStates.add_ch_url)
async def process_add_ch_url(message: Message, state: FSMContext):
    url = message.text.strip()
    data = await state.get_data()
    await add_channel(data["channel_id"], data["channel_title"], url)
    await state.clear()
    await message.answer(f"✅ <b>{data['channel_title']}</b> kanali muvaffaqiyatli qo'shildi!", parse_mode="HTML")

@router.callback_query(F.data.startswith("del_ch_"))
async def cb_del_channel(callback: CallbackQuery):
    user_id = callback.from_user.id
    if not await check_admin_permission(user_id, "can_manage_channels"):
        await callback.answer("⚠️ Ruxsat yo'q!", show_alert=True)
        return
    cid = callback.data.replace("del_ch_", "")
    await delete_channel(cid)
    await callback.answer("🗑 Kanal o'chirildi!", show_alert=True)
    await cb_admin_channels(callback)

# --- ZAYAFKA KANALI ---

@router.callback_query(F.data == "admin_zayafka_ch")
async def cb_admin_zayafka_ch(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if not await is_admin(user_id):
        return
    if not await check_admin_permission(user_id, "can_manage_channels"):
        await callback.answer("⚠️ Sizda ushbu ruxsat yo'q!", show_alert=True)
        return

    current_ch = await get_all_settings()
    z_ch = current_ch.get("zayafka_channel_id", "Ulanmagan")
    text = (
        "💳 <b>ZAYAFKA KANALI SOZLAMASI</b>\n\n"
        f"Foydalanuvchilar pul/UC yechish so'rovi yuborganida barcha ma'lumotlar ushbu kanalga tushadi.\n\n"
        f"Joriy Zayafka kanali: <code>{z_ch}</code>\n\n"
        "O'zgartirish uchun kanal ID yoki @username yuboring:"
    )
    await state.set_state(AdminStates.set_zayafka_ch)
    await callback.message.edit_text(text, reply_markup=admin_back_keyboard("admin_main"), parse_mode="HTML")

@router.message(AdminStates.set_zayafka_ch)
async def process_set_zayafka_ch(message: Message, state: FSMContext):
    cid = message.text.strip()
    await set_setting("zayafka_channel_id", cid)
    await state.clear()
    await message.answer(f"✅ Zayafka kanali <code>{cid}</code> qilib belgilandi! (Bot kanalga admin bo'lishi lozim)", parse_mode="HTML")

# --- ZAYAFKALARNI BOSHQARISH & TASDIQLASH ---

@router.callback_query(F.data == "admin_withdrawals")
async def cb_admin_withdrawals(callback: CallbackQuery):
    user_id = callback.from_user.id
    if not await is_admin(user_id):
        return
    if not await check_admin_permission(user_id, "can_manage_withdrawals"):
        await callback.answer("⚠️ Sizda zayafkalarni ko'rish va boshqarish ruxsati yo'q!", show_alert=True)
        return

    pending = await get_pending_withdrawals(limit=10)
    if not pending:
        await callback.message.edit_text("✅ Kutilayotgan zayafkalar mavjud emas!", reply_markup=admin_back_keyboard("admin_main"))
        return

    text = f"📑 <b>KUTILAYOTGAN ZAYAFKALAR ({len(pending)} ta):</b>\n\n"
    for w in pending:
        unit = "so'm" if w["type"] == "CARD" else "UC"
        text += (
            f"🆔 <b>#{w['id']}</b> | Foydalanuvchi: <code>{w['user_id']}</code>\n"
            f"💵 Summa: <b>{w['amount_target']:,.0f} {unit}</b> ({w['amount_coins']:,.0f} 🪙)\n"
            f"📌 Rekvizit: <code>{w['target_value']}</code> ({w['target_details']})\n"
            f"📅 Sana: {w['created_at']}\n"
            f"------------------------------------\n"
        )
    
    kb = []
    for w in pending:
        kb.append([
            InlineKeyboardButton(text=f"✅ #{w['id']} To'landi", callback_data=f"approve_w_{w['id']}"),
            InlineKeyboardButton(text=f"❌ #{w['id']} Rad etish", callback_data=f"reject_w_{w['id']}")
        ])
    kb.append([InlineKeyboardButton(text="◀️ Orqaga", callback_data="admin_main")])
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="HTML")

@router.callback_query(F.data.startswith("approve_w_"))
async def cb_approve_withdrawal(callback: CallbackQuery, bot: Bot):
    user_id = callback.from_user.id
    if not await is_admin(user_id) or not await check_admin_permission(user_id, "can_manage_withdrawals"):
        await callback.answer("⚠️ Sizda ushbu ruxsat yo'q!", show_alert=True)
        return

    w_id = int(callback.data.replace("approve_w_", ""))
    w = await get_withdrawal(w_id)
    if not w or w["status"] != "PENDING":
        await callback.answer("Zayafka allaqachon ko'rib chiqilgan!", show_alert=True)
        return

    await resolve_withdrawal(w_id, "APPROVED", "To'lov amalga oshirildi")
    await callback.answer("✅ Zayafka tasdiqlandi!")
    
    try:
        await callback.message.edit_text(
            f"{callback.message.text}\n\n✅ <b>TO'LANDI! (Admin: {callback.from_user.full_name})</b>",
            parse_mode="HTML"
        )
    except TelegramBadRequest:
        pass

    unit = "so'm" if w["type"] == "CARD" else "UC"
    try:
        await bot.send_message(
            w["user_id"],
            f"🎉 <b>Xushxabar! Pul yechish zayafkangiz tasdiqlandi!</b>\n\n"
            f"🆔 Zayafka: <b>#{w_id}</b>\n"
            f"💵 Summa: <b>{w['amount_target']:,.0f} {unit}</b>\n"
            f"📌 Hisobingizga muvaffaqiyatli o'tkazib berildi!",
            parse_mode="HTML"
        )
    except Exception:
        pass

@router.callback_query(F.data.startswith("reject_w_"))
async def cb_reject_withdrawal_start(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if not await is_admin(user_id) or not await check_admin_permission(user_id, "can_manage_withdrawals"):
        await callback.answer("⚠️ Sizda ushbu ruxsat yo'q!", show_alert=True)
        return

    w_id = int(callback.data.replace("reject_w_", ""))
    await state.update_data(target_w_id=w_id)
    await state.set_state(AdminStates.reject_reason)
    await callback.message.answer(f"❌ #{w_id} zayafkani rad etish sababini yozing (Foydalanuvchiga yuboriladi va tangalari qaytariladi):")
    await callback.answer()

@router.message(AdminStates.reject_reason)
async def process_reject_withdrawal(message: Message, state: FSMContext, bot: Bot):
    user_id = message.from_user.id
    if not await is_admin(user_id) or not await check_admin_permission(user_id, "can_manage_withdrawals"):
        return

    data = await state.get_data()
    w_id = data["target_w_id"]
    reason = message.text.strip()
    
    w = await get_withdrawal(w_id)
    if not w:
        await message.answer("Zayafka topilmadi!")
        await state.clear()
        return

    await resolve_withdrawal(w_id, "REJECTED", reason)
    await state.clear()
    await message.answer(f"❌ #{w_id} zayafka rad etildi va {w['amount_coins']:,.0f} 🪙 tanga foydalanuvchiga qaytarildi!")

    try:
        await bot.send_message(
            w["user_id"],
            f"❌ <b>Sizning pul yechish zayafkangiz rad etildi!</b>\n\n"
            f"🆔 Zayafka: <b>#{w_id}</b>\n"
            f"📝 Sabab: <i>{reason}</i>\n"
            f"🔄 <b>{w['amount_coins']:,.0f} 🪙</b> tanga balansingizga qaytarildi.",
            parse_mode="HTML"
        )
    except Exception:
        pass

@router.callback_query(F.data == "admin_download_db")
async def cb_admin_download_db(callback: CallbackQuery, bot: Bot):
    user_id = callback.from_user.id
    if not await is_admin(user_id):
        await callback.answer("⚠️ Ruxsat yo'q!", show_alert=True)
        return

    if not os.path.exists(DB_NAME):
        await callback.answer("❌ Baza fayli topilmadi!", show_alert=True)
        return

    await callback.answer("⏳ Baza nusxasi tayyorlanmoqda...")
    try:
        db_file = FSInputFile(DB_NAME, filename="clicker_bot_backup.db")
        await callback.message.answer_document(
            document=db_file,
            caption="💾 <b>Ma'lumotlar bazasining to'liq zaxira nusxasi (Backup)</b>\n\n"
                    "Ushbu fayl barcha foydalanuvchilar, ularning hisoblari, pullari, sozlamalar va zayafkalarni o'z ichiga oladi.",
            parse_mode="HTML"
        )
    except Exception as e:
        await callback.message.answer(f"❌ Xatolik yuz berdi: {e}")

@router.callback_query(F.data == "admin_export_users_excel")
async def cb_admin_export_users_excel(callback: CallbackQuery):
    user_id = callback.from_user.id
    if not await is_admin(user_id):
        await callback.answer("⚠️ Ruxsat yo'q!", show_alert=True)
        return

    await callback.answer("⏳ Foydalanuvchilar Excel hisoboti tayyorlanmoqda...")
    try:
        excel_path = await generate_users_excel()
        excel_file = FSInputFile(excel_path, filename="foydalanuvchilar_hisoboti.xlsx")
        await callback.message.answer_document(
            document=excel_file,
            caption="📊 <b>Barcha Foydalanuvchilar Excel Jadvali (.xlsx)</b>\n\n"
                    "Jadvalda foydalanuvchilar IDsi, ism-familiyasi, balansi, quvvati, referallari va ro'yxatdan o'tgan sanasi to'liq ko'rsatilgan.",
            parse_mode="HTML"
        )
    except Exception as e:
        await callback.message.answer(f"❌ Excel yaratishda xatolik: {e}")

@router.callback_query(F.data == "admin_export_withdraw_excel")
async def cb_admin_export_withdraw_excel(callback: CallbackQuery):
    user_id = callback.from_user.id
    if not await is_admin(user_id):
        await callback.answer("⚠️ Ruxsat yo'q!", show_alert=True)
        return

    await callback.answer("⏳ Zayafkalar Excel hisoboti tayyorlanmoqda...")
    try:
        excel_path = await generate_withdrawals_excel()
        excel_file = FSInputFile(excel_path, filename="zayafkalar_hisoboti.xlsx")
        await callback.message.answer_document(
            document=excel_file,
            caption="📑 <b>Pul & UC Yechish Zayafkalari Excel Jadvali (.xlsx)</b>\n\n"
                    "Jadvalda barcha pul yechish so'rovlari, karta raqamlari, PUBG IDlar, holati va to'langan summalar to'liq keltirilgan.",
            parse_mode="HTML"
        )
    except Exception as e:
        await callback.message.answer(f"❌ Excel yaratishda xatolik: {e}")
