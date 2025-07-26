import asyncio
import os
from datetime import datetime, timedelta
from aiogram import Router, F, types
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, BufferedInputFile

from states import AdminStates
from keyboards import Keyboards
from utils import (
    safe_send_message, safe_send_protected_content,
    handle_cancel, format_file_size, create_backup,
    generate_user_report, generate_content_report
)
from config import settings

admin_router = Router()

# ==============================
# -------- پنل اصلی ادمین ------
# ==============================

@admin_router.message(Command("panel"))
@admin_router.message(F.text == "🔧 پنل مدیریت کلی")
async def admin_main_panel(message: Message, is_admin, db):
    """پنل اصلی مدیریت"""
    if not is_admin:
        return
    
    # دریافت آمار سریع
    stats = await db.get_statistics()
    
    panel_text = f"""🔧 پنل مدیریت {settings.BOT_NAME}

📊 آمار سریع:
👥 کل کاربران: {stats['total_users']}
✅ تایید شده: {stats['approved_users']}
⏳ در انتظار: {stats['pending_users']}
🚫 مسدود: {stats['blocked_users']}
📚 تعداد محتوا: {stats['total_content']}
📈 فعالیت امروز: {stats['today_activities']}

⚡ برای مدیریت سریع از دکمه‌های زیر استفاده کنید:"""

    await message.answer(panel_text, reply_markup=Keyboards.get_admin_panel_keyboard())

# ==============================
# -------- مدیریت کاربران -----
# ==============================

@admin_router.message(F.text == "👥 مدیریت کاربران")
async def user_management_menu(message: Message, is_admin):
    """منوی مدیریت کاربران"""
    if not is_admin:
        return
    
    await message.answer(
        "👥 مدیریت کاربران\n\nبخش مورد نظر را انتخاب کنید:",
        reply_markup=Keyboards.get_user_management_keyboard()
    )

@admin_router.message(F.text == "👥 کاربران جدید")
async def pending_users_button(message: Message, is_admin, db):
    """نمایش کاربران در انتظار تایید"""
    if not is_admin:
        return
    
    users = await db.get_pending_users()
    if not users:
        await message.answer("✅ هیچ کاربری در انتظار تایید نیست.")
        return
    
    await message.answer(f"👥 {len(users)} کاربر در انتظار تایید:")
    
    for user in users[:5]:  # نمایش 5 کاربر اول
        user_text = f"""👤 {user['first_name']} {user['last_name']}
🆔 آیدی: {user['user_id']}
🎯 کد NFT: {user['nft_code']}
💳 ولت: {user['wallet_address'][:20]}...
📅 ثبت نام: {user['join_date']}"""
        
        keyboard = Keyboards.get_user_action_keyboard(user['user_id'])
        await message.answer(user_text, reply_markup=keyboard)
        await asyncio.sleep(0.5)

# ==============================
# -------- مدیریت محتوا --------
# ==============================

@admin_router.message(F.text == "📚 مدیریت محتوا")
async def content_management_menu(message: Message, is_admin):
    """منوی مدیریت محتوا"""
    if not is_admin:
        return
    
    await message.answer(
        "📚 مدیریت محتوا\n\nعملیات مورد نظر را انتخاب کنید:",
        reply_markup=Keyboards.get_content_management_keyboard()
    )

@admin_router.message(F.text == "➕ افزودن محتوا")
async def add_content_start(message: Message, state: FSMContext, is_admin):
    """شروع فرآیند افزودن محتوا"""
    if not is_admin:
        return
    
    await message.answer(
        "📎 لطفا فایل آموزشی را ارسال کنید:\n\n"
        "فرمت‌های پشتیبانی شده:\n"
        "🖼️ عکس (JPG, PNG, WEBP)\n"
        "🎥 ویدیو (MP4, AVI, MOV)\n"
        "📄 سند (PDF, DOC, DOCX, TXT)\n\n"
        "⚠️ حداکثر حجم فایل: 50 مگابایت",
        reply_markup=Keyboards.get_cancel_keyboard()
    )
    await state.set_state(AdminStates.waiting_for_content_file)

