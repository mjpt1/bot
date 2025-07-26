import asyncio
import os
from datetime import datetime
from typing import Optional, List, Dict
import aiosqlite

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton
)

from config import settings
from database import Database
from security import Security

# --- مدیریت stateها ---
class RegistrationStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_lastname = State()
    waiting_for_nft_code = State()
    waiting_for_wallet = State()

class AdminStates(StatesGroup):
    waiting_for_content_file = State()
    waiting_for_category = State()
    waiting_for_subcategory = State()
    waiting_for_subcategory_choice = State()
    waiting_for_new_subcategory_name = State()
    waiting_for_new_subcategory_desc = State()
    waiting_for_title = State()
    waiting_for_description = State()
    waiting_for_broadcast_message = State()
    waiting_for_user_search = State()
    waiting_for_admin_reply = State()
    waiting_for_edit_choice = State()
    waiting_for_new_content = State()
    managing_content = State()
    managing_subcategories = State()
    waiting_for_new_category_name = State()
    waiting_for_new_category_title = State()
    waiting_for_new_category_desc = State()
    waiting_for_category_password = State()
    waiting_for_locked_category_password = State()

class UserStates(StatesGroup):
    waiting_for_support_message = State()
    waiting_for_category_password = State()

# --- راه اندازی ---
bot = Bot(token=settings.BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
db = Database()
security = Security(db)

# --- کیبوردهای اصلی ---
def get_cancel_keyboard():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="❌ انصراف")]], resize_keyboard=True)

def get_back_keyboard():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🔙 بازگشت به منوی اصلی")]], resize_keyboard=True)

def get_main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📚 دسته‌بندی‌ها"), KeyboardButton(text="👤 پروفایل من")],
            [KeyboardButton(text="💬 پشتیبانی")]
        ],
        resize_keyboard=True
    )

def get_admin_main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔧 پنل مدیریت کامل")],
            [KeyboardButton(text="📊 آمار و گزارش"), KeyboardButton(text="👥 مدیریت کاربران")],
            [KeyboardButton(text="📁 مدیریت دسته‌ها"), KeyboardButton(text="📝 مدیریت محتوا")],
            [KeyboardButton(text="💬 پیام‌های پشتیبانی"), KeyboardButton(text="📨 پیام همگانی")]
        ],
        resize_keyboard=True
    )

def get_admin_panel_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 کاربران در انتظار تایید", callback_data="pending_users")],
        [InlineKeyboardButton(text="📊 آمار کلی سیستم", callback_data="statistics")],
        [InlineKeyboardButton(text="👤 مدیریت کاربران", callback_data="users_management")],
        [InlineKeyboardButton(text="📁 ایجاد دسته جدید", callback_data="create_category")],
        [InlineKeyboardButton(text="📂 مدیریت دسته‌ها", callback_data="manage_categories")],
        [InlineKeyboardButton(text="➕ افزودن محتوا", callback_data="add_content")],
        [InlineKeyboardButton(text="📝 مدیریت محتوا", callback_data="manage_content")],
        [InlineKeyboardButton(text="📂 مدیریت زیرمجموعه‌ها", callback_data="manage_subcategories")],
        [InlineKeyboardButton(text="📨 پیام همگانی", callback_data="broadcast")],
        [InlineKeyboardButton(text="🔍 جستجوی کاربر", callback_data="search_user")],
        [InlineKeyboardButton(text="💬 پیام‌های پشتیبانی", callback_data="support_messages")]
    ])

# --- هندلر start ---
@dp.message(Command("start"))
async def start_handler(message: types.Message, state: FSMContext):
    await state.clear()
    
    # بررسی اینکه کاربر ادمین است
    if settings.is_admin(message.from_user.id):
        await message.answer(
            "🔰 سلام ادمین عزیز!\n\n"
            "شما به عنوان مدیر سیستم شناخته شده‌اید.\n"
            "از پنل مدیریت اختصاصی خود استفاده کنید.",
            reply_markup=get_admin_main_keyboard()
        )
        return

    # بررسی وضعیت کاربر معمولی
    user = await db.get_user(message.from_user.id)
    if user:
        if user['status'] == 'approved' and not user['is_blocked']:
            await message.answer(
                f"سلام {user['first_name']} عزیز! 👋\n\n"
                "به ربات آموزشی خوش آمدید.\n"
                "از منوی زیر استفاده کنید:",
                reply_markup=get_main_keyboard()
            )
            await db.update_last_activity(message.from_user.id)
        elif user['status'] == 'pending':
            await message.answer(
                "⏳ درخواست شما در حال بررسی است.\n"
                "لطفا صبور باشید تا ادمین درخواست شما را بررسی کند."
            )
        elif user['status'] == 'rejected':
            await message.answer(
                "❌ متاسفانه درخواست شما رد شده است.\n"
                "برای اطلاعات بیشتر با پشتیبانی تماس بگیرید."
            )
        elif user['is_blocked']:
            await message.answer(
                "🚫 دسترسی شما به ربات محدود شده است.\n"
                "برای اطلاعات بیشتر با پشتیبانی تماس بگیرید."
            )
    else:
        # شروع فرآیند ثبت نام
        await message.answer(
            settings.WELCOME_MESSAGE + "\n\n"
            "📝 برای ثبت نام، لطفا اطلاعات زیر را به ترتیب وارد کنید.\n\n"
            "👤 ابتدا نام خود را وارد کنید:",
            reply_markup=get_cancel_keyboard()
        )
        await state.set_state(RegistrationStates.waiting_for_name)
        await db.log_activity(message.from_user.id, "start", "شروع ثبت نام")

