import os
from typing import Optional, List
from pathlib import Path

class Settings:
    def __init__(self):
        # مسیر پروژه (پایه)
        self.base_dir = Path(__file__).parent
        self.env_file = self.base_dir / '.env'
        self._load_env_file()
        self.load_settings()
        if not self.BOT_TOKEN:
            raise ValueError("❌ توکن ربات در فایل .env یافت نشد!")
        self._create_directories()
        self._display_settings()

    def _load_env_file(self):
        """بارگذاری دستی فایل .env"""
        if not self.env_file.exists():
            print(f"⚠️ فایل .env در مسیر {self.env_file} یافت نشد!")
            return
        try:
            with open(self.env_file, 'r', encoding='utf-8-sig') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip()
                        if key not in os.environ:
                            os.environ[key] = value
            print(f"✅ فایل .env از مسیر {self.env_file} بارگذاری شد")
        except Exception as e:
            print(f"❌ خطا در خواندن فایل .env: {e}")

    def load_settings(self):
        # توکن ربات
        self.BOT_TOKEN = os.getenv('BOT_TOKEN', '').strip()
        
        # لیست ادمین‌ها (آیدی عددی)
        admin_ids_str = os.getenv('ADMIN_IDS', '8073439954,23994187')
        self.ADMIN_IDS = self._parse_admin_ids(admin_ids_str)
        
        # مسیرها
        self.DATABASE_PATH = os.path.join(str(self.base_dir), os.getenv('DATABASE_PATH', 'data/bot.db').strip())
        self.CONTENT_DIR = os.path.join(str(self.base_dir), os.getenv('CONTENT_DIR', 'content').strip())
        self.BACKUP_DIR = os.path.join(str(self.base_dir), os.getenv('BACKUP_DIR', 'backups').strip())
        self.LOG_DIR = os.path.join(str(self.base_dir), os.getenv('LOG_DIR', 'logs').strip())
        
        # تنظیمات امنیتی
        self.MAX_LOGIN_ATTEMPTS = int(os.getenv('MAX_LOGIN_ATTEMPTS', '5'))
        self.LOGIN_TIMEOUT_MINUTES = int(os.getenv('LOGIN_TIMEOUT_MINUTES', '10'))
        self.SESSION_TIMEOUT_HOURS = int(os.getenv('SESSION_TIMEOUT_HOURS', '24'))
        
        # تنظیمات ربات
        self.BOT_NAME = os.getenv('BOT_NAME', 'Diamond s.land').strip()
        self.WEBSITE_URL = os.getenv('WEBSITE_URL', 'https://diamond-s-land.com').strip()
        
        # پیام‌ها
        self.WELCOME_MESSAGE = os.getenv('WELCOME_MESSAGE', f'💎 به {self.BOT_NAME} خوش آمدید! 💎\n\nسرزمین آموزش و رشد')
        self.ADMIN_WELCOME = os.getenv('ADMIN_WELCOME', '👋 سلام ادمین گرامی!')
        self.USER_WELCOME = os.getenv('USER_WELCOME', '👋 خوش آمدید!')
        
        # تنظیمات پیشرفته
        self.MAX_CONTENT_SIZE_MB = int(os.getenv('MAX_CONTENT_SIZE_MB', '50'))
        self.ALLOWED_FILE_TYPES = os.getenv('ALLOWED_FILE_TYPES', 'jpg,jpeg,png,mp4,pdf,doc,docx').split(',')
        self.CONTENT_WATERMARK = os.getenv('CONTENT_WATERMARK', f'💎 {self.BOT_NAME}').strip()
        
        # عملکرد
        self.DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'
        self.MAINTENANCE_MODE = os.getenv('MAINTENANCE_MODE', 'False').lower() == 'true'
        self.AUTO_APPROVE_USERS = os.getenv('AUTO_APPROVE_USERS', 'False').lower() == 'true'
        
        # تنظیمات پشتیبانی
        self.SUPPORT_CHAT_ID = os.getenv('SUPPORT_CHAT_ID', '').strip()
        self.NOTIFICATION_ENABLED = os.getenv('NOTIFICATION_ENABLED', 'True').lower() == 'true'

    def _parse_admin_ids(self, admin_ids_str: str) -> List[int]:
        """تبدیل رشته آیدی‌های ادمین به لیست اعداد"""
        admin_ids = []
        if admin_ids_str:
            for admin_id in admin_ids_str.split(','):
                try:
                    admin_ids.append(int(admin_id.strip()))
                except ValueError:
                    print(f"⚠️ آیدی ادمین نامعتبر: {admin_id}")
        return admin_ids if admin_ids else [8073439954, 23994187]

    def _create_directories(self):
        """ایجاد پوشه‌های مورد نیاز"""
        directories = [
            os.path.dirname(self.DATABASE_PATH),
            self.CONTENT_DIR,
            self.BACKUP_DIR,
            self.LOG_DIR,
            os.path.join(self.CONTENT_DIR, 'photos'),
            os.path.join(self.CONTENT_DIR, 'videos'),
            os.path.join(self.CONTENT_DIR, 'documents'),
            os.path.join(self.CONTENT_DIR, 'temp')
        ]
        for directory in directories:
            if directory:
                try:
                    os.makedirs(directory, exist_ok=True)
                except Exception as e:
                    print(f"⚠️ خطا در ایجاد پوشه {directory}: {e}")

    def _display_settings(self):
        """نمایش تنظیمات بارگذاری شده"""
        print("=" * 60)
        print("✅ تنظیمات Diamond s.land بارگذاری شد:")
        print(f"🤖 نام ربات: {self.BOT_NAME}")
        print(f"📱 آیدی‌های ادمین: {self.ADMIN_IDS}")
        print(f"💾 مسیر دیتابیس: {self.DATABASE_PATH}")
        print(f"📁 پوشه محتوا: {self.CONTENT_DIR}")
        print(f"🔒 حداکثر تلاش ورود: {self.MAX_LOGIN_ATTEMPTS}")
        print(f"⏱️ تایم‌اوت ورود: {self.LOGIN_TIMEOUT_MINUTES} دقیقه")
        print(f"📏 حداکثر اندازه فایل: {self.MAX_CONTENT_SIZE_MB} مگابایت")
        print(f"📋 فرمت‌های مجاز: {', '.join(self.ALLOWED_FILE_TYPES)}")
        print(f"🔔 اعلان‌ها: {'فعال' if self.NOTIFICATION_ENABLED else 'غیرفعال'}")
        print(f"🔧 تایید خودکار: {'فعال' if self.AUTO_APPROVE_USERS else 'غیرفعال'}")
        print(f"🐛 حالت دیباگ: {'فعال' if self.DEBUG else 'غیرفعال'}")
        print(f"🔧 حالت تعمیرات: {'فعال' if self.MAINTENANCE_MODE else 'غیرفعال'}")
        print("=" * 60)

    def is_admin(self, user_id: int) -> bool:
        """بررسی ادمین بودن کاربر"""
        return user_id in self.ADMIN_IDS

    def is_file_allowed(self, filename: str) -> bool:
        """بررسی مجاز بودن فرمت فایل"""
        if not filename:
            return False
        file_ext = filename.lower().split('.')[-1]
        return file_ext in [ext.strip().lower() for ext in self.ALLOWED_FILE_TYPES]

    def get_content_watermark(self) -> str:
        """دریافت واترمارک محتوا"""
        return self.CONTENT_WATERMARK

    def get_max_file_size_bytes(self) -> int:
        """دریافت حداکثر اندازه فایل به بایت"""
        return self.MAX_CONTENT_SIZE_MB * 1024 * 1024

    def get_welcome_message(self) -> str:
        """دریافت پیام خوش‌آمدگویی"""
        return self.WELCOME_MESSAGE

    def should_auto_approve(self) -> bool:
        """آیا کاربران به صورت خودکار تایید شوند؟"""
        return self.AUTO_APPROVE_USERS

    def is_maintenance_mode(self) -> bool:
        """آیا ربات در حالت تعمیرات است؟"""
        return self.MAINTENANCE_MODE

    def get_admin_count(self) -> int:
        """تعداد ادمین‌ها"""
        return len(self.ADMIN_IDS)

    def add_admin(self, user_id: int) -> bool:
        """اضافه کردن ادمین جدید"""
        if user_id not in self.ADMIN_IDS:
            self.ADMIN_IDS.append(user_id)
            return True
        return False

    def remove_admin(self, user_id: int) -> bool:
        """حذف ادمین"""
        if user_id in self.ADMIN_IDS and len(self.ADMIN_IDS) > 1:
            self.ADMIN_IDS.remove(user_id)
            return True
        return False

