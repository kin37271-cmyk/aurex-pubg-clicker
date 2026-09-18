# web_server.py
import os
import json
import time
import asyncio
from aiohttp import web
from database import (
    get_or_create_user,
    get_user,
    tap_user,
    buy_upgrade,
    claim_autobot,
    create_withdrawal,
    get_statistics,
    get_setting,
    get_all_settings,
    set_setting,
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
    get_all_user_ids,
    is_admin_user,
    UPGRADE_COSTS,
    DEFAULT_CARD_MIN_WITHDRAW,
    DEFAULT_PUBG_MIN_WITHDRAW,
    DEFAULT_COIN_TO_SUM_RATE,
    DEFAULT_COIN_TO_UC_RATE,
    DEFAULT_REFERRAL_BONUS
)
from config import ADMINS, OWNER_ID

routes = web.RouteTableDef()
STATIC_DIR = os.path.join(os.path.dirname(__file__), "webapp")

@routes.get("/healthz")
@routes.get("/health")
async def health_handler(request):
    return web.Response(text="OK", status=200)

async def check_is_admin(user_id: int) -> bool:
    try:
        if not user_id or int(user_id) == 0:
            return False
        return await is_admin_user(int(user_id))
    except Exception:
        return False

@routes.get("/")
async def index_handler(request):
    return web.FileResponse(os.path.join(STATIC_DIR, "index.html"))

@routes.get("/api/user")
async def get_user_api(request):
    user_id = request.query.get("user_id")
    if not user_id:
        return web.json_response({"error": "user_id is required"}, status=400)
    
    try:
        uid = int(user_id)
    except ValueError:
        return web.json_response({"error": "Invalid user_id"}, status=400)

    username = request.query.get("username", "")
    full_name = request.query.get("full_name", "Foydalanuvchi")
    referrer_id = request.query.get("ref")
    ref_id = int(referrer_id) if referrer_id and referrer_id.isdigit() else None

    user = await get_or_create_user(uid, username, full_name, ref_id)
    settings = await get_all_settings()

    return web.json_response({
        "user": user,
        "is_admin": await check_is_admin(uid),
        "upgrade_costs": {
            "multitap": UPGRADE_COSTS["multitap"](user["multitap_level"]),
            "max_energy": UPGRADE_COSTS["max_energy"](user["energy_level"]),
            "regen": UPGRADE_COSTS["regen"](user["regen_level"]),
            "autobot": UPGRADE_COSTS["autobot"](user["autobot_level"])
        },
        "rates": {
            "coin_to_sum": float(settings.get("coin_to_sum_rate", DEFAULT_COIN_TO_SUM_RATE)),
            "coin_to_uc": float(settings.get("coin_to_uc_rate", DEFAULT_COIN_TO_UC_RATE)),
            "min_card": float(settings.get("card_min_withdraw", DEFAULT_CARD_MIN_WITHDRAW)),
            "min_pubg": float(settings.get("pubg_min_withdraw", DEFAULT_PUBG_MIN_WITHDRAW)),
            "ref_bonus": float(settings.get("referral_bonus", DEFAULT_REFERRAL_BONUS))
        }
    })

