import hashlib
import hmac
import secrets
import time
import re
import base64
from typing import Optional, Dict, List, Tuple
from datetime import datetime, timedelta
import json
import asyncio

class Security:
    """
    کلاس مدیریت امنیت و رمزنگاری پیشرفته برای ربات
    """

    def __init__(self, db=None):
        self.db = db
        self.failed_attempts = {}  # ذخیره تلاش‌های ناموفق
        self.blocked_users = {}    # کاربران مسدود شده موقت
        self.session_tokens = {}   # توکن‌های جلسه
        self.secret_key = self._generate_secret_key()

    def _generate_secret_key(self) -> str:
        """تولید کلید مخفی برای امضای جلسات"""
        return secrets.token_hex(32)

    # ==================== مدیریت رمزهای عبور ====================

    def hash_password(self, password: str, salt: Optional[str] = None) -> Tuple[str, str]:
        """
        هش کردن رمز عبور با salt برای امنیت بیشتر
        """
        if salt is None:
            salt = secrets.token_hex(16)
        
        # ترکیب رمز و salt
        password_salt = password + salt
        
        # هش با SHA-256
        hashed = hashlib.sha256(password_salt.encode('utf-8')).hexdigest()
        
        return hashed, salt

    def check_password(self, raw_password: str, hashed_password: str, salt: str = None) -> bool:
        """
        مقایسه رمز وارد شده با هش ذخیره شده
        """
        if salt:
            # روش جدید با salt
            test_hash, _ = self.hash_password(raw_password, salt)
            return hmac.compare_digest(test_hash, hashed_password)
        else:
            # روش قدیمی برای سازگاری
            old_hash = hashlib.sha256(raw_password.encode()).hexdigest()
            return hmac.compare_digest(old_hash, hashed_password)

    def is_strong_password(self, password: str) -> Tuple[bool, List[str]]:
        """
        بررسی دقیق قدرت رمز عبور
        """
        issues = []
        
        # طول رمز
        if len(password) < 8:
            issues.append("رمز باید حداقل 8 کاراکتر باشد")
        
        # وجود حروف کوچک
        if not re.search(r'[a-z]', password):
            issues.append("رمز باید شامل حروف کوچک انگلیسی باشد")
        
        # وجود حروف بزرگ
        if not re.search(r'[A-Z]', password):
            issues.append("رمز باید شامل حروف بزرگ انگلیسی باشد")
        
        # وجود عدد
        if not re.search(r'\d', password):
            issues.append("رمز باید شامل حداقل یک عدد باشد")
        
        # وجود کاراکتر خاص
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            issues.append("رمز باید شامل حداقل یک کاراکتر خاص باشد")
        
        # بررسی رمزهای رایج
        common_passwords = [
            "12345678", "password", "123456789", "qwerty", 
            "abc123", "password123", "admin", "user"
        ]
        if password.lower() in common_passwords:
            issues.append("رمز انتخابی بسیار رایج است")
        
        return len(issues) == 0, issues

    def generate_secure_password(self, length: int = 12) -> str:
        """
        تولید رمز عبور امن
        """
        lowercase = "abcdefghijklmnopqrstuvwxyz"
        uppercase = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        digits = "0123456789"
        special = "!@#$%^&*"
        
        # حداقل یکی از هر نوع
        password = [
            secrets.choice(lowercase),
            secrets.choice(uppercase),
            secrets.choice(digits),
            secrets.choice(special)
        ]
        
        # بقیه کاراکترها
        all_chars = lowercase + uppercase + digits + special
        for _ in range(length - 4):
            password.append(secrets.choice(all_chars))
        
        # مخلوط کردن
        secrets.SystemRandom().shuffle(password)
        
        return ''.join(password)

    # ==================== مدیریت تلاش‌های ورود ====================

    def record_failed_attempt(self, user_id: int, ip: str = None) -> bool:
        """
        ثبت تلاش ناموفق ورود
        """
        current_time = time.time()
        key = f"{user_id}_{ip}" if ip else str(user_id)
        
        if key not in self.failed_attempts:
            self.failed_attempts[key] = []
        
        # حذف تلاش‌های قدیمی (بیش از 1 ساعت)
        self.failed_attempts[key] = [
            attempt_time for attempt_time in self.failed_attempts[key]
            if current_time - attempt_time < 3600
        ]
        
        # اضافه کردن تلاش جدید
        self.failed_attempts[key].append(current_time)
        
        # بررسی مسدود شدن
        if len(self.failed_attempts[key]) >= 5:
            self.block_user_temporarily(user_id, 10)  # 10 دقیقه
            return True
        
        return False

    def clear_failed_attempts(self, user_id: int, ip: str = None):
        """
        پاک کردن تلاش‌های ناموفق پس از ورود موفق
        """
        key = f"{user_id}_{ip}" if ip else str(user_id)
        if key in self.failed_attempts:
            del self.failed_attempts[key]

    def block_user_temporarily(self, user_id: int, minutes: int = 10):
        """
        مسدود کردن موقت کاربر
        """
        block_until = time.time() + (minutes * 60)
        self.blocked_users[user_id] = {
            'blocked_until': block_until,
            'reason': 'تلاش‌های ناموفق زیاد',
            'blocked_at': datetime.now().isoformat()
        }

    def is_user_blocked(self, user_id: int) -> Tuple[bool, Optional[int]]:
        """
        بررسی مسدود بودن کاربر
        """
        if user_id not in self.blocked_users:
            return False, None
        
        block_info = self.blocked_users[user_id]
        current_time = time.time()
        
        if current_time >= block_info['blocked_until']:
            # مدت مسدودی تمام شده
            del self.blocked_users[user_id]
            return False, None
        
        # محاسبه زمان باقی‌مانده
        remaining_seconds = int(block_info['blocked_until'] - current_time)
        return True, remaining_seconds

    # ==================== مدیریت جلسات ====================

    def create_session_token(self, user_id: int, expires_hours: int = 24) -> str:
        """
        ایجاد توکن جلسه امن
        """
        # داده‌های توکن
        token_data = {
            'user_id': user_id,
            'created_at': time.time(),
            'expires_at': time.time() + (expires_hours * 3600),
            'random': secrets.token_hex(16)
        }
        
        # تبدیل به JSON و رمزگذاری
        json_data = json.dumps(token_data)
        encoded_data = base64.b64encode(json_data.encode()).decode()
        
        # امضای دیجیتال
        signature = hmac.new(
            self.secret_key.encode(),
            encoded_data.encode(),
            hashlib.sha256
        ).hexdigest()
        
        # توکن نهایی
        token = f"{encoded_data}.{signature}"
        
        # ذخیره در حافظه
        self.session_tokens[token] = token_data
        
        return token

    def verify_session_token(self, token: str) -> Tuple[bool, Optional[int]]:
        """
        تأیید معتبر بودن توکن جلسه
        """
        try:
            # جداسازی داده و امضا
            encoded_data, signature = token.split('.')
            
            # بررسی امضا
            expected_signature = hmac.new(
                self.secret_key.encode(),
                encoded_data.encode(),
                hashlib.sha256
            ).hexdigest()
            
            if not hmac.compare_digest(signature, expected_signature):
                return False, None
            
            # رمزگشایی داده‌ها
            json_data = base64.b64decode(encoded_data).decode()
            token_data = json.loads(json_data)
            
            # بررسی انقضا
            if time.time() > token_data['expires_at']:
                # حذف توکن منقضی
                if token in self.session_tokens:
                    del self.session_tokens[token]
                return False, None
            
            return True, token_data['user_id']
            
        except Exception:
            return False, None

    def revoke_session_token(self, token: str):
        """
        لغو توکن جلسه
        """
        if token in self.session_tokens:
            del self.session_tokens[token]

    def cleanup_expired_sessions(self):
        """
        پاکسازی جلسات منقضی
        """
        current_time = time.time()
        expired_tokens = []
        
        for token, data in self.session_tokens.items():
            if current_time > data['expires_at']:
                expired_tokens.append(token)
        
        for token in expired_tokens:
            del self.session_tokens[token]

    # ==================== اعتبارسنجی ورودی ====================

    def sanitize_input(self, text: str) -> str:
        """
        پاکسازی ورودی از کاراکترهای مخرب
        """
        if not text:
            return ""
        
        # حذف کاراکترهای کنترلی
        text = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', text)
        
        # حذف اسکریپت‌های مخرب
        text = re.sub(r'<script.*?</script>', '', text, flags=re.IGNORECASE | re.DOTALL)
        
        # محدود کردن طول
        text = text[:1000]
        
        return text.strip()

    def validate_user_input(self, text: str, input_type: str = 'general') -> Tuple[bool, str]:
        """
        اعتبارسنجی انواع مختلف ورودی
        """
        if not text:
            return False, "ورودی خالی است"
        
        # پاکسازی
        text = self.sanitize_input(text)
        
        if input_type == 'name':
            if len(text) < 2:
                return False, "نام باید حداقل 2 کاراکتر باشد"
            if len(text) > 50:
                return False, "نام نباید بیش از 50 کاراکتر باشد"
            if not re.match(r'^[a-zA-Zآ-ی\s]+$', text):
                return False, "نام فقط باید شامل حروف باشد"
        
        elif input_type == 'nft_code':
            if not re.match(r'^[A-Z0-9]{6,12}$', text):
                return False, "کد NFT باید 6-12 کاراکتر انگلیسی بزرگ و عدد باشد"
        
        elif input_type == 'wallet':
            if len(text) < 26 or len(text) > 62:
                return False, "آدرس کیف پول نامعتبر است"
            if not re.match(r'^[a-zA-Z0-9]+$', text):
                return False, "آدرس کیف پول فقط باید شامل حروف و اعداد باشد"
        
        return True, "معتبر"

    # ==================== رمزگذاری فایل ====================

    def encrypt_file_content(self, content: bytes, password: str) -> bytes:
        """
        رمزگذاری محتوای فایل (ساده)
        """
        key = hashlib.sha256(password.encode()).digest()
        encrypted = bytearray()
        
        for i, byte in enumerate(content):
            encrypted.append(byte ^ key[i % len(key)])
        
        return bytes(encrypted)

    def decrypt_file_content(self, encrypted_content: bytes, password: str) -> bytes:
        """
        رمزگشایی محتوای فایل
        """
        # در این روش ساده، رمزگذاری و رمزگشایی یکسان است (XOR)
        return self.encrypt_file_content(encrypted_content, password)

    # ==================== گزارش امنیتی ====================

    def generate_security_report(self) -> Dict:
        """
        تولید گزارش وضعیت امنیتی
        """
        current_time = time.time()
        
        # تلاش‌های ناموفق اخیر
        recent_failures = 0
        for attempts in self.failed_attempts.values():
            recent_failures += len([
                t for t in attempts 
                if current_time - t < 3600  # آخرین ساعت
            ])
        
        # کاربران مسدود شده
        active_blocks = len([
            block for block in self.blocked_users.values()
            if current_time < block['blocked_until']
        ])
        
        # جلسات فعال
        active_sessions = len([
            data for data in self.session_tokens.values()
            if current_time < data['expires_at']
        ])
        
        return {
            'timestamp': datetime.now().isoformat(),
            'failed_attempts_last_hour': recent_failures,
            'active_blocks': active_blocks,
            'active_sessions': active_sessions,
            'total_tracked_users': len(self.failed_attempts),
            'system_status': 'healthy' if recent_failures < 10 else 'warning'
        }

    async def log_security_event(self, event_type: str, user_id: int, details: str):
        """
        ثبت رویداد امنیتی در دیتابیس
        """
        if self.db:
            try:
                await self.db.add_security_log(
                    event_type=event_type,
                    user_id=user_id,
                    details=details,
                    timestamp=datetime.now()
                )
            except Exception as e:
                print(f"خطا در ثبت لاگ امنیتی: {e}")

    # ==================== پاکسازی خودکار ====================

    async def cleanup_security_data(self):
        """
        پاکسازی دوره‌ای داده‌های امنیتی
        """
        while True:
            try:
                # پاکسازی جلسات منقضی
                self.cleanup_expired_sessions()
                
                # پاکسازی تلاش‌های قدیمی
                current_time = time.time()
                for key in list(self.failed_attempts.keys()):
                    self.failed_attempts[key] = [
                        t for t in self.failed_attempts[key]
                        if current_time - t < 3600
                    ]
                    if not self.failed_attempts[key]:
                        del self.failed_attempts[key]
                
                # پاکسازی مسدودیت‌های منقضی
                for user_id in list(self.blocked_users.keys()):
                    if current_time >= self.blocked_users[user_id]['blocked_until']:
                        del self.blocked_users[user_id]
                
                # منتظر 30 دقیقه
                await asyncio.sleep(1800)
                
            except Exception as e:
                print(f"خطا در پاکسازی امنیتی: {e}")
                await asyncio.sleep(60)


