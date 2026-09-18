# main.py
import asyncio
import logging
import aiohttp
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
import os
import time
from datetime import datetime
from aiogram.types import MenuButtonWebApp, WebAppInfo, FSInputFile

import config
from database import init_db
from middlewares.ban_check import BanCheckMiddleware
from web_server import create_web_app
# Handlerlarni import qilish
from handlers.start import router as start_router
from handlers.clicker import router as clicker_router
from handlers.shop import router as shop_router
from handlers.withdraw import router as withdraw_router
from handlers.admin import router as admin_router
from handlers.broadcast import router as broadcast_router

# Logging sozlamalari
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(name)s - %(message)s"
)
logger = logging.getLogger(__name__)

async def self_ping_keep_alive():
    """Bot serverini 24/7 uyg'oq ushlab turish uchun har 5 daqiqada o'ziga so'rov yuboruvchi avto-pinger"""
    await asyncio.sleep(60)
    logger.info("⚡️ 24/7 Avto-Uyg'otuvchi (Keep-Alive Pinger) xizmati ishga tushdi.")
    while True:
        try:
            url = config.WEBAPP_URL
            if url and url.startswith("https://"):
                health_url = f"{url.rstrip('/')}/health"
                async with aiohttp.ClientSession() as session:
                    async with session.get(health_url, timeout=15) as resp:
                        if resp.status == 200:
                            logger.info(f"⚡️ [24/7 Auto-Ping]: Server muvaffaqiyatli uyg'otildi ({resp.status})")
                        else:
                            logger.warning(f"⚠️ [24/7 Auto-Ping]: Status {resp.status}")
        except Exception as e:
            logger.debug(f"Auto-ping xatolik: {e}")

        await asyncio.sleep(300) # Har 5 daqiqada (300 soniya)

async def start_web_server(bot: Bot):
    app = create_web_app(bot)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, config.WEB_HOST, config.WEB_PORT)
    await site.start()
    logger.info(f"Web Server ishga tushdi: http://{config.WEB_HOST}:{config.WEB_PORT}")
    return runner

async def on_startup(bot: Bot):
    await init_db()
    logger.info("Ma'lumotlar bazasi ishga tushirildi.")
    
    # Telegram Bot Menu Button-ni WebApp qilib sozlash
    if config.WEBAPP_URL and config.WEBAPP_URL.startswith("https://"):
        try:
            await bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(
                    text="🔥 O'YNASH",
                    web_app=WebAppInfo(url=config.WEBAPP_URL)
                )
            )
            logger.info(f"Telegram Bot Menu Button (Web App) sozlandi: {config.WEBAPP_URL}")
        except Exception as e:
            logger.error(f"Menu button sozlashda xato: {e}")

    bot_info = await bot.get_me()
    logger.info(f"Bot muvaffaqiyatli ishga tushdi: @{bot_info.username}")
    
    # 24/7 Uyg'otuvchi (Keep-Alive) vazifasini ishga tushirish (Telegramga hech narsa yozmaydi)
    asyncio.create_task(self_ping_keep_alive())

async def main():
    while True:
        try:
            bot = Bot(
                token=config.BOT_TOKEN,
                default=DefaultBotProperties(parse_mode=ParseMode.HTML)
            )
            dp = Dispatcher(storage=MemoryStorage())

            # Middleware-larni ulash
            dp.message.middleware(BanCheckMiddleware())
            dp.callback_query.middleware(BanCheckMiddleware())

            # Routerlarni ro'yxatdan o'tkazish
            dp.include_router(admin_router)
            dp.include_router(broadcast_router)
            dp.include_router(start_router)
            dp.include_router(clicker_router)
            dp.include_router(shop_router)
            dp.include_router(withdraw_router)

            # Web Serverni ishga tushirish
            runner = await start_web_server(bot)
            
            # Startup event
            await on_startup(bot)

            try:
                # Eski kutilmagan xabarlarni tozalash va bot pollingni boshlash
                await bot.delete_webhook(drop_pending_updates=True)
                await dp.start_polling(bot, handle_signals=False)
            finally:
                await runner.cleanup()
        except (KeyboardInterrupt, SystemExit):
            logger.info("Bot to'xtatildi.")
            break
        except Exception as e:
            logger.error(f"Xatolik: {e}. 3 soniyada qayta urinilmoqda...")
            await asyncio.sleep(3)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Dastur yakunlandi.")
