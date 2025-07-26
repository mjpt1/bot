import os
import asyncio
import hashlib
import re
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
from pathlib import Path
import logging

from aiogram import Bot, types
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.fsm.context import FSMContext

from config import settings

logger = logging.getLogger(__name__)

# ==============================
# ---- مدیریت انصراف -----------
# ==============================

async def handle_cancel(message: types.Message, state: FSMContext) -> bool:
    """مدیریت انصراف در همه state ها"""
    if message.text == "❌ انصراف":
        await state.clear()
        
        # Import داخلی برای جلوگیری از circular import
        from keyboards import Keyboards
        
        if settings.is_admin(message.from_user.id):
            await message.answer("عملیات لغو شد.", reply_markup=Keyboards.get_admin_main_keyboard())
        else:
            await message.answer("عملیات لغو شد.", reply_markup=Keyboards.get_main_keyboard())
        return True
    return False

async def handle_back_to_main(message: types.Message, state: FSMContext) -> bool:
    """مدیریت بازگشت به منوی اصلی"""
    if message.text == "🔙 بازگشت به منوی اصلی":
        await state.clear()
        
        # Import داخلی برای جلوگیری از circular import
        from keyboards import Keyboards
        
        if settings.is_admin(message.from_user.id):
            await message.answer("🔙 بازگشت به منوی اصلی", reply_markup=Keyboards.get_admin_main_keyboard())
        else:
            user = await get_user_from_db(message.from_user.id)
            if user and user['status'] == 'approved':
                await message.answer("🔙 بازگشت به منوی اصلی", reply_markup=Keyboards.get_main_keyboard())
            else:
                await message.answer("لطفا ابتدا ثبت نام کنید.", reply_markup=types.ReplyKeyboardRemove())
        return True
    return False

async def get_user_from_db(user_id: int):
    """دریافت کاربر از دیتابیس - تابع کمکی"""
    try:
        from database import Database
        db = Database()
        return await db.get_user(user_id)
    except:
        return None

# ==============================
# ---- توابع ارسال ایمن --------
# ==============================

async def safe_send_message(chat_id: int, text: str, **kwargs) -> Optional[types.Message]:
    """ارسال ایمن پیام"""
    try:
        from bot import bot
        return await bot.send_message(chat_id, text, **kwargs)
    except TelegramForbiddenError:
        logger.warning(f"کاربر {chat_id} ربات را بلاک کرده است")
        return None
    except TelegramBadRequest as e:
        logger.error(f"خطای Telegram در ارسال پیام به {chat_id}: {e}")
        return None
    except Exception as e:
        logger.error(f"خطای غیرمنتظره در ارسال پیام به {chat_id}: {e}")
        return None

async def safe_edit_message(message: types.Message, text: str, **kwargs) -> Optional[types.Message]:
    """ویرایش ایمن پیام"""
    try:
        return await message.edit_text(text, **kwargs)
    except TelegramBadRequest as e:
        if "message is not modified" in str(e).lower():
            return message
        logger.error(f"خطا در ویرایش پیام: {e}")
        return None
    except Exception as e:
        logger.error(f"خطای غیرمنتظره در ویرایش پیام: {e}")
        return None

async def safe_delete_message(message: types.Message) -> bool:
    """حذف ایمن پیام"""
    try:
        await message.delete()
        return True
    except Exception as e:
        logger.error(f"خطا در حذف پیام: {e}")
        return False

async def safe_send_protected_content(chat_id: int, content: Dict, caption: str = "") -> Optional[types.Message]:
    """ارسال محتوای محافظت شده"""
    try:
        from bot import bot
        
        # تنظیمات حفاظت
        protect_content = True
        
        if content['file_type'] == 'photo':
            if content.get('file_id'):
                return await bot.send_photo(
                    chat_id,
                    content['file_id'],
                    caption=caption,
                    protect_content=protect_content,
                    has_spoiler=False
                )
            else:
                with open(content['file_path'], 'rb') as photo:
                    return await bot.send_photo(
                        chat_id,
                        photo,
                        caption=caption,
                        protect_content=protect_content,
                        has_spoiler=False
                    )
        
        elif content['file_type'] == 'video':
            if content.get('file_id'):
                return await bot.send_video(
                    chat_id,
                    content['file_id'],
                    caption=caption,
                    protect_content=protect_content,
                    has_spoiler=False
                )
            else:
                with open(content['file_path'], 'rb') as video:
                    return await bot.send_video(
                        chat_id,
                        video,
                        caption=caption,
                        protect_content=protect_content,
                        has_spoiler=False
                    )
        
        elif content['file_type'] == 'document':
            if content.get('file_id'):
                return await bot.send_document(
                    chat_id,
                    content['file_id'],
                    caption=caption,
                    protect_content=protect_content
                )
            else:
                with open(content['file_path'], 'rb') as doc:
                    return await bot.send_document(
                        chat_id,
                        doc,
                        caption=caption,
                        protect_content=protect_content
                    )
    
    except Exception as e:
        logger.error(f"خطا در ارسال محتوای محافظت شده: {e}")
        return None

