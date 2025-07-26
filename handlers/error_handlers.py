import logging
import traceback
from datetime import datetime

from aiogram import Dispatcher, Bot
from aiogram.types import ErrorEvent, Update
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from config import settings
from database import Database
from utils import safe_send_message

logger = logging.getLogger(__name__)

def setup_error_handlers(dp: Dispatcher, db: Database, bot: Bot):
    """راه‌اندازی error handlers"""
    
    @dp.error()
    async def error_handler(event: ErrorEvent, db: Database = db):
        """هندلر کلی خطاها"""
        
        try:
            # ثبت خطا در لاگ
            logger.error(f"خطا در بات: {event.exception}")
            logger.error(f"Update: {event.update}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            
            # ثبت خطا در دیتابیس
            await log_error_to_database(event, db)
            
            # ارسال اطلاع رسانی به ادمین‌ها
            await notify_admins_about_error(event, bot)
            
            # مدیریت خطاهای خاص
            if isinstance(event.exception, TelegramForbiddenError):
                await handle_forbidden_error(event, db)
            elif isinstance(event.exception, TelegramBadRequest):
                await handle_bad_request_error(event, db)
            else:
                await handle_general_error(event, db, bot)
                
        except Exception as e:
            logger.critical(f"خطای حین مدیریت خطا: {e}")
    
    async def log_error_to_database(event: ErrorEvent, db: Database):
        """ثبت خطا در دیتابیس"""
        try:
            user_id = None
            if event.update.message:
                user_id = event.update.message.from_user.id
            elif event.update.callback_query:
                user_id = event.update.callback_query.from_user.id
            
            error_details = {
                'error_type': type(event.exception).__name__,
                'error_message': str(event.exception),
                'traceback': traceback.format_exc(),
                'update_data': str(event.update)
            }
            
            if user_id:
                await db.log_activity(
                    user_id, 
                    "error", 
                    f"خطا: {error_details['error_type']}"
                )
        except Exception as e:
            logger.error(f"خطا در ثبت خطا در دیتابیس: {e}")
    
    async def notify_admins_about_error(event: ErrorEvent, bot: Bot):
        """اطلاع رسانی خطا به ادمین‌ها"""
        try:
            if not settings.DEBUG:  # فقط در حالت عادی
                return
            
            error_message = f"""🚨 خطای بات:

📅 زمان: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
❌ نوع خطا: {type(event.exception).__name__}
💬 پیام خطا: {str(event.exception)[:200]}

👤 کاربر: {event.update.message.from_user.id if event.update.message else 'نامشخص'}
"""
            
            for admin_id in settings.ADMIN_IDS:
                await safe_send_message(admin_id, error_message)
                
        except Exception as e:
            logger.error(f"خطا در اطلاع رسانی به ادمین‌ها: {e}")
    
    async def handle_forbidden_error(event: ErrorEvent, db: Database):
        """مدیریت خطای Forbidden (کاربر بلاک کرده)"""
        try:
            user_id = None
            if event.update.message:
                user_id = event.update.message.from_user.id
            elif event.update.callback_query:
                user_id = event.update.callback_query.from_user.id
            
            if user_id:
                logger.info(f"کاربر {user_id} ربات را بلاک کرده است")
                await db.log_activity(user_id, "blocked_bot", "کاربر ربات را بلاک کرد")
                
        except Exception as e:
            logger.error(f"خطا در مدیریت Forbidden Error: {e}")
    
    async def handle_bad_request_error(event: ErrorEvent, db: Database):
        """مدیریت خطای Bad Request"""
        try:
            error_message = str(event.exception).lower()
            
            if "message is not modified" in error_message:
                # پیام تغییری نکرده - نیازی به اقدام نیست
                pass
            elif "message to edit not found" in error_message:
                # پیام برای ویرایش یافت نشد
                logger.warning("پیام برای ویرایش یافت نشد")
            elif "message can't be deleted" in error_message:
                # پیام قابل حذف نیست
                logger.warning("پیام قابل حذف نیست")
            else:
                logger.error(f"Bad Request خطای ناشناخته: {event.exception}")
                
        except Exception as e:
            logger.error(f"خطا در مدیریت Bad Request Error: {e}")
    
    async def handle_general_error(event: ErrorEvent, db: Database, bot: Bot):
        """مدیریت خطاهای عمومی"""
        try:
            # ارسال پیام خطا به کاربر (در صورت امکان)
            user_id = None
            if event.update.message:
                user_id = event.update.message.from_user.id
            elif event.update.callback_query:
                user_id = event.update.callback_query.from_user.id
            
            if user_id:
                error_message = "❌ خطایی رخ داده است. لطفا دوباره تلاش کنید."
                if settings.DEBUG:
                    error_message += f"\n\nجزئیات خطا: {str(event.exception)[:100]}"
                
                await safe_send_message(user_id, error_message)
                
        except Exception as e:
            logger.error(f"خطا در مدیریت خطای عمومی: {e}")

    # ثبت error handlers
    dp.error.register(error_handler)
