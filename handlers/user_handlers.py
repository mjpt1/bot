from aiogram import Dispatcher, types, F
from aiogram.fsm.context import FSMContext

from config import settings
from database import Database
from utils import handle_cancel, handle_back_to_main, safe_send_message

def setup_user_handlers(dp: Dispatcher, db: Database, bot):
    """راه‌اندازی handlers کاربران عادی"""
    
    @dp.message(F.text == "👤 پروفایل من")
    async def show_user_profile(message: types.Message):
        """نمایش پروفایل کاربر"""
        user = await db.get_user(message.from_user.id)
        if not user:
            await message.answer("شما ثبت نام نشده‌اید. لطفا از دستور /start استفاده کنید.")
            return
        
        if user['status'] != 'approved':
            await message.answer("حساب کاربری شما هنوز تایید نشده است.")
            return
        
        from utils import format_user_profile, get_user_stats
        stats = await get_user_stats(message.from_user.id, db)
        profile_text = format_user_profile(user, stats)
        
        await message.answer(profile_text)
        await db.update_last_activity(message.from_user.id)
    
    @dp.message(F.text == "💬 پشتیبانی")
    async def support_menu(message: types.Message):
        """منوی پشتیبانی"""
        user = await db.get_user(message.from_user.id)
        if not user or user['status'] != 'approved':
            await message.answer("برای استفاده از پشتیبانی، ابتدا باید ثبت نام کرده و تایید شوید.")
            return
        
        from keyboards import Keyboards
        await message.answer(
            "💬 بخش پشتیبانی\n\nچگونه می‌توانیم کمکتان کنیم؟",
            reply_markup=Keyboards.get_support_keyboard()
        )
        await db.update_last_activity(message.from_user.id)