# --- فرآیند ثبت نام ---
@dp.message(RegistrationStates.waiting_for_name)
async def process_name(message: types.Message, state: FSMContext):
    if message.text == "❌ انصراف":
        await state.clear()
        await message.answer("ثبت نام لغو شد.", reply_markup=types.ReplyKeyboardRemove())
        return
    
    if len(message.text) < 2 or len(message.text) > 50:
        await message.answer("❌ نام باید بین 2 تا 50 کاراکتر باشد.\nلطفا دوباره وارد کنید:")
        return
    
    await state.update_data(first_name=message.text)
    await message.answer("👤 حالا نام خانوادگی خود را وارد کنید:")
    await state.set_state(RegistrationStates.waiting_for_lastname)

@dp.message(RegistrationStates.waiting_for_lastname)
async def process_lastname(message: types.Message, state: FSMContext):
    if message.text == "❌ انصراف":
        await state.clear()
        await message.answer("ثبت نام لغو شد.", reply_markup=types.ReplyKeyboardRemove())
        return
    
    if len(message.text) < 2 or len(message.text) > 50:
        await message.answer("❌ نام خانوادگی باید بین 2 تا 50 کاراکتر باشد.\nلطفا دوباره وارد کنید:")
        return
    
    await state.update_data(last_name=message.text)
    await message.answer("🎯 کد NFT خود را وارد کنید:")
    await state.set_state(RegistrationStates.waiting_for_nft_code)

@dp.message(RegistrationStates.waiting_for_nft_code)
async def process_nft_code(message: types.Message, state: FSMContext):
    if message.text == "❌ انصراف":
        await state.clear()
        await message.answer("ثبت نام لغو شد.", reply_markup=types.ReplyKeyboardRemove())
        return
    
    await state.update_data(nft_code=message.text)
    await message.answer("💳 آدرس کیف پول (Wallet Address) خود را وارد کنید:")
    await state.set_state(RegistrationStates.waiting_for_wallet)

@dp.message(RegistrationStates.waiting_for_wallet)
async def process_wallet(message: types.Message, state: FSMContext):
    if message.text == "❌ انصراف":
        await state.clear()
        await message.answer("ثبت نام لغو شد.", reply_markup=types.ReplyKeyboardRemove())
        return
    
    data = await state.get_data()
    user_data = {
        'user_id': message.from_user.id,
        'first_name': data['first_name'],
        'last_name': data['last_name'],
        'wallet_address': message.text,
        'nft_code': data['nft_code'],
        'nft_image_path': None,
        'access_code': 'NOT_REQUIRED'
    }
    
    if await db.add_user(user_data):
        await message.answer(
            "✅ ثبت نام شما با موفقیت انجام شد!\n\n"
            "⏳ درخواست شما در انتظار بررسی ادمین است.\n"
            "به محض تایید، اطلاع رسانی خواهد شد.",
            reply_markup=types.ReplyKeyboardRemove()
        )
        
        # اطلاع رسانی به ادمین‌ها
        admin_message = f"""🆕 درخواست ثبت نام جدید:

👤 نام: {data['first_name']} {data['last_name']}
🆔 آیدی: {message.from_user.id}
📱 یوزرنیم: @{message.from_user.username or 'ندارد'}
🎯 کد NFT: {data['nft_code']}
💳 آدرس ولت: {message.text}
📅 زمان: {datetime.now().strftime('%Y-%m-%d %H:%M')}"""

        approve_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ تایید", callback_data=f"approve_{message.from_user.id}"),
                InlineKeyboardButton(text="❌ رد", callback_data=f"reject_{message.from_user.id}")
            ],
            [InlineKeyboardButton(text="👤 مشاهده پروفایل", callback_data=f"view_profile_{message.from_user.id}")]
        ])
        
        for admin_id in settings.ADMIN_IDS:
            try:
                await bot.send_message(admin_id, admin_message, reply_markup=approve_keyboard)
            except Exception as e:
                print(f"⚠️ خطا در ارسال به ادمین {admin_id}: {str(e)}")
        
        await db.log_activity(message.from_user.id, "registration", "تکمیل ثبت نام")
    else:
        await message.answer(
            "❌ خطا در ثبت نام!\n"
            "لطفا دوباره با دستور /start تلاش کنید.",
            reply_markup=types.ReplyKeyboardRemove()
        )
    
    await state.clear()

# --- پنل‌های ادمین ---
@dp.message(F.text == "🔧 پنل مدیریت کامل")
async def admin_full_panel(message: types.Message):
    if not settings.is_admin(message.from_user.id):
        return
    await message.answer(
        "🔧 پنل مدیریت کامل سیستم\n\n"
        "از گزینه‌های زیر برای مدیریت استفاده کنید:",
        reply_markup=get_admin_panel_keyboard()
    )

@dp.message(F.text == "📊 آمار و گزارش")
async def admin_stats_report(message: types.Message):
    if not settings.is_admin(message.from_user.id):
        return
    stats = await db.get_statistics()
    await message.answer(
        f"📊 آمار کامل سیستم:\n\n"
        f"👥 کل کاربران: {stats['total_users']}\n"
        f"✅ تایید شده: {stats['approved_users']}\n"
        f"⏳ در انتظار: {stats['pending_users']}\n"
        f"🚫 مسدود شده: {stats['blocked_users']}\n"
        f"📚 تعداد محتوا: {stats['total_content']}\n"
        f"📊 فعالیت امروز: {stats['today_activities']}"
    )

