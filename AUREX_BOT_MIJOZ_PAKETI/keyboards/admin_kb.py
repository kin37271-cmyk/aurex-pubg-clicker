# keyboards/admin_kb.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def admin_main_keyboard(is_owner: bool = True) -> InlineKeyboardMarkup:
    kb = [
        [
            InlineKeyboardButton(text="📊 To'liq Statistika", callback_data="admin_stats"),
            InlineKeyboardButton(text="👤 Mijozlar (Foydalanuvchilar)", callback_data="admin_users")
        ],
        [
            InlineKeyboardButton(text="📑 Zayafkalar (Pul yechish)", callback_data="admin_withdrawals"),
            InlineKeyboardButton(text="📢 Xabar Tarqatish", callback_data="admin_broadcast")
        ],
        [
            InlineKeyboardButton(text="⚙️ Narx & Kurslar", callback_data="admin_rates"),
            InlineKeyboardButton(text="🔋 Limit & Tiklanish", callback_data="admin_limits")
        ],
        [
            InlineKeyboardButton(text="📢 Majburiy Kanallar", callback_data="admin_channels"),
            InlineKeyboardButton(text="💳 Zayafka Kanali", callback_data="admin_zayafka_ch")
        ],
        [
            InlineKeyboardButton(text="📊 Excel (Foydalanuvchilar)", callback_data="admin_export_users_excel"),
            InlineKeyboardButton(text="📑 Excel (Zayafkalar)", callback_data="admin_export_withdraw_excel")
        ],
        [
            InlineKeyboardButton(text="💾 Baza Nusxasi (Backup)", callback_data="admin_download_db")
        ]
    ]
    if is_owner:
        kb.append([InlineKeyboardButton(text="👮‍♂️ Adminlar & Ruxsatlar", callback_data="admin_manage_admins")])
        
    kb.append([InlineKeyboardButton(text="◀️ Admin Paneldan Chiqish", callback_data="admin_exit")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def admin_user_control_keyboard(user_id: int, is_banned: bool) -> InlineKeyboardMarkup:
    ban_btn_text = "🟢 Bandan Olish" if is_banned else "🔴 Bloklash (BAN)"
    ban_callback = f"unban_user_{user_id}" if is_banned else f"ban_user_{user_id}"
    
    kb = [
        [
            InlineKeyboardButton(text="➕ Balans Qo'shish", callback_data=f"add_bal_{user_id}"),
            InlineKeyboardButton(text="➖ Balans Ayirish", callback_data=f"sub_bal_{user_id}")
        ],
        [
            InlineKeyboardButton(text="✍️ Lichkaga Xabar Yozish", callback_data=f"msg_user_{user_id}"),
            InlineKeyboardButton(text=ban_btn_text, callback_data=ban_callback)
        ],
        [InlineKeyboardButton(text="◀️ Foydalanuvchilar menyusi", callback_data="admin_users")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

def admin_withdrawal_action_keyboard(w_id: int) -> InlineKeyboardMarkup:
    kb = [
        [
            InlineKeyboardButton(text="✅ Tasdiqlash (To'landi)", callback_data=f"approve_w_{w_id}"),
            InlineKeyboardButton(text="❌ Rad etish", callback_data=f"reject_w_{w_id}")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

def admin_list_keyboard(admins: list) -> InlineKeyboardMarkup:
    kb = []
    for adm in admins:
        role_icon = "👑" if adm.get("role") == "owner" else "👮‍♂️"
        title = f"{role_icon} {adm.get('full_name') or adm['user_id']}"
        kb.append([InlineKeyboardButton(text=title, callback_data=f"adm_detail_{adm['user_id']}")])
    
    kb.append([InlineKeyboardButton(text="➕ Yangi Admin Qo'shish", callback_data="add_new_admin_btn")])
    kb.append([InlineKeyboardButton(text="◀️ Orqaga", callback_data="admin_main")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def admin_permissions_keyboard(admin: dict, is_current_user_owner: bool = True) -> InlineKeyboardMarkup:
    uid = admin["user_id"]
    is_owner = admin.get("role") == "owner"
    
    def mark(key):
        if is_owner:
            return "✅"
        return "✅" if admin.get(key, 0) == 1 else "❌"

    kb = [
        [InlineKeyboardButton(text=f"{mark('can_manage_users')} 👤 Mijozlarni boshqarish", callback_data=f"tog_perm_{uid}_can_manage_users")],
        [InlineKeyboardButton(text=f"{mark('can_manage_withdrawals')} 💳 Zayafkalarni ko'rish/tasdiqlash", callback_data=f"tog_perm_{uid}_can_manage_withdrawals")],
        [InlineKeyboardButton(text=f"{mark('can_change_settings')} ⚙️ Narx & Kurslarni o'zgartirish", callback_data=f"tog_perm_{uid}_can_change_settings")],
        [InlineKeyboardButton(text=f"{mark('can_manage_channels')} 📢 Majburiy kanallar", callback_data=f"tog_perm_{uid}_can_manage_channels")],
        [InlineKeyboardButton(text=f"{mark('can_broadcast')} 📨 Xabar tarqatish (Broadcast)", callback_data=f"tog_perm_{uid}_can_broadcast")],
    ]
    
    if not is_owner and is_current_user_owner:
        kb.append([InlineKeyboardButton(text="🗑 Adminlikdan Olib Tashlash", callback_data=f"del_admin_{uid}")])
        
    kb.append([InlineKeyboardButton(text="◀️ Adminlar Ro'yxati", callback_data="admin_manage_admins")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def admin_back_keyboard(target: str = "admin_main") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Orqaga", callback_data=target)]
    ])
