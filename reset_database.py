# reset_database.py
import os
import asyncio
from database import Database
from config import settings

async def reset_database():
    """پاک کردن و ایجاد مجدد دیتابیس"""
    # حذف دیتابیس قدیمی
    if os.path.exists(settings.DATABASE_PATH):
        os.remove(settings.DATABASE_PATH)
        print("✅ دیتابیس قدیمی حذف شد")
    
    # حذف پوشه uploads اگر وجود دارد
    if os.path.exists('uploads'):
        import shutil
        shutil.rmtree('uploads')
        print("✅ پوشه uploads حذف شد")
    
    # ایجاد پوشه uploads
    os.makedirs('uploads', exist_ok=True)
    for folder in ['photos', 'videos', 'documents', 'nft_images']:
        os.makedirs(f'uploads/{folder}', exist_ok=True)
    print("✅ پوشه‌های مورد نیاز ایجاد شد")
    
    # ایجاد دیتابیس جدید
    db = Database()
    await db.init_db()
    print("✅ دیتابیس جدید با ساختار کامل ایجاد شد")
    
    # نمایش دسته‌های پیش‌فرض
    categories = await db.get_categories()
    print("\n📁 دسته‌های پیش‌فرض:")
    for cat in categories:
        print(f"  - {cat['title']} ({cat['name']})")

if __name__ == "__main__":
    asyncio.run(reset_database())
