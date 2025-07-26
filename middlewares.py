from typing import Dict, Any, Awaitable, Callable
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject, User
from config import settings
from database import Database
import asyncio
import time
from datetime import datetime, timedelta

class SecurityMiddleware(BaseMiddleware):
    """میدل‌ویر امنیتی برای بررسی کاربران مسدود و محدودیت نرخ"""
    
    def __init__(self, db: Database):
        self.db = db
        self.rate_limit = {}  # نگهداری آخرین درخواست‌ها
        self.blocked_users = set()  # کش کاربران مسدود
        
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        # استخراج اطلاعات کاربر
        user = None
        if isinstance(event, (Message, CallbackQuery)):
            user = event.from_user
        
        if not user:
            return await handler(event, data)
        
        user_id = user.id
        
        # بررسی حالت تعمیرات (فقط ادمین‌ها دسترسی دارند)
        if settings.MAINTENANCE_MODE and not settings.is_admin(user_id):
            if isinstance(event, Message):
                await event.answer("🔧 ربات در حال تعمیرات است. لطفاً بعداً تلاش کنید.")
            elif isinstance(event, CallbackQuery):
                await event.answer("🔧 ربات در حال تعمیرات است.", show_alert=True)
            return
        
        # بررسی کاربر مسدود (با کش)
        if user_id in self.blocked_users or await self._is_user_blocked(user_id):
            if isinstance(event, Message):
                await event.answer("🚫 دسترسی شما محدود شده است.")
            elif isinstance(event, CallbackQuery):
                await event.answer("🚫 دسترسی شما محدود شده است.", show_alert=True)
            return
        
        # بررسی محدودیت نرخ درخواست
        if not settings.is_admin(user_id) and not await self._check_rate_limit(user_id):
            if isinstance(event, Message):
                await event.answer("⏱️ لطفاً کمی صبر کنید و سپس دوباره تلاش کنید.")
            elif isinstance(event, CallbackQuery):
                await event.answer("⏱️ درخواست‌های بیش از حد!", show_alert=True)
            return
        
        # ثبت فعالیت کاربر
        await self._log_user_activity(user_id, event)
        
        # ادامه پردازش
        return await handler(event, data)
    
    async def _is_user_blocked(self, user_id: int) -> bool:
        """بررسی مسدود بودن کاربر"""
        try:
            user = await self.db.get_user(user_id)
            if user and user.get('is_blocked', False):
                self.blocked_users.add(user_id)
                return True
            else:
                self.blocked_users.discard(user_id)
                return False
        except:
            return False
    
    async def _check_rate_limit(self, user_id: int) -> bool:
        """بررسی محدودیت نرخ درخواست"""
        current_time = time.time()
        
        if user_id not in self.rate_limit:
            self.rate_limit[user_id] = []
        
        # حذف درخواست‌های قدیمی (بیش از 1 دقیقه)
        self.rate_limit[user_id] = [
            req_time for req_time in self.rate_limit[user_id] 
            if current_time - req_time < 60
        ]
        
        # بررسی تعداد درخواست‌ها در دقیقه اخیر
        if len(self.rate_limit[user_id]) >= 30:  # حداکثر 30 درخواست در دقیقه
            return False
        
        # افزودن درخواست جدید
        self.rate_limit[user_id].append(current_time)
        return True
    
    async def _log_user_activity(self, user_id: int, event: TelegramObject):
        """ثبت فعالیت کاربر"""
        try:
            action = "unknown"
            details = ""
            
            if isinstance(event, Message):
                if event.text:
                    if event.text.startswith('/'):
                        action = "command"
                        details = event.text.split()[0]
                    else:
                        action = "message"
                        details = f"text_length:{len(event.text)}"
                elif event.photo:
                    action = "photo_upload"
                elif event.document:
                    action = "document_upload"
                elif event.video:
                    action = "video_upload"
                    
            elif isinstance(event, CallbackQuery):
                action = "callback"
                details = event.data[:50] if event.data else ""
            
            await self.db.log_activity(user_id, action, details)
        except Exception as e:
            print(f"خطا در ثبت فعالیت: {e}")