# --- مدیریت دسته‌بندی‌ها ---
@dp.callback_query(F.data == "create_category")
async def create_new_category(callback: types.CallbackQuery, state: FSMContext):
    if not settings.is_admin(callback.from_user.id):
        await callback.answer("دسترسی ندارید!", show_alert=True)
        return
    
    await callback.message.answer(
        "📁 ایجاد دسته جدید\n\n"
        "نام انگلیسی دسته را وارد کنید (برای آدرس‌دهی):",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(AdminStates.waiting_for_new_category_name)
    await callback.answer()

@dp.message(AdminStates.waiting_for_new_category_name)
async def receive_category_name(message: types.Message, state: FSMContext):
    if message.text == "❌ انصراف":
        await state.clear()
        await message.answer("عملیات لغو شد.", reply_markup=get_admin_main_keyboard())
        return
    
    await state.update_data(category_name=message.text.lower().replace(' ', '_'))
    await message.answer("📝 عنوان فارسی دسته را وارد کنید:")
    await state.set_state(AdminStates.waiting_for_new_category_title)

@dp.message(AdminStates.waiting_for_new_category_title)
async def receive_category_title(message: types.Message, state: FSMContext):
    if message.text == "❌ انصراف":
        await state.clear()
        await message.answer("عملیات لغو شد.", reply_markup=get_admin_main_keyboard())
        return
    
    await state.update_data(category_title=message.text)
    await message.answer("📄 توضیحات دسته را وارد کنید (یا /skip برای رد کردن):")
    await state.set_state(AdminStates.waiting_for_new_category_desc)

@dp.message(AdminStates.waiting_for_new_category_desc)
async def receive_category_description(message: types.Message, state: FSMContext):
    if message.text == "❌ انصراف":
        await state.clear()
        await message.answer("عملیات لغو شد.", reply_markup=get_admin_main_keyboard())
        return
    
    desc = message.text if message.text != "/skip" else None
    await state.update_data(category_desc=desc)
    
    # انتخاب نوع دسته
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔓 دسته عادی", callback_data="normal_category")],
        [InlineKeyboardButton(text="🔐 دسته رمزدار", callback_data="locked_category")]
    ])
    
    await message.answer("🔐 نوع دسته را انتخاب کنید:", reply_markup=keyboard)

@dp.callback_query(F.data.in_(["normal_category", "locked_category"]))
async def handle_category_type(callback: types.CallbackQuery, state: FSMContext):
    if not settings.is_admin(callback.from_user.id):
        await callback.answer("دسترسی ندارید!", show_alert=True)
        return
    
    data = await state.get_data()
    is_locked = callback.data == "locked_category"
    
    if is_locked:
        await callback.message.answer("🔑 رمز عبور برای این دسته را وارد کنید:")
        await state.update_data(is_locked=True)
        await state.set_state(AdminStates.waiting_for_category_password)
    else:
        # ایجاد دسته عادی
        result = await db.add_category(
            name=data['category_name'],
            title=data['category_title'],
            description=data.get('category_desc'),
            is_locked=False
        )
        
        if result:
            await callback.message.answer("✅ دسته جدید با موفقیت ایجاد شد!", reply_markup=get_admin_main_keyboard())
        else:
            await callback.message.answer("❌ خطا در ایجاد دسته!")
        
        await state.clear()
    
    await callback.answer()

@dp.message(AdminStates.waiting_for_category_password)
async def receive_category_password(message: types.Message, state: FSMContext):
    if message.text == "❌ انصراف":
        await state.clear()
        await message.answer("عملیات لغو شد.", reply_markup=get_admin_main_keyboard())
        return
    
    data = await state.get_data()
    
    # ایجاد دسته رمزدار
    result = await db.add_category(
        name=data['category_name'],
        title=data['category_title'],
        description=data.get('category_desc'),
        is_locked=True,
        password=message.text
    )
    
    if result:
        await message.answer("✅ دسته رمزدار با موفقیت ایجاد شد!", reply_markup=get_admin_main_keyboard())
    else:
        await message.answer("❌ خطا در ایجاد دسته!")
    
    await state.clear()