# ایجاد نمونه تنظیمات
settings = Settings()

# تست سلامت تنظیمات
def test_settings():
    """تست سلامت تنظیمات"""
    try:
        print("\n🔍 تست سلامت تنظیمات...")
        
        # تست توکن
        if not settings.BOT_TOKEN:
            raise ValueError("توکن ربات خالی است!")
        print("✅ توکن ربات: موجود")
        
        # تست ادمین‌ها
        if not settings.ADMIN_IDS:
            raise ValueError("هیچ ادمینی تعریف نشده!")
        print(f"✅ ادمین‌ها: {len(settings.ADMIN_IDS)} نفر")
        
        # تست مسیرها
        if not os.path.exists(os.path.dirname(settings.DATABASE_PATH)):
            raise ValueError("مسیر دیتابیس قابل دسترسی نیست!")
        print("✅ مسیر دیتابیس: قابل دسترسی")
        
        if not os.path.exists(settings.CONTENT_DIR):
            raise ValueError("پوشه محتوا قابل دسترسی نیست!")
        print("✅ پوشه محتوا: قابل دسترسی")
        
        print("✅ همه تنظیمات سالم هستند!")
        return True
        
    except Exception as e:
        print(f"❌ مشکل در تنظیمات: {e}")
        return False

# اجرای تست در صورت نیاز
if __name__ == "__main__":
    test_settings()