# ==============================
# ---- اعتبارسنجی ورودی --------
# ==============================

def validate_user_input(text: str, input_type: str) -> Dict[str, Any]:
    """اعتبارسنجی ورودی کاربر"""
    
    if not text or not text.strip():
        return {'valid': False, 'message': 'متن نمی‌تواند خالی باشد'}
    
    text = text.strip()
    
    if input_type == 'name':
        if len(text) < 2:
            return {'valid': False, 'message': 'نام باید حداقل 2 کاراکتر باشد'}
        if len(text) > 50:
            return {'valid': False, 'message': 'نام نباید بیش از 50 کاراکتر باشد'}
        if not re.match(r'^[\u0600-\u06FFa-zA-Z\s]+$', text):
            return {'valid': False, 'message': 'نام فقط می‌تواند شامل حروف فارسی و انگلیسی باشد'}
    
    elif input_type == 'nft_code':
        if len(text) < 3:
            return {'valid': False, 'message': 'کد NFT باید حداقل 3 کاراکتر باشد'}
        if len(text) > 100:
            return {'valid': False, 'message': 'کد NFT نباید بیش از 100 کاراکتر باشد'}
    
    elif input_type == 'wallet_address':
        if len(text) < 10:
            return {'valid': False, 'message': 'آدرس ولت باید حداقل 10 کاراکتر باشد'}
        if len(text) > 200:
            return {'valid': False, 'message': 'آدرس ولت نباید بیش از 200 کاراکتر باشد'}
    
    elif input_type == 'support_message':
        if len(text) < 5:
            return {'valid': False, 'message': 'پیام باید حداقل 5 کاراکتر باشد'}
        if len(text) > 1000:
            return {'valid': False, 'message': 'پیام نباید بیش از 1000 کاراکتر باشد'}
    
    elif input_type == 'content_title':
        if len(text) < 3:
            return {'valid': False, 'message': 'عنوان باید حداقل 3 کاراکتر باشد'}
        if len(text) > 200:
            return {'valid': False, 'message': 'عنوان نباید بیش از 200 کاراکتر باشد'}
    
    elif input_type == 'content_description':
        if len(text) > 500:
            return {'valid': False, 'message': 'توضیحات نباید بیش از 500 کاراکتر باشد'}
    
    return {'valid': True, 'message': 'معتبر است'}

def validate_file_upload(file: Any) -> Dict[str, Any]:
    """اعتبارسنجی فایل آپلود شده"""
    
    # بررسی اندازه فایل
    max_size = settings.MAX_FILE_SIZE
    
    if hasattr(file, 'file_size') and file.file_size:
        if file.file_size > max_size:
            return {'valid': False, 'message': f'اندازه فایل نباید بیش از {settings.MAX_FILE_SIZE // (1024*1024)} مگابایت باشد'}
    
    # بررسی نوع فایل
    if hasattr(file, 'mime_type'):
        allowed_types = [
            'image/jpeg', 'image/png', 'image/gif',
            'video/mp4', 'video/mpeg', 'video/quicktime',
            'application/pdf', 'application/msword',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        ]
        
        if file.mime_type not in allowed_types:
            return {'valid': False, 'message': 'نوع فایل پشتیبانی نمی‌شود'}
    
    return {'valid': True, 'message': 'فایل معتبر است'}

# ==============================
# ---- متون و فرمت‌دهی --------
# ==============================