# === تست کلاس ===
if __name__ == "__main__":
    # ایجاد نمونه
    security = Security()
    
    print("🔒 تست سیستم امنیتی")
    print("=" * 40)
    
    # تست رمز عبور
    password = "MySecure123!"
    hashed, salt = security.hash_password(password)
    is_correct = security.check_password(password, hashed, salt)
    print(f"✅ تست رمز عبور: {'موفق' if is_correct else 'ناموفق'}")
    
    # تست قدرت رمز
    is_strong, issues = security.is_strong_password(password)
    print(f"✅ قدرت رمز: {'قوی' if is_strong else 'ضعیف'}")
    if issues:
        for issue in issues:
            print(f"   - {issue}")
    
    # تولید رمز امن
    secure_pass = security.generate_secure_password()
    print(f"🔑 رمز تولید شده: {secure_pass}")
    
    # تست توکن جلسه
    token = security.create_session_token(123456)
    is_valid, user_id = security.verify_session_token(token)
    print(f"🎫 توکن جلسه: {'معتبر' if is_valid else 'نامعتبر'}")
    
    # گزارش امنیتی
    report = security.generate_security_report()
    print(f"📊 وضعیت سیستم: {report['system_status']}")
    
    print("=" * 40)
    print("✅ تست‌ها کامل شد!")