@admin_router.message(AdminStates.waiting_for_content_file, F.photo)
async def receive_photo_content(message: Message, state: FSMContext, is_admin):
    """دریافت محتوای عکس"""
    if not is_admin:
        return
    
    if await handle_cancel(message, state):
        return
    
    # پردازش فایل عکس
    file = message.photo[-1]  # بزرگترین سایز
    file_info = await message.bot.get_file(file.file_id)
    
    # بررسی حجم فایل
    if file_info.file_size > 50 * 1024 * 1024:  # 50MB
        await message.answer("❌ حجم فایل بیش از حد مجاز است. حداکثر 50 مگابایت.")
        return
    
    # ذخیره فایل
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    file_path = f"{settings.CONTENT_PHOTOS_DIR}/photo_{timestamp}_{message.from_user.id}.jpg"
    
    os.makedirs(settings.CONTENT_PHOTOS_DIR, exist_ok=True)
    await message.bot.download_file(file_info.file_path, file_path)
    
    await state.update_data(
        file_type='photo',
        file_path=file_path,
        file_id=file.file_id,
        file_size=file_info.file_size
    )
    
    # انتخاب دسته
    categories = await state.get_data().get('db').get_all_categories()
    keyboard = Keyboards.get_content_categories_keyboard(categories)
    
    await message.answer(
        "✅ عکس دریافت شد!\n📂 لطفا دسته‌بندی را انتخاب کنید:",
        reply_markup=keyboard
    )
    await state.set_state(AdminStates.waiting_for_category)

@admin_router.message(AdminStates.waiting_for_content_file, F.video)
async def receive_video_content(message: Message, state: FSMContext, is_admin):
    """دریافت محتوای ویدیو"""
    if not is_admin:
        return
    
    if await handle_cancel(message, state):
        return
    
    file = message.video
    file_info = await message.bot.get_file(file.file_id)
    
    # بررسی حجم
    if file_info.file_size > 50 * 1024 * 1024:
        await message.answer("❌ حجم فایل بیش از حد مجاز است.")
        return
    
    # ذخیره فایل
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    file_path = f"{settings.CONTENT_VIDEOS_DIR}/video_{timestamp}_{message.from_user.id}.mp4"
    
    os.makedirs(settings.CONTENT_VIDEOS_DIR, exist_ok=True)
    await message.bot.download_file(file_info.file_path, file_path)
    
    await state.update_data(
        file_type='video',
        file_path=file_path,
        file_id=file.file_id,
        file_size=file_info.file_size,
        duration=file.duration
    )
    
    # انتخاب دسته
    categories = await state.get_data().get('db').get_all_categories()
    keyboard = Keyboards.get_content_categories_keyboard(categories)
    
    await message.answer(
        f"✅ ویدیو دریافت شد! ({format_file_size(file_info.file_size)})\n"
        f"⏱️ مدت: {file.duration // 60}:{file.duration % 60:02d}\n"
        f"📂 لطفا دسته‌بندی را انتخاب کنید:",
        reply_markup=keyboard
    )
    await state.set_state(AdminStates.waiting_for_category)