def sanitize_text(text: str) -> str:
    """پاک‌سازی متن از کاراکترهای مخرب"""
    if not text:
        return ""
    
    # حذف کاراکترهای مخرب
    text = re.sub(r'[<>\"\'&]', '', text)
    
    # محدود کردن فاصله‌های متوالی
    text = re.sub(r'\s+', ' ', text)
    
    return text.strip()

def format_user_info(user: Dict) -> str:
    """فرمت‌دهی اطلاعات کاربر"""
    status_emoji = {
        'pending': '⏳',
        'approved': '✅',
        'rejected': '❌',
        'blocked': '🚫'
    }
    
    status_text = {
        'pending': 'در انتظار تایید',
        'approved': 'تایید شده',
        'rejected': 'رد شده',
        'blocked': 'مسدود شده'
    }
    
    emoji = status_emoji.get(user['status'], '❓')
    status = status_text.get(user['status'], 'نامشخص')
    
    return f"""👤 اطلاعات کاربر:

🆔 آیدی: {user['user_id']}
👤 نام: {user['first_name']} {user['last_name']}
🎯 کد NFT: {user.get('nft_code', 'ندارد')}
💳 آدرس ولت: {user.get('wallet_address', 'ندارد')[:30]}...
📅 تاریخ عضویت: {user.get('join_date', 'نامشخص')[:10]}
⏰ آخرین فعالیت: {user.get('last_activity', 'نامشخص')[:10]}
{emoji} وضعیت: {status}
🚫 مسدود: {'بله' if user.get('is_blocked') else 'خیر'}"""

def format_content_info(content: Dict) -> str:
    """فرمت‌دهی اطلاعات محتوا"""
    file_type_emoji = {
        'photo': '🖼️',
        'video': '🎥',
        'document': '📄'
    }
    
    emoji = file_type_emoji.get(content['file_type'], '📎')
    
    return f"""{emoji} اطلاعات محتوا:

🆔 شناسه: {content['id']}
📝 عنوان: {content['title']}
📂 دسته: {content['category']}
📁 زیرمجموعه: {content.get('subcategory', 'ندارد')}
📄 نوع فایل: {content['file_type']}
📅 تاریخ آپلود: {content.get('upload_date', 'نامشخص')[:10]}
📝 توضیحات: {content.get('description', 'ندارد')[:100]}"""

def format_user_profile(user: Dict, stats: Dict = None) -> str:
    """فرمت‌دهی پروفایل کاربر"""
    if not stats:
        stats = {}
        
    return f"""👤 پروفایل شما:

🆔 آیدی: {user['user_id']}
👤 نام: {user['first_name']} {user['last_name']}
🎯 کد NFT: {user.get('nft_code', 'ندارد')}
💳 آدرس ولت: {user.get('wallet_address', 'ندارد')[:20]}...
📅 تاریخ عضویت: {user.get('join_date', 'نامشخص')[:10]}
⏰ آخرین فعالیت: {user.get('last_activity', 'نامشخص')[:10]}

📊 آمار فعالیت:
👁️ تعداد بازدید: {stats.get('views', 0)}
💬 پیام‌های پشتیبانی: {stats.get('support_messages', 0)}
📚 محتوای مشاهده شده: {stats.get('content_viewed', 0)}"""

# ==============================
# ---- مدیریت فایل و پوشه -----
# ==============================

def ensure_directory_exists(directory_path: str):
    """اطمینان از وجود پوشه"""
    try:
        Path(directory_path).mkdir(parents=True, exist_ok=True)
        return True
    except Exception as e:
        logger.error(f"خطا در ایجاد پوشه {directory_path}: {e}")
        return False

