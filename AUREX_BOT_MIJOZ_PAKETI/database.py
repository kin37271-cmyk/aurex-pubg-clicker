# database.py
import aiosqlite
import time
from config import (
    OWNER_ID,
    ADMINS,
    DB_NAME,
    DEFAULT_MAX_ENERGY,
    DEFAULT_ENERGY_REGEN_TIME,
    DEFAULT_COIN_PER_TAP,
    DEFAULT_REFERRAL_BONUS,
    DEFAULT_CARD_MIN_WITHDRAW,
    DEFAULT_PUBG_MIN_WITHDRAW,
    DEFAULT_COIN_TO_SUM_RATE,
    DEFAULT_COIN_TO_UC_RATE
)

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            balance REAL DEFAULT 0,
            total_earned REAL DEFAULT 0,
            energy INTEGER DEFAULT 200,
            max_energy INTEGER DEFAULT 200,
            multitap_level INTEGER DEFAULT 2,
            energy_level INTEGER DEFAULT 1,
            regen_level INTEGER DEFAULT 1,
            autobot_level INTEGER DEFAULT 0,
            last_energy_update INTEGER,
            last_autobot_claim INTEGER,
            referred_by INTEGER DEFAULT NULL,
            referral_count INTEGER DEFAULT 0,
            is_banned INTEGER DEFAULT 0,
            ban_reason TEXT DEFAULT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id TEXT UNIQUE,
            channel_title TEXT,
            channel_url TEXT
        )
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            role TEXT DEFAULT 'admin',
            can_manage_users INTEGER DEFAULT 1,
            can_manage_withdrawals INTEGER DEFAULT 1,
            can_change_settings INTEGER DEFAULT 1,
            can_manage_channels INTEGER DEFAULT 1,
            can_broadcast INTEGER DEFAULT 1,
            can_manage_admins INTEGER DEFAULT 0,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS withdrawals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            type TEXT,
            amount_coins REAL,
            amount_target REAL,
            target_value TEXT,
            target_details TEXT,
            status TEXT DEFAULT 'PENDING',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            resolved_at TIMESTAMP DEFAULT NULL,
            admin_note TEXT DEFAULT NULL
        )
        """)

        # Boshlang'ich sozlamalarni kiritish
        default_settings = {
            "initial_max_energy": str(DEFAULT_MAX_ENERGY),
            "energy_regen_time": str(DEFAULT_ENERGY_REGEN_TIME),
            "coin_per_tap": str(DEFAULT_COIN_PER_TAP),
            "referral_bonus": str(DEFAULT_REFERRAL_BONUS),
            "card_min_withdraw": str(DEFAULT_CARD_MIN_WITHDRAW),
            "pubg_min_withdraw": str(DEFAULT_PUBG_MIN_WITHDRAW),
            "coin_to_sum_rate": str(DEFAULT_COIN_TO_SUM_RATE),
            "coin_to_uc_rate": str(DEFAULT_COIN_TO_UC_RATE),
            "zayafka_channel_id": "",
            "bot_status": "ACTIVE"
        }

        for k, v in default_settings.items():
            await db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))

        # Standart majburiy kanallarni qo'shish
        default_channels = [
            ("@aurexotzifkanali", "Aurex Otziv Kanali", "https://t.me/aurexotzifkanali"),
            ("@Aurex_Pubg", "Aurex PUBG Rasmiy", "https://t.me/Aurex_Pubg")
        ]
        for cid, title, url in default_channels:
            await db.execute("INSERT OR IGNORE INTO channels (channel_id, channel_title, channel_url) VALUES (?, ?, ?)", (cid, title, url))

        # Asosiy Bosh Ega (@Aurex_Ega) - Eng yuqori to'liq vakolat
        await db.execute("""
        INSERT OR REPLACE INTO admins (user_id, username, full_name, role, can_manage_users, can_manage_withdrawals, can_change_settings, can_manage_channels, can_broadcast, can_manage_admins)
        VALUES (8825408278, 'Aurex_Ega', 'Aurex Egasi', 'owner', 1, 1, 1, 1, 1, 1)
        """)

        await db.commit()

async def get_setting(key: str, default=None):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT value FROM settings WHERE key = ?", (key,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else default

async def set_setting(key: str, value: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
        await db.commit()

async def get_all_settings():
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT key, value FROM settings") as cursor:
            rows = await cursor.fetchall()
            return {row[0]: row[1] for row in rows}

# --- FOYDALANUVCHILAR BOSHQARUVI ---

async def get_or_create_user(user_id: int, username: str = None, full_name: str = None, referrer_id: int = None):
    now = int(time.time())
    initial_energy = int(await get_setting("initial_max_energy", DEFAULT_MAX_ENERGY))
    initial_tap = int(await get_setting("coin_per_tap", DEFAULT_COIN_PER_TAP))
    
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                user = dict(row)
                # Username yoki full_name yangilash
                if username != user.get("username") or full_name != user.get("full_name"):
                    await db.execute("UPDATE users SET username = ?, full_name = ? WHERE user_id = ?", (username, full_name, user_id))
                    await db.commit()
                # Energiyani hisoblash
                return await calculate_current_user_energy(user)
            
            # Yangi foydalanuvchi yaratish
            referred_by = None
            if referrer_id and referrer_id != user_id:
                async with db.execute("SELECT user_id FROM users WHERE user_id = ?", (referrer_id,)) as ref_cur:
                    if await ref_cur.fetchone():
                        referred_by = referrer_id

            await db.execute("""
                INSERT INTO users (user_id, username, full_name, balance, total_earned, energy, max_energy, 
                                  multitap_level, energy_level, last_energy_update, last_autobot_claim, referred_by)
                VALUES (?, ?, ?, 0, 0, ?, ?, ?, 1, ?, ?, ?)
            """, (user_id, username, full_name, initial_energy, initial_energy, initial_tap, now, now, referred_by))

            # Refererga bonus berish
            if referred_by:
                ref_bonus = float(await get_setting("referral_bonus", DEFAULT_REFERRAL_BONUS))
                await db.execute("""
                    UPDATE users SET balance = balance + ?, total_earned = total_earned + ?, referral_count = referral_count + 1 
                    WHERE user_id = ?
                """, (ref_bonus, ref_bonus, referred_by))

            await db.commit()
            
            async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
                return dict(await cursor.fetchone())

async def calculate_current_user_energy(user: dict):
    now = int(time.time())
    last_update = user["last_energy_update"] or now
    max_energy = user["max_energy"]
    current_energy = user["energy"]
    regen_level = user.get("regen_level", 1)

    # Standart 1 soat (3600s), har bir regen_level uchun 15% tezroq to'ladi
    regen_time = DEFAULT_ENERGY_REGEN_TIME / (1 + (regen_level - 1) * 0.25)
    
    elapsed = now - last_update
    if elapsed > 0 and current_energy < max_energy:
        # Har sekundda qancha tiklanadi
        added = int(elapsed * (max_energy / regen_time))
        if added > 0:
            current_energy = min(max_energy, current_energy + added)
            async with aiosqlite.connect(DB_NAME) as db:
                await db.execute("UPDATE users SET energy = ?, last_energy_update = ? WHERE user_id = ?", 
                                 (current_energy, now, user["user_id"]))
                await db.commit()
            user["energy"] = current_energy
            user["last_energy_update"] = now

    return user

async def get_user(user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return await calculate_current_user_energy(dict(row))
            return None

async def tap_user(user_id: int):
    user = await get_user(user_id)
    if not user:
        return None, "Foydalanuvchi topilmadi!"
    
    if user["is_banned"]:
        return None, "Siz bloklangansiz!"

    multitap = user["multitap_level"]
    energy_cost = multitap
    coins_earned = multitap

    if user["energy"] < energy_cost:
        return None, "⚡ Energiya yetarli emas! Kuting, quvvat to'lmoqda."

    now = int(time.time())
    new_energy = user["energy"] - energy_cost
    new_balance = user["balance"] + coins_earned
    new_total = user["total_earned"] + coins_earned

    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            UPDATE users 
            SET energy = ?, balance = ?, total_earned = ?, last_energy_update = ?
            WHERE user_id = ?
        """, (new_energy, new_balance, new_total, now, user_id))
        await db.commit()

    user["energy"] = new_energy
    user["balance"] = new_balance
    user["total_earned"] = new_total
    user["last_energy_update"] = now
    return user, f"+{coins_earned} 🪙"