@admin_router.message(AdminStates.waiting_for_content_file, F.document)
async def receive_document_content(message: Message, state: FSMContext, is_admin):
    """دریافت محتوای سند"""
    if not is_admin:
        return
    
    if await handle_cancel(message, state):
        return
    
    file = message.document
    file_info = await message.bot.get_file(file.file_id)
    
    # بررسی نوع فایل
    allowed_extensions = ['.pdf', '.doc', '.docx', '.txt', '.ppt', '.pptx']
    file_ext = os.path.splitext(file.file_name or '')[1].lower()
    
    if file_ext not in allowed_extensions:
        await message.answer(
            f"❌ نوع فایل پشتیبانی نمی‌شود.\n"
            f"فرمت‌های مجاز: {', '.join(allowed_extensions)}"
        )
        return
    
    # بررسی حجم
    if file_info.file_size > 50 * 1024 * 1024:
        await message.answer("❌ حجم فایل بیش از حد مجاز است.")
        return
    
    # ذخیره فایل
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    safe_filename = file.file_name.replace(' ', '_').replace('/', '_')
    file_path = f"{settings.CONTENT_DOCUMENTS_DIR}/doc_{timestamp}_{safe_filename}"
    
    os.makedirs(settings.CONTENT_DOCUMENTS_DIR, exist_ok=True)
    await message.bot.download_file(file_info.file_path, file_path)
    
    await state.update_data(
        file_type='document',
        file_path=file_path,
        file_id=file.file_id,
        file_size=file_info.file_size,
        original_name=file.file_name
    )
    
    # انتخاب دسته
    categories = await state.get_data().get('db').get_all_categories()
    keyboard = Keyboards.get_content_categories_keyboard(categories)
    
    await message.answer(
        f"✅ سند دریافت شد!\n"
        f"📄 نام: {file.file_name}\n"
        f"📊 حجم: {format_file_size(file_info.file_size)}\n"
        f"📂 لطفا دسته‌بندی را انتخاب کنید:",
        reply_markup=keyboard
    )
    await state.set_state(AdminStates.waiting_for_category)

@admin_router.message(AdminStates.waiting_for_title)
async def process_content_title(message: Message, state: FSMContext, is_admin):
    """پردازش عنوان محتوا"""
    if not is_admin:
        return
    
    if await handle_cancel(message, state):
        return
    
    title = message.text.strip()
    
    if len(title) < 3:
        await message.answer("❌ عنوان باید حداقل 3 کاراکتر باشد:")
        return
    elif len(title) > 100:
        await message.answer("❌ عنوان نباید بیش از 100 کاراکتر باشد:")
        return
    
    await state.update_data(content_title=title)
    await message.answer(
        "📝 لطفا توضیحات محتوا را وارد کنید:\n"
        "(یا 'بدون توضیح' بنویسید)",
        reply_markup=Keyboards.get_cancel_keyboard()
    )
    await state.set_state(AdminStates.waiting_for_description)

@admin_router.message(AdminStates.waiting_for_description)
async def process_content_description(message: Message, state: FSMContext, is_admin, db):
    """پردازش توضیحات محتوا و ذخیره نهایی"""
    if not is_admin:
        return
    
    if await handle_cancel(message, state):
        return
    
    description = message.text.strip()
    if description.lower() in ['بدون توضیح', 'ندارد', '-']:
        description = None
    elif len(description) > 500:
        await message.answer("❌ توضیحات نباید بیش از 500 کاراکتر باشد:")
        return
    
    # دریافت تمام داده‌ها
    data = await state.get_data()
    
    # آماده‌سازی داده‌های محتوا
    content_data = {
        'category': data['selected_category'],
        'subcategory': data.get('selected_subcategory'),
        'title': data['content_title'],
        'description': description,
        'file_type': data['file_type'],
        'file_path': data['file_path'],
        'file_id': data['file_id']
    }
    
    # ذخیره در دیتابیس
    success = await db.add_content(content_data)
    
    if success:
        await message.answer(
            "✅ محتوا با موفقیت اضافه شد!\n\n"
            f"📂 دسته: {data['selected_category']}\n"
            f"📁 زیرمجموعه: {data.get('selected_subcategory', 'ندارد')}\n"
            f"📝 عنوان: {data['content_title']}\n"
            f"📄 نوع: {data['file_type']}\n"
            f"📊 حجم: {format_file_size(data.get('file_size', 0))}",
            reply_markup=Keyboards.get_admin_main_keyboard()
        )
        
        await db.log_activity(message.from_user.id, "add_content", f"افزودن محتوا: {data['content_title']}")
    else:
        await message.answer(
            "❌ خطا در ذخیره محتوا!\n"
            "لطفاً دوباره تلاش کنید.",
            reply_markup=Keyboards.get_admin_main_keyboard()
        )
    
    await state.clear()

# ==============================
# -------- مدیریت دسته‌ها -----
# ==============================

@admin_router.message(F.text == "📂 مدیریت دسته‌ها")
async def category_management_menu(message: Message, is_admin):
    """منوی مدیریت دسته‌ها"""
    if not is_admin:
        return
    
    await message.answer(
        "📂 مدیریت دسته‌ها\n\nعملیات مورد نظر را انتخاب کنید:",
        reply_markup=Keyboards.get_category_management_keyboard()
    )

