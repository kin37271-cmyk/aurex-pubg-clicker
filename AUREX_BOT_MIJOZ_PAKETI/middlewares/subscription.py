# middlewares/subscription.py
from aiogram import Bot
from database import get_all_channels
from config import ADMINS

async def get_unsubscribed_channels(bot: Bot, user_id: int):
    if user_id in ADMINS:
        return []
        
    channels = await get_all_channels()
    if not channels:
        return []

    unsubscribed = []
    for ch in channels:
        try:
            member = await bot.get_chat_member(chat_id=ch["channel_id"], user_id=user_id)
            if member.status in ["left", "kicked"]:
                unsubscribed.append(ch)
        except Exception as e:
            # Agar bot kanalga admin qilinmagan bo'lsa yoki kanal ID noto'g'ri bo'lsa
            continue

    return unsubscribed