async def claim_autobot(user_id: int):
    user = await get_user(user_id)
    if not user or user["autobot_level"] <= 0:
        return 0, "Sizda Auto-Bot faol emas!"

    now = int(time.time())
    last_claim = user.get("last_autobot_claim") or now
    elapsed_hours = (now - last_claim) / 3600.0

    # Har bir autobot darajasi soatiga 50 coin ishlab beradi (maksimal 8 soat to'planadi)
    capped_hours = min(8.0, elapsed_hours)
    coins_per_hour = user["autobot_level"] * 50
    earned = int(capped_hours * coins_per_hour)

    if earned < 1:
        return 0, "Hozircha yig'ilgan tangalar yo'q. Biroz kuting!"

    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            UPDATE users SET balance = balance + ?, total_earned = total_earned + ?, last_autobot_claim = ?
            WHERE user_id = ?
        """, (earned, earned, now, user_id))
        await db.commit()

    return earned, f"🤖 Auto-Bot sizga {earned} 🪙 yig'ib berdi!"

# Upgrade narxlari va sotib olish
UPGRADE_COSTS = {
    "multitap": lambda lvl: int(50 * (2.2 ** (lvl - 1))),
    "max_energy": lambda lvl: int(40 * (2.0 ** (lvl - 1))),
    "regen": lambda lvl: int(100 * (2.5 ** (lvl - 1))),
    "autobot": lambda lvl: int(300 * (3.0 ** lvl))
}

async def buy_upgrade(user_id: int, upgrade_type: str):
    user = await get_user(user_id)
    if not user:
        return False, "Foydalanuvchi topilmadi!"

    if upgrade_type == "multitap":
        lvl = user["multitap_level"]
        cost = UPGRADE_COSTS["multitap"](lvl)
        if user["balance"] < cost:
            return False, f"Mablag' yetarli emas! Kerak: {cost} 🪙"
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("UPDATE users SET balance = balance - ?, multitap_level = multitap_level + 1 WHERE user_id = ?", (cost, user_id))
            await db.commit()
        return True, f"✅ Multitap darajasi {lvl + 1}-ga ko'tarildi! Endi 1 bosishda {lvl + 1} 🪙 olasiz."

    elif upgrade_type == "max_energy":
        lvl = user["energy_level"]
        cost = UPGRADE_COSTS["max_energy"](lvl)
        if user["balance"] < cost:
            return False, f"Mablag' yetarli emas! Kerak: {cost} 🪙"
        new_max = user["max_energy"] + 100
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("UPDATE users SET balance = balance - ?, energy_level = energy_level + 1, max_energy = ? WHERE user_id = ?", 
                             (cost, new_max, user_id))
            await db.commit()
        return True, f"✅ Maksimal Energiya {new_max}-ga oshirildi!"

    elif upgrade_type == "regen":
        lvl = user["regen_level"]
        cost = UPGRADE_COSTS["regen"](lvl)
        if user["balance"] < cost:
            return False, f"Mablag' yetarli emas! Kerak: {cost} 🪙"
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("UPDATE users SET balance = balance - ?, regen_level = regen_level + 1 WHERE user_id = ?", (cost, user_id))
            await db.commit()
        return True, f"✅ Energiya tiklanish tezligi oshirildi (Daraja {lvl + 1})!"

    elif upgrade_type == "autobot":
        lvl = user["autobot_level"]
        cost = UPGRADE_COSTS["autobot"](lvl)
        if user["balance"] < cost:
            return False, f"Mablag' yetarli emas! Kerak: {cost} 🪙"
        now = int(time.time())
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("UPDATE users SET balance = balance - ?, autobot_level = autobot_level + 1, last_autobot_claim = ? WHERE user_id = ?", 
                             (cost, now, user_id))
            await db.commit()
        return True, f"✅ Auto-Bot darajasi {lvl + 1}-ga ko'tarildi! Soatiga { (lvl + 1) * 50 } 🪙 beradi."

    return False, "Noma'lum yangilanish turi!"

# --- ADMIN USER FUNKSIYALARI ---

async def update_user_balance(user_id: int, amount: float, mode: str = "ADD"):
    async with aiosqlite.connect(DB_NAME) as db:
        if mode == "ADD":
            await db.execute("UPDATE users SET balance = balance + ?, total_earned = total_earned + ? WHERE user_id = ?", 
                             (amount, max(0, amount), user_id))
        elif mode == "SET":
            await db.execute("UPDATE users SET balance = ? WHERE user_id = ?", (amount, user_id))
        elif mode == "SUB":
            await db.execute("UPDATE users SET balance = MAX(0, balance - ?) WHERE user_id = ?", (amount, user_id))
        await db.commit()

async def ban_user(user_id: int, reason: str = "Admin tomonidan bloklandi"):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET is_banned = 1, ban_reason = ? WHERE user_id = ?", (reason, user_id))
        await db.commit()

async def unban_user(user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET is_banned = 0, ban_reason = NULL WHERE user_id = ?", (user_id,))
        await db.commit()

async def search_users(query: str):
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        if query.isdigit():
            async with db.execute("SELECT * FROM users WHERE user_id = ?", (int(query),)) as cursor:
                return [dict(r) for r in await cursor.fetchall()]
        clean_q = query.lstrip("@")
        async with db.execute("SELECT * FROM users WHERE username LIKE ? OR full_name LIKE ? LIMIT 20", 
                             (f"%{clean_q}%", f"%{clean_q}%")) as cursor:
            return [dict(r) for r in await cursor.fetchall()]

async def get_all_user_ids():
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT user_id FROM users WHERE is_banned = 0") as cursor:
            rows = await cursor.fetchall()
            return [r[0] for r in rows]

async def get_statistics():
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT COUNT(*), SUM(balance), SUM(total_earned) FROM users") as cursor:
            total_users, total_balance, total_earned = await cursor.fetchone()
        
        async with db.execute("SELECT COUNT(*) FROM users WHERE is_banned = 1") as cursor:
            banned_users = (await cursor.fetchone())[0]

        async with db.execute("SELECT COUNT(*) FROM withdrawals WHERE status = 'PENDING'") as cursor:
            pending_withdrawals = (await cursor.fetchone())[0]

        async with db.execute("SELECT COUNT(*), SUM(amount_target) FROM withdrawals WHERE status = 'APPROVED' AND type = 'CARD'") as cursor:
            approved_card_count, approved_card_sum = await cursor.fetchone()

        async with db.execute("SELECT COUNT(*), SUM(amount_target) FROM withdrawals WHERE status = 'APPROVED' AND type = 'PUBG'") as cursor:
            approved_pubg_count, approved_pubg_uc = await cursor.fetchone()

        return {
            "total_users": total_users or 0,
            "total_balance": total_balance or 0,
            "total_earned": total_earned or 0,
            "banned_users": banned_users or 0,
            "pending_withdrawals": pending_withdrawals or 0,
            "approved_card_count": approved_card_count or 0,
            "approved_card_sum": approved_card_sum or 0,
            "approved_pubg_count": approved_pubg_count or 0,
            "approved_pubg_uc": approved_pubg_uc or 0,
        }

# --- MAJBURIY KANALLAR ---

async def get_all_channels():
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM channels") as cursor:
            return [dict(r) for r in await cursor.fetchall()]

async def add_channel(channel_id: str, channel_title: str, channel_url: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR REPLACE INTO channels (channel_id, channel_title, channel_url) VALUES (?, ?, ?)",
                         (channel_id, channel_title, channel_url))
        await db.commit()

async def delete_channel(channel_id: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM channels WHERE channel_id = ?", (channel_id,))
        await db.commit()

# --- ZAYAFKALAR (YECHIB OLISH) ---

async def create_withdrawal(user_id: int, w_type: str, amount_coins: float, amount_target: float, target_val: str, target_details: str):
    async with aiosqlite.connect(DB_NAME) as db:
        # Balansdan ayirish
        await db.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (amount_coins, user_id))
        cursor = await db.execute("""
            INSERT INTO withdrawals (user_id, type, amount_coins, amount_target, target_value, target_details, status)
            VALUES (?, ?, ?, ?, ?, ?, 'PENDING')
        """, (user_id, w_type, amount_coins, amount_target, target_val, target_details))
        withdrawal_id = cursor.lastrowid
        await db.commit()
        return withdrawal_id

async def get_withdrawal(w_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM withdrawals WHERE id = ?", (w_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

async def get_pending_withdrawals(limit: int = 10):
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM withdrawals WHERE status = 'PENDING' ORDER BY id DESC LIMIT ?", (limit,)) as cursor:
            return [dict(r) for r in await cursor.fetchall()]

async def resolve_withdrawal(w_id: int, status: str, admin_note: str = None):
    now = time.strftime('%Y-%m-%d %H:%M:%S')
    async with aiosqlite.connect(DB_NAME) as db:
        w = await get_withdrawal(w_id)
        if not w or w["status"] != "PENDING":
            return False, "Zayafka topilmadi yoki allaqachon ko'rib chiqilgan!"

        if status == "REJECTED":
            # Pulni foydalanuvchiga qaytarish
            await db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (w["amount_coins"], w["user_id"]))

        await db.execute("""
            UPDATE withdrawals 
            SET status = ?, resolved_at = ?, admin_note = ? 
            WHERE id = ?
        """, (status, now, admin_note, w_id))
        await db.commit()
        return True, "Zayafka yangilandi!"

# --- ADMINLAR & RUXSATLAR BOSHQARUVI ---

async def is_admin_user(user_id: int) -> bool:
    if not user_id or int(user_id) == 0:
        return False
    if int(user_id) in (OWNER_ID, 8825408278) or int(user_id) in ADMINS:
        return True
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT user_id FROM admins WHERE user_id = ?", (user_id,)) as cursor:
            return bool(await cursor.fetchone())

async def get_admin(user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM admins WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)
            if int(user_id) in (OWNER_ID, 8825408278) or int(user_id) in ADMINS:
                return {
                    "user_id": int(user_id),
                    "username": "Aurex_Ega",
                    "full_name": "Aurex Egasi (Bosh Ega)",
                    "role": "owner",
                    "can_manage_users": 1,
                    "can_manage_withdrawals": 1,
                    "can_change_settings": 1,
                    "can_manage_channels": 1,
                    "can_broadcast": 1,
                    "can_manage_admins": 1
                }
            return None

async def get_all_admins():
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM admins ORDER BY (role = 'owner') DESC, added_at ASC") as cursor:
            return [dict(r) for r in await cursor.fetchall()]

async def add_new_admin(user_id: int, username: str = None, full_name: str = None, role: str = "admin"):
    async with aiosqlite.connect(DB_NAME) as db:
        if not username or not full_name:
            async with db.execute("SELECT username, full_name FROM users WHERE user_id = ?", (user_id,)) as cur:
                u_row = await cur.fetchone()
                if u_row:
                    username = username or u_row[0]
                    full_name = full_name or u_row[1]

        await db.execute("""
            INSERT OR REPLACE INTO admins (user_id, username, full_name, role, can_manage_users, 
                                          can_manage_withdrawals, can_change_settings, can_manage_channels, 
                                          can_broadcast, can_manage_admins)
            VALUES (?, ?, ?, ?, 1, 1, 1, 1, 1, 0)
        """, (user_id, username or "", full_name or f"Admin {user_id}", role))
        await db.commit()
        return True

async def delete_admin(user_id: int):
    if int(user_id) in (OWNER_ID, 8825408278) or int(user_id) in ADMINS:
        return False, "Asosiy Bosh Egani o'chirib bo'lmaydi!"
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM admins WHERE user_id = ?", (user_id,))
        await db.commit()
        return True, "Admin muvaffaqiyatli o'chirildi va adminlik huquqi bekor qilindi!"

async def toggle_admin_permission(user_id: int, permission_name: str):
    valid_perms = [
        "can_manage_users",
        "can_manage_withdrawals",
        "can_change_settings",
        "can_manage_channels",
        "can_broadcast",
        "can_manage_admins"
    ]
    if permission_name not in valid_perms:
        return None
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(f"SELECT {permission_name} FROM admins WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            current_val = row[0]
            new_val = 0 if current_val == 1 else 1
        
        await db.execute(f"UPDATE admins SET {permission_name} = ? WHERE user_id = ?", (new_val, user_id))
        await db.commit()
        return new_val

async def check_admin_permission(user_id: int, permission_name: str) -> bool:
    if int(user_id) in (OWNER_ID, 8825408278) or int(user_id) in ADMINS:
        return True
    admin = await get_admin(user_id)
    if not admin:
        return False
    if admin.get("role") == "owner":
        return True
    return bool(admin.get(permission_name, 0))

async def get_detailed_statistics():
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT COUNT(*), SUM(balance), SUM(total_earned) FROM users") as cursor:
            total_users, total_balance, total_earned = await cursor.fetchone()
        
        async with db.execute("SELECT COUNT(*) FROM users WHERE date(created_at, 'localtime') = date('now', 'localtime')") as cursor:
            row = await cursor.fetchone()
            today_users = row[0] if row else 0

        async with db.execute("SELECT COUNT(*) FROM users WHERE is_banned = 1") as cursor:
            banned_users = (await cursor.fetchone())[0]

        async with db.execute("SELECT COUNT(*) FROM admins") as cursor:
            total_admins = (await cursor.fetchone())[0]

        async with db.execute("SELECT COUNT(*) FROM withdrawals WHERE status = 'PENDING'") as cursor:
            pending_withdrawals = (await cursor.fetchone())[0]

        async with db.execute("SELECT COUNT(*), SUM(amount_target) FROM withdrawals WHERE status = 'APPROVED' AND type = 'CARD'") as cursor:
            approved_card_count, approved_card_sum = await cursor.fetchone()

        async with db.execute("SELECT COUNT(*), SUM(amount_target) FROM withdrawals WHERE status = 'APPROVED' AND type = 'PUBG'") as cursor:
            approved_pubg_count, approved_pubg_uc = await cursor.fetchone()

        return {
            "total_users": total_users or 0,
            "today_users": today_users or 0,
            "total_admins": total_admins or 0,
            "total_balance": total_balance or 0,
            "total_earned": total_earned or 0,
            "banned_users": banned_users or 0,
            "pending_withdrawals": pending_withdrawals or 0,
            "approved_card_count": approved_card_count or 0,
            "approved_card_sum": approved_card_sum or 0,
            "approved_pubg_count": approved_pubg_count or 0,
            "approved_pubg_uc": approved_pubg_uc or 0,
        }