# --- نمایش دسته‌بندی‌ها برای کاربران ---
@dp.message(F.text == "📚 دسته‌بندی‌ها")
async def show_categories(message: types.Message):
    user = await db.get_user(message.from_user.id)
    if not user or user['status'] != 'approved' or user['is_blocked']:
        await message.answer("❌ شما دسترسی ندارید!")
        return
    
    categories = await db.get_all_categories()
    if not categories:
        await message.answer("هیچ دسته‌ای در دسترس نیست.")
        return
    
    keyboard = []
    for cat in categories:
        icon = "🔐" if cat['is_locked'] else "📁"
        keyboard.append([InlineKeyboardButton(
            text=f"{icon} {cat['title']}", 
            callback_data=f"category_{cat['name']}"
        )])
    
    await message.answer(
        "📚 دسته‌بندی‌های آموزشی:\n\n"
        "🔐 دسته‌های دارای این علامت نیاز به رمز عبور دارند.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )

@dp.callback_query(F.data.startswith("category_"))
async def handle_category_selection(callback: types.CallbackQuery, state: FSMContext):
    category_name = callback.data.replace("category_", "")
    user_id = callback.from_user.id
    
    # بررسی دسترسی
    category = await db.get_category(category_name)
    if not category:
        await callback.answer("دسته یافت نشد!", show_alert=True)
        return
    
    # اگر دسته رمزدار است
    if category['is_locked']:
        has_access = await db.has_category_access(user_id, category_name)
        if not has_access:
            await callback.message.answer(
                f"🔐 دسته «{category['title']}» رمزدار است.\n\n"
                "رمز عبور را وارد کنید:",
                reply_markup=get_cancel_keyboard()
            )
            await state.update_data(locked_category=category_name)
            await state.set_state(UserStates.waiting_for_category_password)
            await callback.answer()
            return
    
    # نمایش محتوای دسته
    await show_category_content(callback.message, category_name, category['title'])
    await callback.answer()

@dp.message(UserStates.waiting_for_category_password)
async def check_category_password(message: types.Message, state: FSMContext):
    if message.text == "❌ انصراف":
        await state.clear()
        await message.answer("عملیات لغو شد.", reply_markup=get_main_keyboard())
        return
    
    data = await state.get_data()
    category_name = data['locked_category']
    
    # بررسی رمز
    is_correct = await db.check_category_password(category_name, message.text)
    if is_correct:
        category = await db.get_category(category_name)
        await db.grant_category_access(message.from_user.id, category['id'])
        await message.answer("✅ رمز صحیح است! دسترسی اعطا شد.")
        await show_category_content(message, category_name, category['title'])
    else:
        await message.answer("❌ رمز اشتباه است! دوباره تلاش کنید:")
        return
    
    await state.clear()

async def show_category_content(message, category_name: str, category_title: str):
    """نمایش محتوای یک دسته"""
    # دریافت زیرمجموعه‌ها
    subcategories = await db.get_subcategories(category_name)
    # دریافت محتوای مستقیم
    direct_content = await db.get_content_by_category(category_name)
    
    keyboard = []
    
    # زیرمجموعه‌ها
    for sub in subcategories:
        keyboard.append([InlineKeyboardButton(
            text=f"📂 {sub['name']}", 
            callback_data=f"subcategory_{category_name}_{sub['id']}"
        )])
    
    # محتوای مستقیم
    for content in direct_content:
        type_icon = "📷" if content['file_type'] == 'photo' else "🎥" if content['file_type'] == 'video' else "📄"
        keyboard.append([InlineKeyboardButton(
            text=f"{type_icon} {content['title']}", 
            callback_data=f"content_{content['id']}"
        )])
    
    if not keyboard:
        await message.answer(f"📁 {category_title}\n\nهنوز محتوایی در این دسته قرار نگرفته است.")
    else:
        await message.answer(
            f"📁 {category_title}\n\nمحتوای موجود:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
        )

# --- نمایش محتوا با محدودیت کپی ---
@dp.callback_query(F.data.startswith("content_"))
async def show_content(callback: types.CallbackQuery):
    content_id = int(callback.data.replace("content_", ""))
    content = await db.get_content(content_id)
    
    if not content:
        await callback.answer("محتوا یافت نشد!", show_alert=True)
        return
    
    caption = f"📚 {content['title']}"
    if content['description']:
        caption += f"\n\n📝 {content['description']}"
    
    caption += "\n\n⚠️ این محتوا قابل کپی یا ذخیره نیست."
    
    try:
        if content['file_type'] == 'photo':
            await bot.send_photo(
                callback.from_user.id,
                photo=content['file_id'],
                caption=caption,
                has_spoiler=False,
                protect_content=True  # جلوگیری از کپی
            )
        elif content['file_type'] == 'video':
            await bot.send_video(
                callback.from_user.id,
                video=content['file_id'],
                caption=caption,
                protect_content=True  # جلوگیری از کپی
            )
        elif content['file_type'] == 'document':
            await bot.send_document(
                callback.from_user.id,
                document=content['file_id'],
                caption=caption,
                protect_content=True  # جلوگیری از کپی
            )
        
        await db.log_activity(callback.from_user.id, "view_content", f"مشاهده محتوا: {content['title']}")
        
    except Exception as e:
        await callback.answer("خطا در ارسال محتوا!", show_alert=True)
        print(f"Error sending content: {e}")
    
    await callback.answer()

# --- مدیریت کاربران توسط ادمین ---
@dp.callback_query(F.data == "pending_users")
async def show_pending_users(callback: types.CallbackQuery):
    if not settings.is_admin(callback.from_user.id):
        await callback.answer("دسترسی ندارید!", show_alert=True)
        return
    
    users = await db.get_pending_users()
    if not users:
        await callback.message.answer("✅ هیچ کاربری در انتظار تایید نیست.")
        return
    
    await callback.message.answer(f"👥 {len(users)} کاربر در انتظار تایید:")
    
    for user in users[:10]:  # نمایش فقط ۱۰ نفر
        text = f"""👤 {user['first_name']} {user['last_name']}
🆔 آیدی: {user['user_id']}
🎯 کد NFT: {user['nft_code']}
💳 ولت: {user['wallet_address'][:30]}...
📅 ثبت نام: {user['join_date'][:16]}"""

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ تایید", callback_data=f"approve_{user['user_id']}"),
                InlineKeyboardButton(text="❌ رد", callback_data=f"reject_{user['user_id']}")
            ],
            [InlineKeyboardButton(text="👤 جزئیات", callback_data=f"view_profile_{user['user_id']}")]
        ])
        
        await callback.message.answer(text, reply_markup=keyboard)
        await asyncio.sleep(0.1)
    
    await callback.answer()