class AuthMiddleware(BaseMiddleware):
    """میدل‌ویر احراز هویت کاربران"""
    
    def __init__(self, db: Database):
        self.db = db
        
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        # استخراج اطلاعات کاربر
        user = None
        if isinstance(event, (Message, CallbackQuery)):
            user = event.from_user
        
        if not user:
            return await handler(event, data)
        
        user_id = user.id
        
        # بررسی ادمین بودن
        if settings.is_admin(user_id):
            data['is_admin'] = True
            return await handler(event, data)
        
        # دریافت اطلاعات کاربر از دیتابیس
        user_data = await self.db.get_user(user_id)
        
        # بررسی دستورات مجاز برای کاربران غیرثبت‌نام
        if not user_data:
            allowed_commands = ['/start', '/help']
            allowed_callbacks = ['register_', 'cancel_registration']
            
            if isinstance(event, Message):
                if event.text and not any(event.text.startswith(cmd) for cmd in allowed_commands):
                    await event.answer("❌ ابتدا باید ثبت نام کنید. /start را بزنید.")
                    return
            elif isinstance(event, CallbackQuery):
                if event.data and not any(event.data.startswith(cb) for cb in allowed_callbacks):
                    await event.answer("❌ ابتدا باید ثبت نام کنید.", show_alert=True)
                    return
        
        # بررسی وضعیت کاربر
        elif user_data:
            status = user_data.get('status', 'pending')
            
            if status == 'pending':
                # کاربر در انتظار تایید
                allowed_states = ['waiting_approval', 'contact_support']
                if isinstance(event, Message) and event.text not in ['💬 پشتیبانی', '/start']:
                    await event.answer("⏳ حساب شما در انتظار تایید است. برای اطلاعات بیشتر با پشتیبانی تماس بگیرید.")
                    return
                    
            elif status == 'rejected':
                # کاربر رد شده
                await event.answer("❌ حساب شما رد شده است. برای اطلاعات بیشتر با پشتیبانی تماس بگیرید.")
                return
                
            elif status != 'approved':
                # وضعیت نامشخص
                await event.answer("❌ وضعیت حساب شما نامشخص است. با پشتیبانی تماس بگیرید.")
                return
        
        # اضافه کردن اطلاعات کاربر به داده‌ها
        data['user_data'] = user_data
        data['is_admin'] = False
        
        # بروزرسانی آخرین فعالیت
        if user_data:
            await self.db.update_last_activity(user_id)
        
        return await handler(event, data)

class LoggingMiddleware(BaseMiddleware):
    """میدل‌ویر لاگ‌گیری"""
    
    def __init__(self, db: Database):
        self.db = db
        
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        start_time = time.time()
        
        # استخراج اطلاعات برای لاگ
        user_id = None
        action_type = "unknown"
        action_data = ""
        
        if isinstance(event, Message):
            user_id = event.from_user.id
            action_type = "message"
            if event.text:
                action_data = f"text: {event.text[:100]}..."
            elif event.photo:
                action_data = "photo_received"
            elif event.document:
                action_data = f"document: {event.document.file_name}"
            elif event.video:
                action_data = "video_received"
                
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id
            action_type = "callback"
            action_data = event.data[:100] if event.data else ""
        
        try:
            # اجرای handler
            result = await handler(event, data)
            
            # محاسبه زمان پردازش
            process_time = time.time() - start_time
            
            # ثبت لاگ موفق
            if settings.DEBUG and user_id:
                print(f"[{datetime.now()}] User {user_id}: {action_type} - {action_data} ({process_time:.2f}s)")
            
            return result
            
        except Exception as e:
            # ثبت لاگ خطا
            error_msg = str(e)[:200]
            if user_id:
                await self.db.log_activity(user_id, f"error_{action_type}", f"Error: {error_msg}")
            
            print(f"[ERROR] User {user_id}: {action_type} - {error_msg}")
            
            # ارسال پیام خطا به کاربر
            if isinstance(event, Message):
                await event.answer("❌ خطایی رخ داد. لطفاً دوباره تلاش کنید.")
            elif isinstance(event, CallbackQuery):
                await event.answer("❌ خطایی رخ داد.", show_alert=True)
            
            raise

