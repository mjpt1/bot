import asyncio
from datetime import datetime
from typing import Dict, List

from aiogram import Dispatcher, types, F, Bot
from aiogram.fsm.context import FSMContext

from config import settings
from database import Database
from states import AdminStates, UserStates
from keyboards import Keyboards
from utils import (
    safe_send_message, safe_edit_message, format_user_info,
    format_content_info, validate_user_input, sanitize_text
)

def setup_callback_handlers(dp: Dispatcher, db: Database, bot: Bot):
    """راه‌اندازی callback handlers"""
    
    # ==============================
    # ---- مدیریت کاربران ---------
    # ==============================
    
    @dp.callback_query(F.data.startswith("approve_"))
    async def approve_user(callback: types.CallbackQuery):
        """تایید کاربر توسط ادمین"""
        if not settings.is_admin(callback.from_user.id):
            await callback.answer("دسترسی ندارید!", show_alert=True)
            return
        
        user_id = int(callback.data.split("_")[1])
        
        if await db.update_user_status(user_id, 'approved'):
            await callback.answer("✅ کاربر تایید شد")
            await safe_edit_message(
                callback.message,
                callback.message.text + "\n\n✅ تایید شد",
                reply_markup=None
            )
            
            # اطلاع رسانی به کاربر
            await safe_send_message(
                user_id,
                f"🎉 تبریک! درخواست شما تایید شد.\n\nحالا می‌توانید از تمامی امکانات ربات استفاده کنید.",
                reply_markup=Keyboards.get_main_keyboard()
            )
            
            await db.log_activity(user_id, "approved", f"توسط ادمین {callback.from_user.id}")
        else:
            await callback.answer("❌ خطا در تایید کاربر", show_alert=True)
    
    @dp.callback_query(F.data.startswith("reject_"))
    async def reject_user(callback: types.CallbackQuery):
        """رد کاربر توسط ادمین"""
        if not settings.is_admin(callback.from_user.id):
            await callback.answer("دسترسی ندارید!", show_alert=True)
            return
        
        user_id = int(callback.data.split("_")[1])
        
        if await db.update_user_status(user_id, 'rejected'):
            await callback.answer("❌ کاربر رد شد")
            await safe_edit_message(
                callback.message,
                callback.message.text + "\n\n❌ رد شد",
                reply_markup=None
            )
            
            # اطلاع رسانی به کاربر
            await safe_send_message(
                user_id,
                "❌ متاسفانه درخواست شما رد شد.\n\nبرای اطلاعات بیشتر با پشتیبانی تماس بگیرید."
            )
            
            await db.log_activity(user_id, "rejected", f"توسط ادمین {callback.from_user.id}")
        else:
            await callback.answer("❌ خطا در رد کاربر", show_alert=True)
    
    @dp.callback_query(F.data.startswith("toggle_block_"))
    async def toggle_block_user(callback: types.CallbackQuery):
        """مسدود/رفع مسدودی کاربر"""
        if not settings.is_admin(callback.from_user.id):
            await callback.answer("دسترسی ندارید!", show_alert=True)
            return
        
        user_id = int(callback.data.split("_")[2])
        
        if await db.toggle_block_user(user_id):
            user = await db.get_user(user_id)
            status = "مسدود شد" if user.get('is_blocked') else "رفع مسدودی شد"
            
            await callback.answer(f"✅ کاربر {status}")
            
            # اطلاع رسانی به کاربر
            if user.get('is_blocked'):
                await safe_send_message(user_id, "🚫 حساب شما مسدود شده است.")
            else:
                await safe_send_message(
                    user_id,
                    "✅ مسدودی حساب شما رفع شد.\nحالا می‌توانید از ربات استفاده کنید.",
                    reply_markup=Keyboards.get_main_keyboard()
                )
            
            await db.log_activity(user_id, "block_toggle", f"توسط ادمین {callback.from_user.id}")
        else:
            await callback.answer("❌ خطا در تغییر وضعیت", show_alert=True)
    
    @dp.callback_query(F.data.startswith("view_profile_"))
    async def view_user_profile(callback: types.CallbackQuery):
        """مشاهده پروفایل کاربر"""
        if not settings.is_admin(callback.from_user.id):
            await callback.answer("دسترسی ندارید!", show_alert=True)
            return
        
        user_id = int(callback.data.split("_")[2])
        user = await db.get_user(user_id)
        
        if not user:
            await callback.answer("کاربر یافت نشد!", show_alert=True)
            return
        
        profile_text = format_user_info(user)
        keyboard = Keyboards.get_user_actions_keyboard(user_id)
        
        await safe_edit_message(callback.message, profile_text, reply_markup=keyboard)
        await callback.answer()
    
    # ==============================
    # ---- پنل مدیریت -------------
    # ==============================
    
    @dp.callback_query(F.data == "pending_users")
    async def show_pending_users(callback: types.CallbackQuery):
        """نمایش کاربران در انتظار تایید"""
        if not settings.is_admin(callback.from_user.id):
            await callback.answer("دسترسی ندارید!", show_alert=True)
            return
        
        users = await db.get_pending_users()
        
        if not users:
            await safe_edit_message(
                callback.message,
                "✅ هیچ کاربری در انتظار تایید نیست.",
                reply_markup=Keyboards.get_admin_panel_keyboard()
            )
            await callback.answer()
            return
        
        text = f"👥 کاربران در انتظار تایید ({len(users)} نفر):\n\n"
        
        for i, user in enumerate(users[:10], 1):  # نمایش حداکثر 10 نفر
            text += f"{i}. {user['first_name']} {user['last_name']} (ID: {user['user_id']})\n"
        
        if len(users) > 10:
            text += f"\n... و {len(users) - 10} نفر دیگر"
        
        keyboard = Keyboards.get_user_management_keyboard()
        await safe_edit_message(callback.message, text, reply_markup=keyboard)
        await callback.answer()
    
    @dp.callback_query(F.data == "statistics")
    async def show_statistics(callback: types.CallbackQuery):
        """نمایش آمار کلی"""
        if not settings.is_admin(callback.from_user.id):
            await callback.answer("دسترسی ندارید!", show_alert=True)
            return
        
        stats = await db.get_statistics()
        
        stats_text = f"""📊 آمار کلی سیستم:
📅 تاریخ: {datetime.now().strftime('%Y-%m-%d %H:%M')}

👥 کاربران:
- کل: {stats.get('total_users', 0)}
- تایید شده: {stats.get('approved_users', 0)}
- در انتظار: {stats.get('pending_users', 0)}
- رد شده: {stats.get('rejected_users', 0)}
- مسدود شده: {stats.get('blocked_users', 0)}

📚 محتوا:
- تعداد کل: {stats.get('total_content', 0)}

📈 فعالیت:
- فعالیت امروز: {stats.get('today_activities', 0)}"""
        
        await safe_edit_message(
            callback.message,
            stats_text,
            reply_markup=Keyboards.get_stats_keyboard()
        )
        await callback.answer()
    
    @dp.callback_query(F.data == "users_list")
    async def show_users_list(callback: types.CallbackQuery):
        """نمایش لیست کاربران"""
        if not settings.is_admin(callback.from_user.id):
            await callback.answer("دسترسی ندارید!", show_alert=True)
            return
        
        users = await db.get_all_users(limit=20)
        
        if not users:
            await safe_edit_message(
                callback.message,
                "📭 هیچ کاربری یافت نشد.",
                reply_markup=Keyboards.get_admin_panel_keyboard()
            )
            await callback.answer()
            return
        
        text = f"👥 لیست کاربران ({len(users)} نفر):\n\n"
        
        for user in users:
            status_emoji = {'pending': '⏳', 'approved': '✅', 'rejected': '❌'}.get(user['status'], '❓')
            text += f"{status_emoji} {user['first_name']} {user['last_name']} (ID: {user['user_id']})\n"
        
        keyboard = Keyboards.get_user_management_keyboard()
        await safe_edit_message(callback.message, text, reply_markup=keyboard)
        await callback.answer()
    
    # ==============================
    # ---- مدیریت محتوا -----------
    # ==============================
    
    @dp.callback_query(F.data == "add_content")
    async def start_add_content(callback: types.CallbackQuery, state: FSMContext):
        """شروع فرآیند افزودن محتوا"""
        if not settings.is_admin(callback.from_user.id):
            await callback.answer("دسترسی ندارید!", show_alert=True)
            return
        
        await safe_edit_message(
            callback.message,
            "📎 لطفا فایل محتوای جدید را ارسال کنید:\n\n"
            "فرمت‌های پشتیبانی شده:\n"
            "• 🖼️ عکس (JPG, PNG)\n"
            "• 🎥 ویدیو (MP4, MOV)\n"
            "• 📄 سند (PDF, DOC, DOCX)",
            reply_markup=None
        )
        
        await state.set_state(AdminStates.waiting_for_content_file)
        await callback.answer()
    
    @dp.callback_query(F.data.startswith("cat_"))
    async def select_category(callback: types.CallbackQuery, state: FSMContext):
        """انتخاب دسته‌بندی برای محتوا"""
        if not settings.is_admin(callback.from_user.id):
            await callback.answer("دسترسی ندارید!", show_alert=True)
            return
        
        category = callback.data.replace("cat_", "")
        await state.update_data(category=category)
        
        # دریافت زیرمجموعه‌ها
        subcategories = await db.get_subcategories(category)
        
        if subcategories:
            keyboard = []
            for sub in subcategories:
                keyboard.append([types.InlineKeyboardButton(
                    text=f"📁 {sub['name']}", 
                    callback_data=f"subcat_{sub['id']}"
                )])
            
            keyboard.append([types.InlineKeyboardButton(
                text="➕ زیرمجموعه جدید", 
                callback_data="new_subcategory"
            )])
            keyboard.append([types.InlineKeyboardButton(
                text="📄 بدون زیرمجموعه", 
                callback_data="no_subcategory"
            )])
            
            reply_markup = types.InlineKeyboardMarkup(inline_keyboard=keyboard)
            
            await safe_edit_message(
                callback.message,
                f"📂 دسته {category} انتخاب شد.\n\nزیرمجموعه را انتخاب کنید:",
                reply_markup=reply_markup
            )
        else:
            await safe_edit_message(
                callback.message,
                "📝 عنوان محتوا را وارد کنید:",
                reply_markup=None
            )
            await state.set_state(AdminStates.waiting_for_title)
        
        await callback.answer()
    
    @dp.callback_query(F.data.startswith("subcat_"))
    async def select_subcategory(callback: types.CallbackQuery, state: FSMContext):
        """انتخاب زیرمجموعه"""
        if not settings.is_admin(callback.from_user.id):
            return
        
        subcategory_id = int(callback.data.split("_")[1])
        await state.update_data(subcategory_id=subcategory_id)
        
        await safe_edit_message(
            callback.message,
            "📝 عنوان محتوا را وارد کنید:",
            reply_markup=None
        )
        await state.set_state(AdminStates.waiting_for_title)
        await callback.answer()
    
    @dp.callback_query(F.data == "no_subcategory")
    async def no_subcategory(callback: types.CallbackQuery, state: FSMContext):
        """انتخاب بدون زیرمجموعه"""
        if not settings.is_admin(callback.from_user.id):
            return
        
        await state.update_data(subcategory_id=None)
        
        await safe_edit_message(
            callback.message,
            "📝 عنوان محتوا را وارد کنید:",
            reply_markup=None
        )
        await state.set_state(AdminStates.waiting_for_title)
        await callback.answer()
    
    # ==============================
    # ---- کاربران عادی -----------
    # ==============================
    
    @dp.callback_query(F.data == "new_support_message")
    async def new_support_message(callback: types.CallbackQuery, state: FSMContext):
        """شروع ارسال پیام پشتیبانی"""
        user = await db.get_user(callback.from_user.id)
        if not user or user['status'] != 'approved':
            await callback.answer("دسترسی شما محدود است!", show_alert=True)
            return
        
        await safe_edit_message(
            callback.message,
            "💬 لطفا پیام خود را برای پشتیبانی ارسال کنید:",
            reply_markup=None
        )
        
        await state.set_state(UserStates.waiting_for_support_message)
        await callback.answer()
    
    @dp.callback_query(F.data == "my_support_messages")
    async def show_user_support_messages(callback: types.CallbackQuery):
        """نمایش پیام‌های پشتیبانی کاربر"""
        user = await db.get_user(callback.from_user.id)
        if not user or user['status'] != 'approved':
            await callback.answer("دسترسی شما محدود است!", show_alert=True)
            return
        
        # این تابع باید در database.py پیاده‌سازی شود
        # messages = await db.get_user_support_messages(callback.from_user.id)
        messages = []  # موقتاً خالی
        
        if not messages:
            text = "📭 شما هیچ پیام پشتیبانی ارسال نکرده‌اید."
        else:
            text = f"💬 پیام‌های شما ({len(messages)} پیام):\n\n"
            for msg in messages[:5]:  # نمایش 5 پیام آخر
                status = "✅ خوانده شده" if msg.get('is_read') else "⏳ در انتظار"
                text += f"📅 {msg.get('created_at', '')[:10]}\n{status}\n\n"
        
        await safe_edit_message(
            callback.message,
            text,
            reply_markup=Keyboards.get_support_keyboard()
        )
        await callback.answer()
    
    # ==============================
    # ---- عملیات عمومی -----------
    # ==============================
    
    @dp.callback_query(F.data == "admin_back")
    async def admin_back(callback: types.CallbackQuery):
        """بازگشت به پنل ادمین"""
        if not settings.is_admin(callback.from_user.id):
            return
        
        await safe_edit_message(
            callback.message,
            "🔧 پنل مدیریت ربات\n\nاز گزینه‌های زیر استفاده کنید:",
            reply_markup=Keyboards.get_admin_panel_keyboard()
        )
        await callback.answer()
    
    @dp.callback_query(F.data == "back_to_main")
    async def back_to_main(callback: types.CallbackQuery):
        """بازگشت به منوی اصلی"""
        await callback.message.delete()
        
        if settings.is_admin(callback.from_user.id):
            await safe_send_message(
                callback.from_user.id,
                "🔙 بازگشت به منوی اصلی",
                reply_markup=Keyboards.get_admin_main_keyboard()
            )
        else:
            user = await db.get_user(callback.from_user.id)
            if user and user['status'] == 'approved':
                await safe_send_message(
                    callback.from_user.id,
                    "🔙 بازگشت به منوی اصلی",
                    reply_markup=Keyboards.get_main_keyboard()
                )
        
        await callback.answer()
    
    @dp.callback_query(F.data == "cancel_operation")
    async def cancel_operation(callback: types.CallbackQuery, state: FSMContext):
        """لغو عملیات"""
        await state.clear()
        
        if settings.is_admin(callback.from_user.id):
            await safe_edit_message(
                callback.message,
                "عملیات لغو شد.",
                reply_markup=Keyboards.get_admin_panel_keyboard()
            )
        else:
            await callback.message.delete()
            await safe_send_message(
                callback.from_user.id,
                "عملیات لغو شد.",
                reply_markup=Keyboards.get_main_keyboard()
            )
        
        await callback.answer()
    
    @dp.callback_query(F.data == "refresh_panel")
    async def refresh_panel(callback: types.CallbackQuery):
        """بروزرسانی پنل"""
        if not settings.is_admin(callback.from_user.id):
            return
        
        await safe_edit_message(
            callback.message,
            f"🔧 پنل مدیریت ربات\n\n🔄 آخرین بروزرسانی: {datetime.now().strftime('%H:%M:%S')}\n\nاز گزینه‌های زیر استفاده کنید:",
            reply_markup=Keyboards.get_admin_panel_keyboard()
        )
        await callback.answer("🔄 پنل بروزرسانی شد")
