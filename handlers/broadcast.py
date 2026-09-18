# handlers/broadcast.py
import asyncio
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.exceptions import TelegramRetryAfter, TelegramForbiddenError

from config import ADMINS
from database import get_all_user_ids, is_admin_user, check_admin_permission
from keyboards.admin_kb import admin_back_keyboard

router = Router()

class BroadcastState(StatesGroup):
    waiting_for_content = State()
    confirm_broadcast = State()

async def is_admin(user_id: int) -> bool:
    return await is_admin_user(user_id)

@router.callback_query(F.data == "admin_broadcast")
async def cb_admin_broadcast_start(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if not await is_admin(user_id):
        return
    if not await check_admin_permission(user_id, "can_broadcast"):
        await callback.answer("⚠️ Sizda xabar tarqatish ruxsati yo'q!", show_alert=True)
        return

    await state.set_state(BroadcastState.waiting_for_content)
    text = (
        "📢 <b>XABAR TARQATISH (REKLAMA)</b>\n\n"
        "Barcha foydalanuvchilarga yubormoqchi bo'lgan xabaringizni yuboring.\n\n"
        "<i>Qabul qilinadi: Matn, Rasm, Video, Forward yoki Tugmali postlar.</i>"
    )
    await callback.message.edit_text(text, reply_markup=admin_back_keyboard("admin_main"), parse_mode="HTML")

@router.message(BroadcastState.waiting_for_content)
async def process_broadcast_content(message: Message, state: FSMContext, bot: Bot):
    user_id = message.from_user.id
    if not await is_admin(user_id) or not await check_admin_permission(user_id, "can_broadcast"):
        return
    
    user_ids = await get_all_user_ids()
    total = len(user_ids)
    
    if total == 0:
        await message.answer("Bazada faol foydalanuvchilar yo'q!")
        await state.clear()
        return

    progress_msg = await message.answer(f"⏳ Xabar tarqatish boshlandi...\nJami qabul qiluvchilar: {total} ta")
    
    sent_count = 0
    blocked_count = 0
    failed_count = 0

    for i, uid in enumerate(user_ids, 1):
        try:
            await message.copy_to(chat_id=uid)
            sent_count += 1
        except TelegramForbiddenError:
            blocked_count += 1
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after)
            try:
                await message.copy_to(chat_id=uid)
                sent_count += 1
            except Exception:
                failed_count += 1
        except Exception:
            failed_count += 1

        # Har 25 ta xabardan so'ng progressni yangilash
        if i % 25 == 0 or i == total:
            try:
                await progress_msg.edit_text(
                    f"⏳ <b>Xabar tarqatilmoqda:</b> {i}/{total}\n"
                    f"✅ Yetkazildi: {sent_count}\n"
                    f"🚫 Botni bloklagan: {blocked_count}\n"
                    f"❌ Xatolik: {failed_count}",
                    parse_mode="HTML"
                )
            except Exception:
                pass

        await asyncio.sleep(0.04) # Telegram cheklovlaridan saqlanish

    await state.clear()
    await message.answer(
        f"🎉 <b>Xabar tarqatish yakunlandi!</b>\n\n"
        f"📊 Jami foydalanuvchilar: <b>{total} ta</b>\n"
        f"✅ Muvaffaqiyatli: <b>{sent_count} ta</b>\n"
        f"🚫 Bloklaganlar: <b>{blocked_count} ta</b>\n"
        f"❌ Yetkazilmadi: <b>{failed_count} ta</b>",
        parse_mode="HTML"
    )