def generate_unique_filename(original_name: str, file_type: str) -> str:
    """تولید نام فایل یکتا"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    if original_name and '.' in original_name:
        extension = original_name.split('.')[-1]
    else:
        extension_map = {
            'photo': 'jpg',
            'video': 'mp4',
            'document': 'pdf'
        }
        extension = extension_map.get(file_type, 'bin')
    
    return f"{file_type}_{timestamp}.{extension}"

def clean_old_files(directory: str, days_old: int = 30):
    """پاک‌سازی فایل‌های قدیمی"""
    try:
        cutoff_date = datetime.now() - timedelta(days=days_old)
        
        for file_path in Path(directory).rglob('*'):
            if file_path.is_file():
                file_modified = datetime.fromtimestamp(file_path.stat().st_mtime)
                if file_modified < cutoff_date:
                    file_path.unlink()
                    logger.info(f"فایل قدیمی حذف شد: {file_path}")
        
        return True
    except Exception as e:
        logger.error(f"خطا در پاک‌سازی فایل‌های قدیمی: {e}")
        return False

# ==============================
# ---- آمار و گزارش‌گیری ------
# ==============================

async def get_user_stats(user_id: int, db) -> Dict:
    """دریافت آمار کاربر"""
    try:
        # این تابع باید در database.py پیاده‌سازی شود
        # stats = await db.get_user_statistics(user_id)
        # return stats
        
        # موقتاً مقادیر پیش‌فرض
        return {
            'views': 0,
            'support_messages': 0,
            'content_viewed': 0,
            'last_login': None
        }
    except Exception as e:
        logger.error(f"خطا در دریافت آمار کاربر {user_id}: {e}")
        return {}

async def generate_system_report(db) -> str:
    """تولید گزارش کلی سیستم"""
    try:
        stats = await db.get_statistics()
        
        report = f"""📊 گزارش کلی سیستم
📅 تاریخ: {datetime.now().strftime('%Y-%m-%d %H:%M')}

👥 کاربران:
- کل: {stats.get('total_users', 0)}
- تایید شده: {stats.get('approved_users', 0)}
- در انتظار: {stats.get('pending_users', 0)}
- مسدود شده: {stats.get('blocked_users', 0)}

📚 محتوا:
- تعداد کل: {stats.get('total_content', 0)}

📈 فعالیت:
- فعالیت امروز: {stats.get('today_activities', 0)}
"""
        
        return report
    except Exception as e:
        logger.error(f"خطا در تولید گزارش سیستم: {e}")
        return "❌ خطا در تولید گزارش"

# ==============================
# ---- امنیت و رمزنگاری -------
# ==============================

def hash_password(password: str) -> str:
    """رمزنگاری رمز عبور"""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password: str, hashed: str) -> bool:
    """تایید رمز عبور"""
    return hash_password(password) == hashed

def generate_access_token(user_id: int) -> str:
    """تولید توکن دسترسی"""
    timestamp = str(int(datetime.now().timestamp()))
    data = f"{user_id}_{timestamp}_{settings.BOT_TOKEN[-10:]}"
    return hashlib.md5(data.encode()).hexdigest()

# ==============================
# ---- تسک‌های دوره‌ای ---------
# ==============================

async def cleanup_task():
    """تسک پاک‌سازی دوره‌ای"""
    try:
        # پاک‌سازی فایل‌های قدیمی
        clean_old_files(settings.CONTENT_DIR, 30)
        clean_old_files(f"{settings.LOG_DIR}/temp", 7)
        
        logger.info("✅ تسک پاک‌سازی انجام شد")
        return True
    except Exception as e:
        logger.error(f"❌ خطا در تسک پاک‌سازی: {e}")
        return False

async def backup_task(db):
    """تسک پشتیبان‌گیری دوره‌ای"""
    try:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = f"{settings.BACKUP_DIR}/backup_{timestamp}.db"
        
        # کپی دیتابیس
        import shutil
        shutil.copy2(settings.DATABASE_PATH, backup_path)
        
        logger.info(f"✅ پشتیبان‌گیری انجام شد: {backup_path}")
        return True
    except Exception as e:
        logger.error(f"❌ خطا در پشتیبان‌گیری: {e}")
        return False

# ==============================
# ---- ابزارهای کمکی -----------
# ==============================

def is_valid_telegram_id(user_id: str) -> bool:
    """بررسی معتبر بودن آیدی تلگرام"""
    try:
        uid = int(user_id)
        return 1 <= uid <= 999999999999
    except (ValueError, TypeError):
        return False

def format_file_size(size_bytes: int) -> str:
    """فرمت‌دهی اندازه فایل"""
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB"]
    import math
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    
    return f"{s} {size_names[i]}"

def truncate_text(text: str, max_length: int = 100) -> str:
    """کوتاه کردن متن"""
    if len(text) <= max_length:
        return text
    return text[:max_length-3] + "..."

async def send_notification_to_admins(message: str, bot: Bot):
    """ارسال اطلاع‌رسانی به تمام ادمین‌ها"""
    for admin_id in settings.ADMIN_IDS:
        await safe_send_message(admin_id, message)