class DatabaseMiddleware(BaseMiddleware):
    """میدل‌ویر اتصال دیتابیس"""
    
    def __init__(self, db: Database):
        self.db = db
        
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        # اضافه کردن دیتابیس به داده‌ها
        data['db'] = self.db
        
        # بررسی اتصال دیتابیس
        if not await self.db.test_connection():
            if isinstance(event, Message):
                await event.answer("❌ خطا در اتصال به دیتابیس. لطفاً بعداً تلاش کنید.")
            elif isinstance(event, CallbackQuery):
                await event.answer("❌ خطا در اتصال به دیتابیس.", show_alert=True)
            return
        
        return await handler(event, data)

class AntiFloodMiddleware(BaseMiddleware):
    """میدل‌ویر ضد اسپم پیشرفته"""
    
    def __init__(self):
        self.user_messages = {}
        self.flood_threshold = 5  # تعداد پیام مجاز
        self.flood_window = 10    # در 10 ثانیه
        self.flood_ban_time = 300 # مدت مسدودیت (5 دقیقه)
        self.flooded_users = {}   # کاربران در حال اسپم
        
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        user = None
        if isinstance(event, (Message, CallbackQuery)):
            user = event.from_user
        
        if not user or settings.is_admin(user.id):
            return await handler(event, data)
        
        user_id = user.id
        current_time = time.time()
        
        # بررسی کاربران مسدود شده به دلیل اسپم
        if user_id in self.flooded_users:
            ban_time = self.flooded_users[user_id]
            if current_time - ban_time < self.flood_ban_time:
                if isinstance(event, Message):
                    await event.answer("🚫 شما به دلیل ارسال پیام‌های مکرر موقتاً مسدود شده‌اید.")
                elif isinstance(event, CallbackQuery):
                    await event.answer("🚫 مسدودیت موقت به دلیل اسپم!", show_alert=True)
                return
            else:
                # حذف مسدودیت
                del self.flooded_users[user_id]
        
        # بررسی تعداد پیام‌ها
        if user_id not in self.user_messages:
            self.user_messages[user_id] = []
        
        # حذف پیام‌های قدیمی
        self.user_messages[user_id] = [
            msg_time for msg_time in self.user_messages[user_id]
            if current_time - msg_time < self.flood_window
        ]
        
        # بررسی سقف پیام
        if len(self.user_messages[user_id]) >= self.flood_threshold:
            # مسدود کردن کاربر
            self.flooded_users[user_id] = current_time
            if isinstance(event, Message):
                await event.answer("🚫 شما به دلیل ارسال پیام‌های مکرر برای 5 دقیقه مسدود شدید.")
            elif isinstance(event, CallbackQuery):
                await event.answer("🚫 مسدودیت به دلیل اسپم!", show_alert=True)
            return
        
        # ثبت پیام جدید
        self.user_messages[user_id].append(current_time)
        
        return await handler(event, data)

class MaintenanceMiddleware(BaseMiddleware):
    """میدل‌ویر حالت تعمیرات"""
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        if not settings.MAINTENANCE_MODE:
            return await handler(event, data)
        
        user = None
        if isinstance(event, (Message, CallbackQuery)):
            user = event.from_user
        
        # ادمین‌ها دسترسی دارند
        if user and settings.is_admin(user.id):
            return await handler(event, data)
        
        # سایر کاربران
        maintenance_msg = "🔧 ربات در حال تعمیرات است.\n⏰ لطفاً بعداً مراجعه کنید."
        
        if isinstance(event, Message):
            await event.answer(maintenance_msg)
        elif isinstance(event, CallbackQuery):
            await event.answer("🔧 حالت تعمیرات فعال است.", show_alert=True)
        
        return

# تابع تنظیم تمام میدل‌ویرها
def setup_middlewares(dp, db: Database):
    """تنظیم تمام میدل‌ویرها"""
    
    # ترتیب میدل‌ویرها مهم است
    dp.middleware.setup(MaintenanceMiddleware())      # اول: بررسی تعمیرات
    dp.middleware.setup(DatabaseMiddleware(db))       # دوم: اتصال دیتابیس  
    dp.middleware.setup(SecurityMiddleware(db))       # سوم: امنیت
    dp.middleware.setup(AntiFloodMiddleware())        # چهارم: ضد اسپم
    dp.middleware.setup(AuthMiddleware(db))           # پنجم: احراز هویت
    dp.middleware.setup(LoggingMiddleware(db))        # آخر: لاگ‌گیری
    
    print("✅ تمام میدل‌ویرها تنظیم شدند")
