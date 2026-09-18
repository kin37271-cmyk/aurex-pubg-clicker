# config.py
import os

BOT_TOKEN = os.getenv("BOT_TOKEN", "8987574004:AAEcFYWsaj1Yt2-VRnts3IW0kK_ClMMZG4E")

# Asosiy Bosh Ega (Supreme Owner)
OWNER_ID = int(os.getenv("OWNER_ID", "8825408278"))

# Asosiy Admin / Boshqaruvchi ID-lari
ADMINS = [8825408278]

DB_NAME = "clicker_bot.db"

# Web App sozlamalari
WEB_HOST = "0.0.0.0"
WEB_PORT = int(os.getenv("PORT", 8080))
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://aurex-clicker-bot.onrender.com")

# Standart sozlamalar (Oddiy mijozlar uchun)
DEFAULT_MAX_ENERGY = 200             # Boshlang'ich 200 limit
DEFAULT_ENERGY_REGEN_TIME = 3600    # 1 soat (soniyalarda)
DEFAULT_COIN_PER_TAP = 2            # 1 bosishda 2 tanga (tez bosish)
DEFAULT_REFERRAL_BONUS = 50         # Har bir do'st uchun tanga

# Yechib olish standart sozlamalari
DEFAULT_CARD_MIN_WITHDRAW = 10000    # Minimal tanga kartaga yechish uchun (10,000 coin = 5,000 so'm)
DEFAULT_PUBG_MIN_WITHDRAW = 8000     # Minimal tanga PUBG UC uchun (8,000 coin = 33 UC)
DEFAULT_COIN_TO_SUM_RATE = 5000 / 10000  # 10,000 tanga = 5,000 so'm (1 coin = 0.5 so'm)
DEFAULT_COIN_TO_UC_RATE = 60 / 15000     # 15,000 tanga = 60 UC (1 UC = 250 tanga)