# ==============================
# -------- پیام همگانی --------
# ==============================

@admin_router.message(F.text == "📨 پیام همگانی")
async def broadcast_menu(message: Message, is_admin):
    """منوی پیام همگانی"""
    if not is_admin:
        return
    
    await message.answer(
        "📨 پیام همگانی\n\nعملیات مورد نظر را انتخاب کنید:",
        reply_markup=Keyboards.get_broadcast_keyboard()
    )

@admin_router.message(AdminStates.waiting_for_broadcast_message)
async def process_broadcast_message(message: Message, state: FSMContext, is_admin, db):
    """پردازش پیام همگانی"""
    if not is_admin:
        return
    
    if await handle_cancel(message, state):
        return
    
    if not message.text:
        await message.answer("❌ لطفاً پیام متنی ارسال کنید.")
        return
    
    if len(message.text) > 2000:
        await message.answer("❌ پیام نباید بیش از 2000 کاراکتر باشد.")
        return
    
    # ذخیره پیام
    await state.update_data(broadcast_message=message.text)
    
    # انتخاب مخاطبان
    stats = await db.get_statistics()
    
    target_text = f"""📊 انتخاب مخاطبان پیام:

👥 همه کاربران: {stats['total_users']}
✅ تایید شده: {stats['approved_users']}
⭐ کاربران VIP: {stats.get('vip_users', 0)}
⏳ در انتظار: {stats['pending_users']}

📝 پیام شما:
{message.text[:200]}{'...' if len(message.text) > 200 else ''}

مخاطبان را انتخاب کنید:"""

    await message.answer(target_text, reply_markup=Keyboards.get_broadcast_target_keyboard())
    await state.set_state(AdminStates.waiting_for_broadcast_target)

# ==============================
# -------- آمار و گزارش -------
# ==============================

@admin_router.message(F.text == "📊 آمار سریع")
async def quick_stats(message: Message, is_admin, db):
    """نمایش آمار سریع"""
    if not is_admin:
        return
    
    stats = await db.get_statistics()
    recent_users = await db.get_recent_users(5)
    
    stats_text = f"""📊 آمار {settings.BOT_NAME}

👥 آمار کاربران:
- کل: {stats['total_users']}
- تایید شده: {stats['approved_users']}
- در انتظار: {stats['pending_users']}
- مسدود: {stats['blocked_users']}

📚 آمار محتوا:
- کل محتوا: {stats['total_content']}
- محتوای VIP: {stats.get('vip_content', 0)}
- دسته‌ها: {stats.get('categories_count', 0)}

📈 فعالیت:
- امروز: {stats['today_activities']}
- این هفته: {stats.get('week_activities', 0)}

👤 آخرین کاربران:"""

    for user in recent_users:
        stats_text += f"\n• {user['first_name']} ({user['user_id']})"
    
    await message.answer(stats_text)

@admin_router.message(F.text == "📊 آمار و گزارش")
async def stats_menu(message: Message, is_admin):
    """منوی آمار و گزارش"""
    if not is_admin:
        return
    
    await message.answer(
        "📊 آمار و گزارش\n\nنوع گزارش مورد نظر را انتخاب کنید:",
        reply_markup=Keyboards.get_stats_keyboard()
    )

# ==============================
# -------- بک‌آپ و بازیابی -----
# ==============================

@admin_router.message(F.text == "🔄 بک‌آپ")
async def backup_menu(message: Message, is_admin):
    """منوی بک‌آپ"""
    if not is_admin:
        return
    
    await message.answer(
        "🔄 بک‌آپ و بازیابی\n\nعملیات مورد نظر را انتخاب کنید:",
        reply_markup=Keyboards.get_backup_keyboard()
    )

