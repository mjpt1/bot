import aiosqlite
import os
from datetime import datetime
from typing import Optional, List, Dict, Any
import hashlib
from config import settings

class Database:
    def __init__(self):
        self.db_path = settings.DATABASE_PATH

    async def init_db(self):
        """ایجاد تمام جداول دیتابیس فقط یکبار لازم است اجرا شود"""
        async with aiosqlite.connect(self.db_path) as db:
            # جدول کاربران
            await db.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    first_name TEXT NOT NULL,
                    last_name TEXT NOT NULL,
                    nft_code TEXT,
                    nft_image_path TEXT,
                    wallet_address TEXT,
                    access_code TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_blocked BOOLEAN DEFAULT FALSE
                )
            ''')

            # جدول دسته‌بندی
            await db.execute('''
                CREATE TABLE IF NOT EXISTS categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    title TEXT NOT NULL,
                    description TEXT,
                    icon TEXT DEFAULT '📁',
                    is_locked BOOLEAN DEFAULT FALSE,
                    password_hash TEXT,
                    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    position INTEGER DEFAULT 0
                )
            ''')

            # جدول دسترسی بخش‌های رمزدار برای یوزرها
            await db.execute('''
                CREATE TABLE IF NOT EXISTS category_access (
                    user_id INTEGER,
                    category_id INTEGER,
                    granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (user_id, category_id),
                    FOREIGN KEY (user_id) REFERENCES users (user_id),
                    FOREIGN KEY (category_id) REFERENCES categories (id)
                )
            ''')

            # جدول زیرمجموعه‌ها
            await db.execute('''
                CREATE TABLE IF NOT EXISTS subcategories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT,
                    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(category, name)
                )
            ''')

            # جدول محتوا
            await db.execute('''
                CREATE TABLE IF NOT EXISTS content (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT NOT NULL,
                    subcategory TEXT,
                    title TEXT NOT NULL,
                    description TEXT,
                    file_type TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    file_id TEXT,
                    upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # جدول لاگ تلاش ورود
            await db.execute('''
                CREATE TABLE IF NOT EXISTS login_attempts (
                    user_id INTEGER,
                    attempt_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    success BOOLEAN DEFAULT FALSE
                )
            ''')

            # فعالیت‌ها (آمار)
            await db.execute('''
                CREATE TABLE IF NOT EXISTS activities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    action TEXT NOT NULL,
                    details TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # جدول پیام پشتیبانی
            await db.execute('''
                CREATE TABLE IF NOT EXISTS support_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    message TEXT NOT NULL,
                    is_read BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # جدول بازدید محتوا
            await db.execute('''
                CREATE TABLE IF NOT EXISTS content_views (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    content_id INTEGER,
                    viewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id),
                    FOREIGN KEY (content_id) REFERENCES content (id)
                )
            ''')

            await self._insert_default_categories(db)
            await db.commit()

    async def _insert_default_categories(self, db):
        """اضافه‌کردن دسته‌های پیش‌فرض در اولین اجرا"""
        default_categories = [
            ('mindset', 'آموزش نگرش', '📚', 'آموزش‌های مربوط به ذهنیت', 0),
            ('blockchain', 'آموزش بلاکچین', '🔗', 'آموزش بلاکچین و رمزارزها', 1),
            ('referral', 'آموزش رفرال', '👥', 'روش‌های رفرال و معرفی', 2)
        ]
        for name, title, icon, desc, pos in default_categories:
            await db.execute('''
                INSERT OR IGNORE INTO categories (name, title, icon, description, position)
                VALUES (?, ?, ?, ?, ?)
            ''', (name, title, icon, desc, pos))

    # ==============================
    # ---------- کاربران -----------
    # ==============================

    async def add_user(self, user_data: dict) -> bool:
        """ثبت کاربر جدید"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('''
                    INSERT INTO users (user_id, first_name, last_name, nft_code,
                                       nft_image_path, wallet_address, access_code)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    user_data['user_id'],
                    user_data['first_name'],
                    user_data['last_name'],
                    user_data.get('nft_code'),
                    user_data.get('nft_image_path'),
                    user_data.get('wallet_address'),
                    user_data['access_code']
                ))
                await db.commit()
                return True
        except Exception as e:
            print(f"خطا در افزودن کاربر: {e}")
            return False

    async def get_user(self, user_id: int) -> Optional[Dict]:
        """گرفتن اطلاعات کاربر با user_id"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                'SELECT * FROM users WHERE user_id = ?', (user_id,)
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def update_user_status(self, user_id: int, status: str) -> bool:
        """تغییر وضعیت کاربر"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    'UPDATE users SET status = ? WHERE user_id = ?',
                    (status, user_id)
                )
                await db.commit()
                return True
        except Exception as e:
            print(f"update_user_status error: {e}")
            return False

    async def get_pending_users(self) -> List[Dict]:
        """همه کاربران در انتظار تایید"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                'SELECT * FROM users WHERE status = "pending"'
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def update_last_activity(self, user_id: int):
        """بروزرسانی آخرین فعالیت کاربر"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                'UPDATE users SET last_activity = CURRENT_TIMESTAMP WHERE user_id = ?',
                (user_id,)
            )
            await db.commit()

    async def toggle_block_user(self, user_id: int) -> bool:
        """غیرفعال‌سازی یا فعال‌سازی کاربر"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                'UPDATE users SET is_blocked = NOT is_blocked WHERE user_id = ?',
                (user_id,)
            )
            await db.commit()
            return True

    async def get_all_users(self, limit: int = 10, offset: int = 0) -> List[Dict]:
        """دریافت لیست همه کاربران با صفحه‌بندی"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                'SELECT * FROM users ORDER BY join_date DESC LIMIT ? OFFSET ?',
                (limit, offset)
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def search_user(self, query: str) -> List[Dict]:
        """جستجو بین کاربران بر اساس نام/نام‌خانوادگی/آیدی"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            try:
                user_id = int(query)
                cursor = await db.execute(
                    'SELECT * FROM users WHERE user_id = ? OR first_name LIKE ? OR last_name LIKE ?',
                    (user_id, f'%{query}%', f'%{query}%')
                )
            except:
                cursor = await db.execute(
                    'SELECT * FROM users WHERE first_name LIKE ? OR last_name LIKE ?',
                    (f'%{query}%', f'%{query}%')
                )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    # ==============================
    # ---------- دسته‌بندی ----------
    # ==============================
    async def add_category(self, name: str, title: str, description: str = None,
                          icon: str = '📁', is_locked: bool = False,
                          password: str = None) -> bool:
        """ایجاد دسته جدید (می‌تواند رمزدار باشد)"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                password_hash = None
                if is_locked and password:
                    password_hash = hashlib.sha256(password.encode()).hexdigest()

                await db.execute('''
                    INSERT INTO categories (name, title, description, icon, is_locked, password_hash)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (name, title, description, icon, is_locked, password_hash))
                await db.commit()
                return True
        except Exception as e:
            print(f"add_category error: {e}")
            return False

    async def get_all_categories(self) -> List[Dict]:
        """دریافت همه دسته‌بندی‌ها"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                'SELECT * FROM categories ORDER BY position, created_date'
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_category(self, category_name: str) -> Optional[Dict]:
        """گرفتن یک دسته از روی نام"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                'SELECT * FROM categories WHERE name = ?', (category_name,)
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def get_category_by_id(self, category_id: int) -> Optional[Dict]:
        """گرفتن دسته از روی آیدی"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                'SELECT * FROM categories WHERE id = ?', (category_id,)
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def get_user_accessible_categories(self, user_id: int) -> List[Dict]:
        """دریافت تمام دسته‌هایی که کاربر به آنها دسترسی دارد"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            
            # دسته‌های عادی (غیررمزدار)
            cursor = await db.execute('''
                SELECT * FROM categories 
                WHERE is_locked = 0 OR is_locked IS NULL
                ORDER BY position, created_date
            ''')
            normal_categories = await cursor.fetchall()
            
            # دسته‌های رمزدار که کاربر دسترسی دارد
            cursor = await db.execute('''
                SELECT c.* FROM categories c
                INNER JOIN category_access ca ON c.id = ca.category_id
                WHERE c.is_locked = 1 AND ca.user_id = ?
                ORDER BY c.position, c.created_date
            ''', (user_id,))
            locked_categories = await cursor.fetchall()
            
            all_categories = list(normal_categories) + list(locked_categories)
            return [dict(row) for row in all_categories]

    async def check_category_password(self, category_name: str, password: str) -> bool:
        """بررسی رمز صحیح دسته‌بندی"""
        category = await self.get_category(category_name)
        if not category or not category['is_locked']:
            return True
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        return category['password_hash'] == password_hash

    async def grant_category_access(self, user_id: int, category_id: int) -> bool:
        """اعطای دسترسی به بخش قفل شده"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('''
                    INSERT OR IGNORE INTO category_access (user_id, category_id)
                    VALUES (?, ?)
                ''', (user_id, category_id))
                await db.commit()
                return True
        except:
            return False

    async def has_category_access(self, user_id: int, category_name: str) -> bool:
        """آیا کاربر به دسته قفل‌دار دسترسی دارد؟"""
        category = await self.get_category(category_name)
        if not category:
            return False
        if not category['is_locked']:
            return True
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                'SELECT 1 FROM category_access WHERE user_id = ? AND category_id = ?',
                (user_id, category['id'])
            )
            return await cursor.fetchone() is not None

    # ویرایش و حذف و ...
    async def delete_category(self, category_name: str) -> bool:
        """پاک کردن دسته و همه زیرمجموعه و محتوای آن"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # حذف محتوا و زیرمجموعه
                await db.execute('DELETE FROM content WHERE category = ?', (category_name,))
                await db.execute('DELETE FROM subcategories WHERE category = ?', (category_name,))
                category = await self.get_category(category_name)
                if category:
                    await db.execute('DELETE FROM category_access WHERE category_id = ?', (category['id'],))
                await db.execute('DELETE FROM categories WHERE name = ?', (category_name,))
                await db.commit()
                return True
        except:
            return False

    async def update_category(self, category_name: str, updates: dict) -> bool:
        """آپدیت اطلاعات دسته بر اساس کلیدهای dict"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                fields = []
                values = []
                for key, value in updates.items():
                    if key in ['title', 'description', 'icon', 'is_locked', 'position']:
                        fields.append(f"{key} = ?")
                        values.append(value)
                    elif key == 'password' and value:
                        fields.append("password_hash = ?")
                        values.append(hashlib.sha256(value.encode()).hexdigest())
                if not fields:
                    return False
                values.append(category_name)
                query = f"UPDATE categories SET {', '.join(fields)} WHERE name = ?"
                await db.execute(query, values)
                await db.commit()
                return True
        except:
            return False

    # ==============================
    # ---------- محتوا -----------
    # ==============================

    async def add_content(self, content_data: dict) -> bool:
        """افزودن محتوای آموزشی به هر بخش/زیرمجموعه"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('''
                    INSERT INTO content (category, subcategory, title, description,
                                        file_type, file_path, file_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    content_data['category'],
                    content_data.get('subcategory'),
                    content_data['title'],
                    content_data.get('description'),
                    content_data['file_type'],
                    content_data['file_path'],
                    content_data.get('file_id')
                ))
                await db.commit()
                return True
        except Exception as e:
            print(f"add_content error: {e}")
            return False

    async def get_content_by_category(self, category: str, subcategory: Optional[str] = None) -> List[Dict]:
        """دریافت محتوای یک دسته (همه یا فیلتر شده بر اساس زیرمجموعه)"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            if subcategory:
                cursor = await db.execute(
                    'SELECT * FROM content WHERE category = ? AND subcategory = ?',
                    (category, subcategory)
                )
            else:
                cursor = await db.execute(
                    'SELECT * FROM content WHERE category = ? AND (subcategory IS NULL OR subcategory = "")',
                    (category,)
                )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_content(self, content_id: int) -> Optional[Dict]:
        """دریافت یک محتوا با آیدی"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                'SELECT * FROM content WHERE id = ?', (content_id,)
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def delete_content(self, content_id: int) -> bool:
        """حذف محتوا"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # دریافت اطلاعات محتوا برای حذف فایل
                cursor = await db.execute(
                    'SELECT file_path FROM content WHERE id = ?', (content_id,)
                )
                row = await cursor.fetchone()
                if row and os.path.exists(row[0]):
                    os.remove(row[0])
                
                await db.execute('DELETE FROM content WHERE id = ?', (content_id,))
                await db.execute('DELETE FROM content_views WHERE content_id = ?', (content_id,))
                await db.commit()
                return True
        except:
            return False

    async def update_content(self, content_id: int, updates: dict) -> bool:
        """آپدیت اطلاعات محتوا"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                fields = []
                values = []
                for key, value in updates.items():
                    if key in ['title', 'description', 'category', 'subcategory']:
                        fields.append(f"{key} = ?")
                        values.append(value)
                if not fields:
                    return False
                values.append(content_id)
                query = f"UPDATE content SET {', '.join(fields)} WHERE id = ?"
                await db.execute(query, values)
                await db.commit()
                return True
        except:
            return False

    async def get_all_content(self, limit: int = 50, offset: int = 0) -> List[Dict]:
        """دریافت همه محتوا با صفحه‌بندی"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                'SELECT * FROM content ORDER BY upload_date DESC LIMIT ? OFFSET ?',
                (limit, offset)
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def search_content(self, query: str) -> List[Dict]:
        """جستجو در محتوا"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                'SELECT * FROM content WHERE title LIKE ? OR description LIKE ?',
                (f'%{query}%', f'%{query}%')
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    # ==============================
    # -------- زیرمجموعه ----------
    # ==============================

    async def add_subcategory(self, category: str, name: str, description: str = None) -> bool:
        """ایجاد زیرمجموعه جدید برای دسته"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('''
                    INSERT INTO subcategories (category, name, description)
                    VALUES (?, ?, ?)
                ''', (category, name, description))
                await db.commit()
                return True
        except Exception as e:
            print(f"add_subcategory error: {e}")
            return False

    async def get_subcategories(self, category: str) -> List[Dict]:
        """دریافت لیست زیرمجموعه‌های یک دسته"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                'SELECT * FROM subcategories WHERE category = ? ORDER BY name',
                (category,)
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def delete_subcategory(self, subcategory_id: int) -> bool:
        """حذف زیرمجموعه و حذف محتوای آن"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(
                    'SELECT name, category FROM subcategories WHERE id = ?',
                    (subcategory_id,)
                )
                row = await cursor.fetchone()
                if row:
                    await db.execute(
                        'DELETE FROM content WHERE category = ? AND subcategory = ?',
                        (row[1], row[0])
                    )
                await db.execute('DELETE FROM subcategories WHERE id = ?', (subcategory_id,))
                await db.commit()
                return True
        except:
            return False

    async def get_subcategory(self, subcategory_id: int) -> Optional[Dict]:
        """دریافت زیرمجموعه با آیدی"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                'SELECT * FROM subcategories WHERE id = ?', (subcategory_id,)
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def update_subcategory(self, subcategory_id: int, name: str, description: str = None) -> bool:
        """آپدیت زیرمجموعه"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    'UPDATE subcategories SET name = ?, description = ? WHERE id = ?',
                    (name, description, subcategory_id)
                )
                await db.commit()
                return True
        except:
            return False

    # ==============================
    # ---------- پشتیبانی ----------
    # ==============================

    async def add_support_message(self, user_id: int, message: str) -> bool:
        """افزودن پیام پشتیبانی کاربر"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('''
                    INSERT INTO support_messages (user_id, message)
                    VALUES (?, ?)
                ''', (user_id, message))
                await db.commit()
                return True
        except:
            return False

    async def get_recent_support_messages(self, limit: int = 10) -> List[Dict]:
        """دریافت جدیدترین پیام‌های پشتیبانی"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(f'''
                SELECT sm.*, u.first_name, u.last_name 
                FROM support_messages sm
                LEFT JOIN users u ON sm.user_id = u.user_id
                ORDER BY sm.created_at DESC LIMIT ?
            ''', (limit,))
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_unread_support_messages(self) -> List[Dict]:
        """پیام‌های خوانده نشده پشتیبانی"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute('''
                SELECT sm.*, u.first_name, u.last_name 
                FROM support_messages sm
                LEFT JOIN users u ON sm.user_id = u.user_id
                WHERE sm.is_read = 0
                ORDER BY sm.created_at DESC
            ''')
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def mark_support_message_read(self, message_id: int) -> bool:
        """خوانده شدن پیام پشتیبانی توسط ادمین"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    'UPDATE support_messages SET is_read = 1 WHERE id = ?',
                    (message_id,)
                )
                await db.commit()
                return True
        except:
            return False

    async def get_support_message(self, message_id: int) -> Optional[Dict]:
        """دریافت پیام پشتیبانی"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                'SELECT * FROM support_messages WHERE id = ?', (message_id,)
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    # ==============================
    # ---------- آمار/فعالیت -------
    # ==============================

    async def log_activity(self, user_id: int, action: str, details: str = None):
        """ثبت یک رویداد فعالیت برای آمار یا لاگ مدیر"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                INSERT INTO activities (user_id, action, details)
                VALUES (?, ?, ?)
            ''', (user_id, action, details))
            await db.commit()

    async def log_content_view(self, user_id: int, content_id: int):
        """ثبت بازدید محتوا"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                INSERT INTO content_views (user_id, content_id)
                VALUES (?, ?)
            ''', (user_id, content_id))
            await db.commit()

    async def get_statistics(self) -> Dict:
        """دریافت آمار کلی سیستم"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute('SELECT COUNT(*) FROM users')
            total_users = (await cursor.fetchone())[0]
            cursor = await db.execute('SELECT COUNT(*) FROM users WHERE status = "approved"')
            approved_users = (await cursor.fetchone())[0]
            cursor = await db.execute('SELECT COUNT(*) FROM users WHERE status = "pending"')
            pending_users = (await cursor.fetchone())[0]
            cursor = await db.execute('SELECT COUNT(*) FROM users WHERE is_blocked = 1')
            blocked_users = (await cursor.fetchone())[0]
            cursor = await db.execute('SELECT COUNT(*) FROM content')
            total_content = (await cursor.fetchone())[0]
            cursor = await db.execute('SELECT COUNT(*) FROM categories')
            total_categories = (await cursor.fetchone())[0]
            cursor = await db.execute('SELECT COUNT(*) FROM subcategories')
            total_subcategories = (await cursor.fetchone())[0]
            cursor = await db.execute('SELECT COUNT(*) FROM support_messages WHERE is_read = 0')
            unread_support = (await cursor.fetchone())[0]
            cursor = await db.execute('''
                SELECT COUNT(*) FROM activities
                WHERE date(timestamp) = date('now')
            ''')
            today_activities = (await cursor.fetchone())[0]
            cursor = await db.execute('''
                SELECT COUNT(*) FROM content_views
                WHERE date(viewed_at) = date('now')
            ''')
            today_views = (await cursor.fetchone())[0]
            
            return {
                'total_users': total_users,
                'approved_users': approved_users,
                'pending_users': pending_users,
                'blocked_users': blocked_users,
                'total_content': total_content,
                'total_categories': total_categories,
                'total_subcategories': total_subcategories,
                'unread_support': unread_support,
                'today_activities': today_activities,
                'today_views': today_views
            }

    async def get_user_statistics(self, user_id: int) -> Dict:
        """آمار کاربر خاص"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                'SELECT COUNT(*) FROM content_views WHERE user_id = ?', (user_id,)
            )
            total_views = (await cursor.fetchone())[0]
            
            cursor = await db.execute(
                'SELECT COUNT(*) FROM activities WHERE user_id = ?', (user_id,)
            )
            total_activities = (await cursor.fetchone())[0]
            
            cursor = await db.execute(
                'SELECT COUNT(*) FROM support_messages WHERE user_id = ?', (user_id,)
            )
            support_messages = (await cursor.fetchone())[0]
            
            return {
                'total_views': total_views,
                'total_activities': total_activities,
                'support_messages': support_messages
            }

    async def get_recent_activities(self, limit: int = 20) -> List[Dict]:
        """فعالیت‌های اخیر"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute('''
                SELECT a.*, u.first_name, u.last_name 
                FROM activities a
                LEFT JOIN users u ON a.user_id = u.user_id
                ORDER BY a.timestamp DESC LIMIT ?
            ''', (limit,))
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    # ==============================
    # -------- تست و دیباگ --------
    # ==============================

    async def cleanup_old_data(self, days: int = 30) -> Dict[str, int]:
        """پاکسازی داده‌های قدیمی"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                results = {}

                # حذف فعالیت‌های قدیمی
                cursor = await db.execute('''
                    DELETE FROM activities
                    WHERE timestamp < date('now', '-{} days')
                '''.format(days))
                results['old_activities'] = cursor.rowcount

                # حذف لاگ‌های ورود قدیمی
                cursor = await db.execute('''
                    DELETE FROM login_attempts
                    WHERE attempt_time < date('now', '-{} days')
                '''.format(days))
                results['old_login_attempts'] = cursor.rowcount

                # حذف بازدیدهای قدیمی
                cursor = await db.execute('''
                    DELETE FROM content_views
                    WHERE viewed_at < date('now', '-{} days')
                '''.format(days))
                results['old_views'] = cursor.rowcount

                await db.commit()
                return results
        except Exception as e:
            print(f"خطا در پاکسازی: {e}")
            return {}

    async def get_database_info(self) -> Dict[str, Any]:
        """اطلاعات دیتابیس"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                info = {}

                # اندازه فایل
                info['file_size'] = os.path.getsize(self.db_path)
                info['file_size_mb'] = round(info['file_size'] / (1024 * 1024), 2)

                # تعداد جداول
                cursor = await db.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
                info['table_count'] = (await cursor.fetchone())[0]

                # اطلاعات جداول
                cursor = await db.execute("""
                    SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'
                """)
                tables = await cursor.fetchall()

                table_info = {}
                for table in tables:
                    table_name = table[0]
                    cursor = await db.execute(f"SELECT COUNT(*) FROM {table_name}")
                    count = (await cursor.fetchone())[0]
                    table_info[table_name] = count

                info['tables'] = table_info
                info['total_records'] = sum(table_info.values())

                return info
        except Exception as e:
            print(f"خطا در دریافت اطلاعات دیتابیس: {e}")
            return {}

    async def vacuum_database(self) -> bool:
        """بهینه‌سازی دیتابیس"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('VACUUM')
                await db.execute('ANALYZE')
                return True
        except Exception as e:
            print(f"خطا در بهینه‌سازی دیتابیس: {e}")
            return False