@routes.post("/api/tap")
async def tap_api(request):
    try:
        data = await request.json()
        user_id = int(data.get("user_id"))
        count = int(data.get("count", 1))
    except Exception:
        return web.json_response({"error": "Invalid payload"}, status=400)

    user = await get_user(user_id)
    if not user:
        user = await get_or_create_user(user_id, "", "Aurex Player")
    if user["is_banned"]:
        return web.json_response({"error": "User is banned"}, status=403)

    multitap = user["multitap_level"]
    available_taps = min(count, user["energy"] // multitap) if multitap > 0 else 0
    if available_taps <= 0:
        return web.json_response({"error": "No energy left", "user": user}, status=400)

    import aiosqlite
    from database import DB_NAME
    now = int(time.time())
    energy_spent = available_taps * multitap
    coins_earned = available_taps * multitap

    new_energy = user["energy"] - energy_spent
    new_balance = user["balance"] + coins_earned
    new_total = user["total_earned"] + coins_earned

    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            UPDATE users SET energy = ?, balance = ?, total_earned = ?, last_energy_update = ?
            WHERE user_id = ?
        """, (new_energy, new_balance, new_total, now, user_id))
        await db.commit()

    user["energy"] = new_energy
    user["balance"] = new_balance
    user["total_earned"] = new_total
    user["last_energy_update"] = now

    return web.json_response({
        "success": True,
        "earned": coins_earned,
        "user": user
    })

@routes.post("/api/upgrade")
async def upgrade_api(request):
    try:
        data = await request.json()
        user_id = int(data.get("user_id"))
        upgrade_type = data.get("type")
    except Exception:
        return web.json_response({"error": "Invalid payload"}, status=400)

    success, msg = await buy_upgrade(user_id, upgrade_type)
    user = await get_user(user_id)
    return web.json_response({
        "success": success,
        "message": msg,
        "user": user,
        "upgrade_costs": {
            "multitap": UPGRADE_COSTS["multitap"](user["multitap_level"]),
            "max_energy": UPGRADE_COSTS["max_energy"](user["energy_level"]),
            "regen": UPGRADE_COSTS["regen"](user["regen_level"]),
            "autobot": UPGRADE_COSTS["autobot"](user["autobot_level"])
        }
    })

@routes.post("/api/claim_autobot")
async def claim_autobot_api(request):
    try:
        data = await request.json()
        user_id = int(data.get("user_id"))
    except Exception:
        return web.json_response({"error": "Invalid payload"}, status=400)

    coins, msg = await claim_autobot(user_id)
    user = await get_user(user_id)
    return web.json_response({
        "success": coins > 0,
        "coins": coins,
        "message": msg,
        "user": user
    })

@routes.post("/api/withdraw")
async def withdraw_api(request):
    try:
        data = await request.json()
        user_id = int(data.get("user_id"))
        w_type = data.get("type")
        amount_coins = float(data.get("amount_coins"))
        target_val = data.get("target_val", "").strip()
        target_details = data.get("target_details", "").strip()
    except Exception:
        return web.json_response({"error": "Invalid payload"}, status=400)

    user = await get_user(user_id)
    if not user or user["balance"] < amount_coins:
        return web.json_response({"error": "Mablag' yetarli emas!"}, status=400)

    settings = await get_all_settings()
    rate_sum = float(settings.get("coin_to_sum_rate", DEFAULT_COIN_TO_SUM_RATE))
    rate_uc = float(settings.get("coin_to_uc_rate", DEFAULT_COIN_TO_UC_RATE))
    min_card = float(settings.get("card_min_withdraw", DEFAULT_CARD_MIN_WITHDRAW))
    min_pubg = float(settings.get("pubg_min_withdraw", DEFAULT_PUBG_MIN_WITHDRAW))

    if w_type == "CARD":
        if amount_coins < min_card:
            return web.json_response({"error": f"Minimal yechish: {min_card:,.0f} coin ({min_card * rate_sum:,.0f} so'm)"}, status=400)
        payout = amount_coins * rate_sum
    else:
        if amount_coins < min_pubg:
            return web.json_response({"error": f"Minimal yechish: {min_pubg:,.0f} coin (33 UC)"}, status=400)
        if amount_coins < 15000:
            payout = 33 + ((amount_coins - 8000) / 7000) * 27 if amount_coins > 8000 else 33
        else:
            payout = (amount_coins / 15000) * 60
        payout = int(round(payout))

    w_id = await create_withdrawal(user_id, w_type, amount_coins, payout, target_val, target_details)
    user = await get_user(user_id)

    # Bot admin notification
    bot = request.app["bot"]
    if bot:
        unit_str = "so'm" if w_type == "CARD" else "UC"
        admin_text = (
            f"🆕 <b>WEB APP ORQALI YANGI ZAYAFKA (#{w_id})</b>\n\n"
            f"👤 Foydalanuvchi: <code>{user_id}</code>\n"
            f"📌 Turi: <b>{w_type}</b>\n"
            f"💎 Tangalar: <b>{amount_coins:,.0f} 🪙</b>\n"
            f"💵 Summa / UC: <b>{payout:,.0f} {unit_str}</b>\n"
            f"💳 Rekvizit: <code>{target_val}</code>\n"
            f"👤 Tafsilot: {target_details}"
        )
        from keyboards.admin_kb import admin_withdrawal_action_keyboard
        kb = admin_withdrawal_action_keyboard(w_id)
        from database import get_all_admins
        from config import OWNER_ID
        active_admins = await get_all_admins()
        admin_ids = {OWNER_ID} | {a["user_id"] for a in active_admins}
        for admin_id in admin_ids:
            try:
                await bot.send_message(admin_id, admin_text, reply_markup=kb, parse_mode="HTML")
            except Exception:
                pass
        
        z_ch = settings.get("zayafka_channel_id")
        if z_ch:
            try:
                await bot.send_message(z_ch, admin_text, reply_markup=kb, parse_mode="HTML")
            except Exception:
                pass

    return web.json_response({
        "success": True,
        "withdrawal_id": w_id,
        "message": f"Zayafkangiz qabul qilindi (#{w_id})!",
        "user": user
    })

# ==================== WEB APP ADMIN API ====================

@routes.get("/api/admin/data")
async def admin_get_data(request):
    admin_id = request.query.get("admin_id")
    if not admin_id or not await check_is_admin(int(admin_id)):
        return web.json_response({"error": "Ruxsat etilmagan (Admin emas)"}, status=403)

    stats = await get_statistics()
    pending_withdrawals = await get_pending_withdrawals(limit=25)
    settings = await get_all_settings()
    channels = await get_all_channels()

    return web.json_response({
        "stats": stats,
        "withdrawals": pending_withdrawals,
        "settings": settings,
        "channels": channels
    })

@routes.post("/api/admin/resolve_withdrawal")
async def admin_resolve_w(request):
    try:
        data = await request.json()
        admin_id = int(data.get("admin_id"))
        if not await check_is_admin(admin_id):
            return web.json_response({"error": "Admin huquqi talab qilinadi"}, status=403)
        
        w_id = int(data.get("withdrawal_id"))
        status = data.get("status") # "APPROVED" or "REJECTED"
        note = data.get("note", "")
    except Exception:
        return web.json_response({"error": "Invalid payload"}, status=400)

    w = await get_withdrawal(w_id)
    if not w:
        return web.json_response({"error": "Zayafka topilmadi"}, status=404)

    success, msg = await resolve_withdrawal(w_id, status, note)
    
    # Notify user in Telegram PM
    bot = request.app["bot"]
    if bot and success:
        unit = "so'm" if w["type"] == "CARD" else "UC"
        if status == "APPROVED":
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
        else:
            try:
                await bot.send_message(
                    w["user_id"],
                    f"❌ <b>Sizning zayafkangiz rad etildi!</b>\n\n"
                    f"🆔 Zayafka: <b>#{w_id}</b>\n"
                    f"📝 Sabab: <i>{note or 'Admin tomonidan bekor qilindi'}</i>\n"
                    f"🔄 <b>{w['amount_coins']:,.0f} 🪙</b> tanga hisobingizga qaytarildi.",
                    parse_mode="HTML"
                )
            except Exception:
                pass

    return web.json_response({"success": success, "message": msg})

@routes.post("/api/admin/search_user")
async def admin_search_user_api(request):
    try:
        data = await request.json()
        admin_id = int(data.get("admin_id"))
        if not await check_is_admin(admin_id):
            return web.json_response({"error": "Admin huquqi talab qilinadi"}, status=403)
        query = str(data.get("query", "")).strip()
    except Exception:
        return web.json_response({"error": "Invalid payload"}, status=400)

    users = await search_users(query)
    return web.json_response({"users": users})

@routes.post("/api/admin/update_balance")
async def admin_update_balance_api(request):
    try:
        data = await request.json()
        admin_id = int(data.get("admin_id"))
        if not await check_is_admin(admin_id):
            return web.json_response({"error": "Admin huquqi talab qilinadi"}, status=403)
        
        target_uid = int(data.get("target_user_id"))
        amount = float(data.get("amount"))
        mode = data.get("mode", "ADD")
    except Exception:
        return web.json_response({"error": "Invalid payload"}, status=400)

    await update_user_balance(target_uid, amount, mode)
    user = await get_user(target_uid)

    bot = request.app["bot"]
    if bot:
        try:
            if mode == "ADD":
                await bot.send_message(target_uid, f"🎁 Admin tomonidan hisobingizga <b>+{amount:,.1f} 🪙</b> qo'shildi!", parse_mode="HTML")
            else:
                await bot.send_message(target_uid, f"⚠️ Admin tomonidan hisobingizdan <b>-{amount:,.1f} 🪙</b> olindi!", parse_mode="HTML")
        except Exception:
            pass

    return web.json_response({"success": True, "user": user, "message": f"Balans muvaffaqiyatli yangilandi!"})

@routes.post("/api/admin/toggle_ban")
async def admin_toggle_ban_api(request):
    try:
        data = await request.json()
        admin_id = int(data.get("admin_id"))
        if not await check_is_admin(admin_id):
            return web.json_response({"error": "Admin huquqi talab qilinadi"}, status=403)
        
        target_uid = int(data.get("target_user_id"))
        is_ban = bool(data.get("is_ban"))
        reason = data.get("reason", "Admin tomonidan bloklandi")
    except Exception:
        return web.json_response({"error": "Invalid payload"}, status=400)

    if is_ban:
        await ban_user(target_uid, reason)
    else:
        await unban_user(target_uid)

    user = await get_user(target_uid)
    bot = request.app["bot"]
    if bot:
        try:
            if is_ban:
                await bot.send_message(target_uid, f"🚫 <b>Siz botdan bloklandingiz!</b>\n📝 Sabab: <i>{reason}</i>", parse_mode="HTML")
            else:
                await bot.send_message(target_uid, "🟢 <b>Profilingiz blokdan chiqarildi!</b>", parse_mode="HTML")
        except Exception:
            pass

    return web.json_response({"success": True, "user": user})

@routes.post("/api/admin/send_message")
async def admin_send_msg_api(request):
    try:
        data = await request.json()
        admin_id = int(data.get("admin_id"))
        if not await check_is_admin(admin_id):
            return web.json_response({"error": "Admin huquqi talab qilinadi"}, status=403)
        
        target_uid = int(data.get("target_user_id"))
        text = str(data.get("text", "")).strip()
    except Exception:
        return web.json_response({"error": "Invalid payload"}, status=400)

    bot = request.app["bot"]
    if not bot or not text:
        return web.json_response({"error": "Matn yoki bot topilmadi"}, status=400)

    try:
        await bot.send_message(target_uid, f"📩 <b>Admin xabari:</b>\n\n{text}", parse_mode="HTML")
        return web.json_response({"success": True, "message": "Xabar muvaffaqiyatli yetkazildi!"})
    except Exception as e:
        return web.json_response({"error": f"Yetkazib bo'lmadi: {e}"}, status=400)

@routes.post("/api/admin/update_settings")
async def admin_update_settings_api(request):
    try:
        data = await request.json()
        admin_id = int(data.get("admin_id"))
        if not await check_is_admin(admin_id):
            return web.json_response({"error": "Admin huquqi talab qilinadi"}, status=403)
        settings = data.get("settings", {})
    except Exception:
        return web.json_response({"error": "Invalid payload"}, status=400)

    for k, v in settings.items():
        await set_setting(k, str(v))

    updated = await get_all_settings()
    return web.json_response({"success": True, "settings": updated, "message": "Sozlamalar saqlandi!"})

@routes.post("/api/admin/channels")
async def admin_channels_api(request):
    try:
        data = await request.json()
        admin_id = int(data.get("admin_id"))
        if not await check_is_admin(admin_id):
            return web.json_response({"error": "Admin huquqi talab qilinadi"}, status=403)
        
        action = data.get("action")
        if action == "add":
            cid = data.get("channel_id")
            title = data.get("channel_title")
            url = data.get("channel_url")
            await add_channel(cid, title, url)
        elif action == "delete":
            cid = data.get("channel_id")
            await delete_channel(cid)
    except Exception:
        return web.json_response({"error": "Invalid payload"}, status=400)

    channels = await get_all_channels()
    return web.json_response({"success": True, "channels": channels})

@routes.post("/api/admin/broadcast")
async def admin_broadcast_api(request):
    try:
        data = await request.json()
        admin_id = int(data.get("admin_id"))
        if not await check_is_admin(admin_id):
            return web.json_response({"error": "Admin huquqi talab qilinadi"}, status=403)
        text = str(data.get("text", "")).strip()
    except Exception:
        return web.json_response({"error": "Invalid payload"}, status=400)

    bot = request.app["bot"]
    if not bot or not text:
        return web.json_response({"error": "Matn kiritilmadi"}, status=400)

    user_ids = await get_all_user_ids()
    sent = 0
    failed = 0

    for uid in user_ids:
        try:
            await bot.send_message(uid, f"📢 <b>E'lon / Xabar:</b>\n\n{text}", parse_mode="HTML")
            sent += 1
            await asyncio.sleep(0.04)
        except Exception:
            failed += 1

    return web.json_response({
        "success": True,
        "sent": sent,
        "failed": failed,
        "total": len(user_ids),
        "message": f"Xabar tarqatildi! ({sent} ta yetkazildi, {failed} ta yetkazilmadi)"
    })

def create_web_app(bot=None):
    app = web.Application()
    app["bot"] = bot
    app.add_routes(routes)
    app.router.add_static("/assets", os.path.join(STATIC_DIR, "assets"))
    app.router.add_static("/static", STATIC_DIR)
    return app