@dp.callback_query(F.data.startswith("approve_"))
async def approve_user(callback: types.CallbackQuery):
    if not settings.is_admin(callback.from_user.id):
        await callback.answer("دسترسی ندارید!", show_alert=True)
        return
    
    user_id = int(callback.data.split("_")[1])
    result = await db.update_user_status(user_id, 'approved')
    
    if result:
        user = await db.get_user(user_id)
        await callback.message.edit_text(f"✅ کاربر {user['first_name']} {user['last_name']} تایید شد.")
        
        # اطلاع به کاربر
        try:
            await bot.send_message(
                user_id,
                "🎉 تبریک! درخواست شما تایید شد.\n\n"
                "اکنون می‌توانید از ربات استفاده کنید.\n"
                "برای شروع دستور /start را ارسال کنید.",
            )
        except:
            pass
        
        await db.log_activity(user_id, "approved", f"تایید شده توسط ادمین {callback.from_user.id}")
    else:
        await callback.answer("خطا در تایید کاربر!", show_alert=True)
    
    await callback.answer()

@dp.callback_query(F.data.startswith("reject_"))
async def reject_user(callback: types.CallbackQuery):
    if not settings.is_admin(callback.from_user.id):
        await callback.answer("دسترسی ندارید!", show_alert=True)
        return
    
    user_id = int(callback.data.split("_")[1])
    result = await db.update_user_status(user_id, 'rejected')
    
    if result:
        user = await db.get_user(user_id)
        await callback.message.edit_text(f"❌ کاربر {user['first_name']} {user['last_name']} رد شد.")
        
        # اطلاع به کاربر
        try:
            await bot.send_message(
                user_id,
                "❌ متاسفانه درخواست شما رد شد.\n\n"
                "برای اطلاعات بیشتر با پشتیبانی تماس بگیرید."
            )
        except:
            pass
        
        await db.log_activity(user_id, "rejected", f"رد شده توسط ادمین {callback.from_user.id}")
    else:
        await callback.answer("خطا در رد کاربر!", show_alert=True)
    
    await callback.answer()

