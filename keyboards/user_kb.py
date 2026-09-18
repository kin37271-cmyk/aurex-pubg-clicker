# keyboards/user_kb.py
from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    WebAppInfo
)
from urllib.parse import quote
from database import UPGRADE_COSTS
from config import WEBAPP_URL

def is_valid_webapp_url(url: str) -> bool:
    return bool(url and url.startswith("https://"))

def build_webapp_url(user_id: int = None, username: str = "", full_name: str = "") -> str:
    if not is_valid_webapp_url(WEBAPP_URL):
        return ""
    if not user_id:
        return WEBAPP_URL
    params = f"?user_id={user_id}"
    if username:
        params += f"&username={quote(str(username))}"
    if full_name:
        params += f"&full_name={quote(str(full_name))}"
    return f"{WEBAPP_URL}{params}"

def main_menu_keyboard(is_admin: bool = False, user_id: int = None, username: str = "", full_name: str = "") -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton(text="⚡️ Do'kon (Kuchaytirish)"), KeyboardButton(text="💳 Pul Yechish (UC / Karta)")],
        [KeyboardButton(text="👥 Do'stlar (Referal)"), KeyboardButton(text="👤 Profil & Balans")],
        [KeyboardButton(text="📊 Bot Statistikasi"), KeyboardButton(text="ℹ️ Qo'llanma")]
    ]
    
    if is_admin:
        keyboard.append([KeyboardButton(text="👑 Admin Panel")])
        
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True, is_persistent=True)

def webapp_inline_keyboard(user_id: int, username: str = "", full_name: str = "") -> InlineKeyboardMarkup:
    kb = []
    app_url = build_webapp_url(user_id, username, full_name)
    if app_url:
        kb.append([InlineKeyboardButton(text="🔥 Aurex PUBG Clicker (Web App)", web_app=WebAppInfo(url=app_url))])
        
    kb.append([
        InlineKeyboardButton(text="⚡️ Do'kon", callback_data="open_shop"),
        InlineKeyboardButton(text="💳 Pul Yechish", callback_data="withdraw_menu_cb")
    ])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def clicker_inline_keyboard(user_id: int, username: str = "", full_name: str = "") -> InlineKeyboardMarkup:
    kb = []
    app_url = build_webapp_url(user_id, username, full_name)
    if app_url:
        kb.append([InlineKeyboardButton(text="🔥 Web Appda O'ynash (AUREX)", web_app=WebAppInfo(url=app_url))])

    kb.append([
        InlineKeyboardButton(text="⚡️ Do'konga o'tish", callback_data="open_shop"),
        InlineKeyboardButton(text="💳 Pul Yechish", callback_data="withdraw_menu_cb")
    ])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def shop_inline_keyboard(user: dict) -> InlineKeyboardMarkup:
    m_lvl = user["multitap_level"]
    m_cost = UPGRADE_COSTS["multitap"](m_lvl)

    e_lvl = user["energy_level"]
    e_cost = UPGRADE_COSTS["max_energy"](e_lvl)

    r_lvl = user["regen_level"]
    r_cost = UPGRADE_COSTS["regen"](r_lvl)

    a_lvl = user["autobot_level"]
    a_cost = UPGRADE_COSTS["autobot"](a_lvl)

    kb = [
        [InlineKeyboardButton(text=f"👆 Multitap (Lvl {m_lvl}) - {m_cost} 🪙", callback_data="buy_multitap")],
        [InlineKeyboardButton(text=f"🔋 Max Limit (Lvl {e_lvl}) - {e_cost} 🪙", callback_data="buy_max_energy")],
        [InlineKeyboardButton(text=f"⏳ Tezkor Quvvat (Lvl {r_lvl}) - {r_cost} 🪙", callback_data="buy_regen")],
        [InlineKeyboardButton(text=f"🤖 Auto-Bot (Lvl {a_lvl}) - {a_cost} 🪙", callback_data="buy_autobot")],
    ]
    if a_lvl > 0:
        kb.append([InlineKeyboardButton(text="💰 Auto-Bot tangalarini yig'ish", callback_data="claim_autobot")])
    kb.append([InlineKeyboardButton(text="◀️ Menyuga qaytish", callback_data="back_to_menu")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def withdraw_methods_keyboard() -> InlineKeyboardMarkup:
    kb = [
        [
            InlineKeyboardButton(text="💳 Bank Kartasiga (So'm)", callback_data="withdraw_card"),
            InlineKeyboardButton(text="🎮 PUBG Mobile (UC)", callback_data="withdraw_pubg")
        ],
        [InlineKeyboardButton(text="📜 Mening zayafkalarim", callback_data="my_withdrawals")],
        [InlineKeyboardButton(text="◀️ Bekor qilish", callback_data="cancel_withdraw")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

def subscription_keyboard(channels: list) -> InlineKeyboardMarkup:
    buttons = []
    for i, ch in enumerate(channels, 1):
        url = ch["channel_url"]
        if not url.startswith("http"):
            url = f"https://t.me/{ch['channel_id'].lstrip('@')}"
        buttons.append([InlineKeyboardButton(text=f"📢 {ch.get('channel_title') or f'{i}-Kanal'}", url=url)])
    
    buttons.append([InlineKeyboardButton(text="✅ A'zo bo'ldim (Tekshirish)", callback_data="check_subscription")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)