@admin_router.message(Command("backup"))
async def create_backup_command(message: Message, is_admin, db):
    """ایجاد بک‌آپ با دستور"""
    if not is_admin:
        return
    
    await message.answer("🔄 در حال ایجاد بک‌آپ...")
    
    try:
        backup_path = await create_backup(db)
        
        if backup_path and os.path.exists(backup_path):
            file_size = os.path.getsize(backup_path)
            
            with open(backup_path, 'rb') as backup_file:
                await message.answer_document(
                    BufferedInputFile(backup_file.read(), filename=os.path.basename(backup_path)),
                    caption=f"✅ بک‌آپ ایجاد شد\n📊 حجم: {format_file_size(file_size)}\n📅 {datetime.now().strftime('%Y/%m/%d - %H:%M')}"
                )
            
            await db.log_activity(message.from_user.id, "create_backup", "ایجاد بک‌آپ دستی")
        else:
            await message.answer("❌ خطا در ایجاد بک‌آپ!")
            
    except Exception as e:
        print(f"خطا در ایجاد بک‌آپ: {e}")
        await message.answer("❌ خطا در ایجاد بک‌آپ!")

# ==============================
# -------- تست سیستم ---------
# ==============================

@admin_router.message(F.text == "🧪 تست سیستم")
async def test_system_menu(message: Message, is_admin):
    """منوی تست سیستم"""
    if not is_admin:
        return
    
    await message.answer(
        "🧪 تست سیستم\n\nبخش مورد نظر برای تست را انتخاب کنید:",
        reply_markup=Keyboards.get_test_system_keyboard()
    )

@admin_router.message(Command("test"))
async def quick_system_test(message: Message, is_admin, db):
    """تست سریع سیستم"""
    if not is_admin:
        return
    
    await message.answer("🧪 در حال انجام تست سریع سیستم...")
    
    test_results = []
    
    # تست دیتابیس
    try:
        db_test = await db.test_connection()
        test_results.append(f"🗄️ دیتابیس: {'✅ سالم' if db_test else '❌ خطا'}")
    except:
        test_results.append("🗄️ دیتابیس: ❌ خطا")
    
    # تست فایل‌ها
    try:
        dirs_ok = all([
            os.path.exists(settings.CONTENT_DIR),
            os.path.exists(settings.DATABASE_DIR),
            os.path.exists(settings.BACKUP_DIR)
        ])
        test_results.append(f"📁 پوشه‌ها: {'✅ سالم' if dirs_ok else '❌ خطا'}")
    except:
        test_results.append("📁 پوشه‌ها: ❌ خطا")
    
    # تست تنظیمات
    try:
        config_ok = bool(settings.BOT_TOKEN and settings.ADMIN_IDS)
        test_results.append(f"⚙️ تنظیمات: {'✅ سالم' if config_ok else '❌ خطا'}")
    except:
        test_results.append("⚙️ تنظیمات: ❌ خطا")
    
    test_text = "🧪 نتایج تست سریع:\n\n" + "\n".join(test_results)
    await message.answer(test_text)

# ==============================
# -------- تنظیمات ------------
# ==============================

@admin_router.message(F.text == "⚙️ تنظیمات")
async def settings_menu(message: Message, is_admin):
    """منوی تنظیمات"""
    if not is_admin:
        return
    
    settings_text = f"""⚙️ تنظیمات {settings.BOT_NAME}

🤖 وضعیت ربات: {'🟢 فعال' if not settings.MAINTENANCE_MODE else '🔴 تعمیرات'}
🔍 حالت دیباگ: {'🟢 فعال' if settings.DEBUG else '🔴 غیرفعال'}
👑 تعداد ادمین: {len(settings.ADMIN_IDS)}

📊 محدودیت‌ها:
- حداکثر تلاش ورود: {settings.MAX_LOGIN_ATTEMPTS}
- زمان انتظار: {settings.LOGIN_TIMEOUT} ثانیه
- انقضای نشست: {settings.SESSION_TIMEOUT} ثانیه

بخش مورد نظر را انتخاب کنید:"""

    await message.answer(settings_text, reply_markup=Keyboards.get_settings_keyboard())

def setup_admin_handlers(dp):
    """تنظیم تمام هندلرهای ادمین"""
    dp.include_router(admin_router)
    print("✅ هندلرهای ادمین تنظیم شدند")