# --- افزودن محتوا ---
@dp.message(F.text == "➕ افزودن محتوا")
@dp.callback_query(F.data == "add_content")
async def add_content_handler(update, state: FSMContext):
    if isinstance(update, types.Message):
        user_id = update.from_user.id
        message = update
    else:
        user_id = update.from_user.id
        message = update.message
    
    if not settings.is_admin(user_id):
        return
    
    await message.answer(
        "📎 افزودن محتوای جدید\n\n"
        "لطفا فایل آموزشی را ارسال کنید:\n\n"
        "فرمت‌های پشتیبانی شده:\n"
        "• عکس (JPG, PNG)\n"
        "• ویدیو (MP4)\n"
        "• سند (PDF, DOC, DOCX)",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(AdminStates.waiting_for_content_file)
    
    if isinstance(update, types.CallbackQuery):
        await update.answer()

# --- پردازش فایل‌های آپلود شده ---
@dp.message(AdminStates.waiting_for_content_file, F.photo)
async def receive_photo_content(message: types.Message, state: FSMContext):
    if not settings.is_admin(message.from_user.id):
        return
    
    file = message.photo[-1]
    file_id = file.file_id
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    file_path = f"{settings.CONTENT_DIR}/photo_{timestamp}.jpg"
    
    os.makedirs(settings.CONTENT_DIR, exist_ok=True)
    await bot.download(file, destination=file_path)
    
    await state.update_data(file_type='photo', file_path=file_path, file_id=file_id)
    await show_category_selection_for_content(message, state)

@dp.message(AdminStates.waiting_for_content_file, F.video)
async def receive_video_content(message: types.Message, state: FSMContext):
    if not settings.is_admin(message.from_user.id):
        return
    
    file = message.video
    file_id = file.file_id
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    file_path = f"{settings.CONTENT_DIR}/video_{timestamp}.mp4"
    
    os.makedirs(settings.CONTENT_DIR, exist_ok=True)
    await bot.download(file, destination=file_path)
    
    await state.update_data(file_type='video', file_path=file_path, file_id=file_id)
    await show_category_selection_for_content(message, state)

@dp.message(AdminStates.waiting_for_content_file, F.document)
async def receive_document_content(message: types.Message, state: FSMContext):
    if not settings.is_admin(message.from_user.id):
        return
    
    file = message.document
    file_id = file.file_id
    file_ext = file.file_name.split('.')[-1] if file.file_name else 'pdf'
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    file_path = f"{settings.CONTENT_DIR}/document_{timestamp}.{file_ext}"
    
    os.makedirs(settings.CONTENT_DIR, exist_ok=True)
    await bot.download(file, destination=file_path)
    
    await state.update_data(file_type='document', file_path=file_path, file_id=file_id)
    await show_category_selection_for_content(message, state)

async def show_category_selection_for_content(message, state):
    """نمایش لیست دسته‌ها برای انتخاب"""
    categories = await db.get_all_categories()
    if not categories:
        await message.answer("هیچ دسته‌ای وجود ندارد! ابتدا دسته ایجاد کنید.")
        await state.clear()
        return
    
    keyboard = []
    for cat in categories:
        keyboard.append([InlineKeyboardButton(
            text=f"📁 {cat['title']}", 
            callback_data=f"cat_{cat['name']}"
        )])
    
    await message.answer(
        "📂 دسته‌بندی را انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
    await state.set_state(AdminStates.waiting_for_category)

@dp.callback_query(AdminStates.waiting_for_category, F.data.startswith("cat_"))
async def select_category_for_content(callback: types.CallbackQuery, state: FSMContext):
    if not settings.is_admin(callback.from_user.id):
        await callback.answer("دسترسی ندارید!", show_alert=True)
        return
    
    category = callback.data.replace("cat_", "")
    await state.update_data(category=category)
    
    # بررسی زیرمجموعه‌ها
    subcategories = await db.get_subcategories(category)
    
    keyboard = []
    if subcategories:
        for sub in subcategories:
            keyboard.append([InlineKeyboardButton(
                text=f"📂 {sub['name']}", 
                callback_data=f"subcat_{sub['id']}"
            )])
    
    keyboard.append([InlineKeyboardButton(text="➕ زیرمجموعه جدید", callback_data="new_subcategory")])
    keyboard.append([InlineKeyboardButton(text="⏩ بدون زیرمجموعه", callback_data="no_subcategory")])
    
    await callback.message.edit_text(
        "📁 زیرمجموعه را انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
    await state.set_state(AdminStates.waiting_for_subcategory_choice)
    await callback.answer()

@dp.callback_query(AdminStates.waiting_for_subcategory_choice)
async def handle_subcategory_choice_for_content(callback: types.CallbackQuery, state: FSMContext):
    if not settings.is_admin(callback.from_user.id):
        await callback.answer("دسترسی ندارید!", show_alert=True)
        return
    
    if callback.data == "new_subcategory":
        await callback.message.answer(
            "📝 نام زیرمجموعه جدید را وارد کنید:",
            reply_markup=get_cancel_keyboard()
        )
        await state.set_state(AdminStates.waiting_for_new_subcategory_name)
    elif callback.data == "no_subcategory":
        await state.update_data(subcategory=None)
        await callback.message.answer(
            "📝 عنوان محتوا را وارد کنید:",
            reply_markup=get_cancel_keyboard()
        )
        await state.set_state(AdminStates.waiting_for_title)
    elif callback.data.startswith("subcat_"):
        subcat_id = int(callback.data.split("_")[1])
        data = await state.get_data()
        subcategories = await db.get_subcategories(data['category'])
        subcategory = next((s for s in subcategories if s['id'] == subcat_id), None)
        
        if subcategory:
            await state.update_data(subcategory=subcategory['name'])
            await callback.message.answer(
                "📝 عنوان محتوا را وارد کنید:",
                reply_markup=get_cancel_keyboard()
            )
            await state.set_state(AdminStates.waiting_for_title)
    
    await callback.answer()

@dp.message(AdminStates.waiting_for_new_subcategory_name)
async def receive_new_subcategory_name_for_content(message: types.Message, state: FSMContext):
    if message.text == "❌ انصراف":
        await state.clear()
        await message.answer("عملیات لغو شد.", reply_markup=get_admin_main_keyboard())
        return
    
    await state.update_data(new_subcategory_name=message.text)
    await message.answer("📄 توضیحات زیرمجموعه را وارد کنید (یا /skip):")
    await state.set_state(AdminStates.waiting_for_new_subcategory_desc)

@dp.message(AdminStates.waiting_for_new_subcategory_desc)
async def receive_new_subcategory_desc_for_content(message: types.Message, state: FSMContext):
    if message.text == "❌ انصراف":
        await state.clear()
        await message.answer("عملیات لغو شد.", reply_markup=get_admin_main_keyboard())
        return
    
    desc = message.text if message.text != "/skip" else ""
    data = await state.get_data()
    
    # ثبت زیرمجموعه
    result = await db.add_subcategory(data['category'], data['new_subcategory_name'], desc)
    if result:
        await state.update_data(subcategory=data['new_subcategory_name'])
        await message.answer("📝 عنوان محتوا را وارد کنید:")
        await state.set_state(AdminStates.waiting_for_title)
    else:
        await message.answer("❌ خطا در ایجاد زیرمجموعه!")
        await state.clear()

@dp.message(AdminStates.waiting_for_title)
async def receive_content_title(message: types.Message, state: FSMContext):
    if message.text == "❌ انصراف":
        await state.clear()
        await message.answer("عملیات لغو شد.", reply_markup=get_admin_main_keyboard())
        return
    
    await state.update_data(title=message.text)
    await message.answer("📝 توضیحات محتوا را وارد کنید (یا /skip):")
    await state.set_state(AdminStates.waiting_for_description)

@dp.message(AdminStates.waiting_for_description)
async def receive_content_description_final(message: types.Message, state: FSMContext):
    if message.text == "❌ انصراف":
        await state.clear()
        await message.answer("عملیات لغو شد.", reply_markup=get_admin_main_keyboard())
        return
    
    desc = message.text if message.text != "/skip" else ""
    data = await state.get_data()
    
    # ثبت محتوا
    content_data = {
        'file_type': data['file_type'],
        'file_path': data['file_path'],
        'file_id': data['file_id'],
        'category': data['category'],
        'subcategory': data.get('subcategory'),
        'title': data['title'],
        'description': desc
    }
    
    result = await db.add_content(content_data)
    if result:
        await message.answer("✅ محتوای جدید با موفقیت اضافه شد!", reply_markup=get_admin_main_keyboard())
        await db.log_activity(message.from_user.id, "add_content", f"افزودن محتوا: {data['title']}")
    else:
        await message.answer("❌ خطا در افزودن محتوا!")
    
    await state.clear()

# --- پیام همگانی ---
@dp.message(F.text == "📨 پیام همگانی")
@dp.callback_query(F.data == "broadcast")
async def broadcast_message_handler(update, state: FSMContext):
    if isinstance(update, types.Message):
        user_id = update.from_user.id
        message = update
    else:
        user_id = update.from_user.id
        message = update.message
    
    if not settings.is_admin(user_id):
        return
    
    await message.answer(
        "📨 ارسال پیام همگانی\n\n"
        "متن پیام خود را بنویسید:",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(AdminStates.waiting_for_broadcast_message)
    
    if isinstance(update, types.CallbackQuery):
        await update.answer()

@dp.message(AdminStates.waiting_for_broadcast_message)
async def send_broadcast_message(message: types.Message, state: FSMContext):
    if message.text == "❌ انصراف":
        await state.clear()
        await message.answer("عملیات لغو شد.", reply_markup=get_admin_main_keyboard())
        return
    
    # دریافت لیست کاربران تایید شده
    approved_users = await db.get_all_users()
    approved_users = [u for u in approved_users if u['status'] == 'approved' and not u['is_blocked']]
    
    if not approved_users:
        await message.answer("هیچ کاربر تایید شده‌ای یافت نشد!")
        await state.clear()
        return
    
    await message.answer(f"📤 در حال ارسال پیام به {len(approved_users)} کاربر...")
    
    sent_count = 0
    failed_count = 0
    
    for user in approved_users:
        try:
            await bot.send_message(user['user_id'], message.text)
            sent_count += 1
            await asyncio.sleep(0.05)  # جلوگیری از محدودیت نرخ
        except Exception as e:
            failed_count += 1
            print(f"خطا در ارسال به {user['user_id']}: {e}")
    
    await message.answer(
        f"✅ ارسال پیام تکمیل شد!\n\n"
        f"✅ موفق: {sent_count}\n"
        f"❌ ناموفق: {failed_count}",
        reply_markup=get_admin_main_keyboard()
    )
    
    await db.log_activity(message.from_user.id, "broadcast", f"پیام همگانی به {sent_count} کاربر")
    await state.clear()

# --- پشتیبانی ---
@dp.message(F.text == "💬 پشتیبانی")
async def user_support_request(message: types.Message, state: FSMContext):
    user = await db.get_user(message.from_user.id)
    if not user or user['status'] != 'approved' or user['is_blocked']:
        await message.answer("❌ شما دسترسی ندارید!")
        return
    
    await message.answer(
        "💬 پشتیبانی\n\n"
        "پیام یا سوال خود را ارسال کنید.\n"
        "ادمین در اسرع وقت پاسخ خواهد داد:",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(UserStates.waiting_for_support_message)

@dp.message(UserStates.waiting_for_support_message)
async def receive_support_message(message: types.Message, state: FSMContext):
    if message.text == "❌ انصراف":
        await state.clear()
        await message.answer("درخواست پشتیبانی لغو شد.", reply_markup=get_main_keyboard())
        return
    
    result = await db.add_support_message(message.from_user.id, message.text)
    if result:
        await message.answer(
            "✅ پیام شما برای ادمین ارسال شد.\n"
            "در اسرع وقت پاسخ داده خواهد شد.",
            reply_markup=get_main_keyboard()
        )
        
        # اطلاع به ادمین‌ها
        user = await db.get_user(message.from_user.id)
        admin_message = f"""💬 پیام پشتیبانی جدید:

👤 {user['first_name']} {user['last_name']}
🆔 {message.from_user.id}
📱 @{message.from_user.username or 'ندارد'}

💬 پیام:
{message.text}

📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}"""

        reply_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✉️ پاسخ", callback_data=f"reply_support_{message.from_user.id}")]
        ])
        
        for admin_id in settings.ADMIN_IDS:
            try:
                await bot.send_message(admin_id, admin_message, reply_markup=reply_keyboard)
            except:
                pass
    else:
        await message.answer("❌ خطا در ارسال پیام!")
    
    await state.clear()

# --- مدیریت پیام‌های پشتیبانی توسط ادمین ---
@dp.message(F.text == "💬 پیام‌های پشتیبانی")
@dp.callback_query(F.data == "support_messages")
async def admin_support_messages(update):
    if isinstance(update, types.Message):
        user_id = update.from_user.id
        message = update
    else:
        user_id = update.from_user.id
        message = update.message
    
    if not settings.is_admin(user_id):
        return
    
    messages = await db.get_recent_support_messages(15)
    if not messages:
        await message.answer("📭 پیام پشتیبانی‌ای وجود ندارد.")
        return
    
    await message.answer(f"💬 {len(messages)} پیام پشتیبانی اخیر:")
    
    for msg in messages:
        status_icon = "✅" if msg['is_read'] else "🔴"
        user = await db.get_user(msg['user_id'])
        user_name = f"{user['first_name']} {user['last_name']}" if user else "کاربر حذف شده"
        
        text = f"""{status_icon} {user_name}
🆔 {msg['user_id']}
💬 {msg['message'][:100]}...
📅 {msg['created_at'][:16]}"""

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✉️ پاسخ", callback_data=f"reply_support_{msg['user_id']}")]
        ])
        
        if not msg['is_read']:
            keyboard.inline_keyboard[0].append(
                InlineKeyboardButton(text="✓ خوانده شد", callback_data=f"mark_read_{msg['id']}")
            )
        
        await message.answer(text, reply_markup=keyboard)
        await asyncio.sleep(0.1)
    
    if isinstance(update, types.CallbackQuery):
        await update.answer()

@dp.callback_query(F.data.startswith("reply_support_"))
async def admin_reply_to_support(callback: types.CallbackQuery, state: FSMContext):
    if not settings.is_admin(callback.from_user.id):
        await callback.answer("دسترسی ندارید!", show_alert=True)
        return
    
    user_id = int(callback.data.split("_")[2])
    user = await db.get_user(user_id)
    
    if not user:
        await callback.answer("کاربر یافت نشد!", show_alert=True)
        return
    
    await state.update_data(support_reply_user_id=user_id)
    await callback.message.answer(
        f"✉️ پاسخ به {user['first_name']} {user['last_name']}\n\n"
        "متن پاسخ خود را بنویسید:",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(AdminStates.waiting_for_admin_reply)
    await callback.answer()

@dp.message(AdminStates.waiting_for_admin_reply)
async def send_admin_support_reply(message: types.Message, state: FSMContext):
    if message.text == "❌ انصراف":
        await state.clear()
        await message.answer("عملیات لغو شد.", reply_markup=get_admin_main_keyboard())
        return
    
    data = await state.get_data()
    user_id = data.get("support_reply_user_id")
    
    if not user_id:
        await message.answer("خطا در دریافت اطلاعات!")
        await state.clear()
        return
    
    try:
        await bot.send_message(
            user_id,
            f"📩 پاسخ پشتیبانی:\n\n{message.text}\n\n"
            "برای سوال جدید از منوی پشتیبانی استفاده کنید."
        )
        await message.answer("✅ پاسخ با موفقیت ارسال شد!", reply_markup=get_admin_main_keyboard())
        await db.log_activity(message.from_user.id, "support_reply", f"پاسخ به کاربر {user_id}")
    except Exception as e:
        await message.answer(f"❌ خطا در ارسال پاسخ: {str(e)}")
    
    await state.clear()

@dp.callback_query(F.data.startswith("mark_read_"))
async def mark_support_message_read(callback: types.CallbackQuery):
    if not settings.is_admin(callback.from_user.id):
        await callback.answer("دسترسی ندارید!", show_alert=True)
        return
    
    message_id = int(callback.data.split("_")[2])
    result = await db.mark_support_message_read(message_id)
    
    if result:
        await callback.answer("✅ به عنوان خوانده شده علامت‌گذاری شد.")
    else:
        await callback.answer("❌ خطا در علامت‌گذاری!")

# --- پروفایل کاربر ---
@dp.message(F.text == "👤 پروفایل من")
async def show_user_profile(message: types.Message):
    user = await db.get_user(message.from_user.id)
    if not user or user['status'] != 'approved' or user['is_blocked']:
        await message.answer("❌ شما دسترسی ندارید!")
        return
    
    profile_text = f"""👤 پروفایل شما:

🆔 آیدی: {user['user_id']}
👤 نام: {user['first_name']} {user['last_name']}
🎯 کد NFT: {user['nft_code']}
💳 ولت: {user['wallet_address'][:20]}...
📅 عضویت: {user['join_date'][:10]}
⏰ آخرین فعالیت: {user['last_activity'][:16]}
✅ وضعیت: {'تایید شده' if user['status'] == 'approved' else user['status']}"""

    await message.answer(profile_text)

# --- لغو عملیات ---
@dp.message(F.text == "❌ انصراف")
async def cancel_operation(message: types.Message, state: FSMContext):
    await state.clear()
    
    if settings.is_admin(message.from_user.id):
        await message.answer("عملیات لغو شد.", reply_markup=get_admin_main_keyboard())
    else:
        await message.answer("عملیات لغو شد.", reply_markup=get_main_keyboard())

@dp.message(F.text == "🔙 بازگشت به منوی اصلی")
async def back_to_main_menu(message: types.Message, state: FSMContext):
    await state.clear()
    
    if settings.is_admin(message.from_user.id):
        await message.answer("🔙 بازگشت به منوی اصلی", reply_markup=get_admin_main_keyboard())
    else:
        user = await db.get_user(message.from_user.id)
        if user and user['status'] == 'approved' and not user['is_blocked']:
            await message.answer("🔙 بازگشت به منوی اصلی", reply_markup=get_main_keyboard())

# --- آمار کلی ---
@dp.callback_query(F.data == "statistics")
async def show_full_statistics(callback: types.CallbackQuery):
    if not settings.is_admin(callback.from_user.id):
        await callback.answer("دسترسی ندارید!", show_alert=True)
        return
    
    stats = await db.get_statistics()
    categories = await db.get_all_categories()
    
    stats_text = f"""📊 آمار کامل سیستم:

👥 کاربران:
├─ کل: {stats['total_users']}
├─ تایید شده: {stats['approved_users']}
├─ در انتظار: {stats['pending_users']}
└─ مسدود شده: {stats['blocked_users']}

📚 محتوا و دسته‌ها:
├─ کل محتوا: {stats['total_content']}
├─ تعداد دسته: {len(categories)}
└─ دسته‌های رمزدار: {len([c for c in categories if c['is_locked']])}

📊 فعالیت:
└─ فعالیت امروز: {stats['today_activities']}

🕐 تاریخ گزارش: {datetime.now().strftime('%Y-%m-%d %H:%M')}"""

    await callback.message.answer(stats_text)
    await callback.answer()

# --- شروع ربات ---
async def main():
    await db.init_db()
    print("🚀 ربات آموزشی راه‌اندازی شد...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
