import asyncio
import os
import logging
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
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from config import settings
from database import Database
from security import Security

# راه‌اندازی لاگینگ
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f"{settings.LOG_DIR}/bot.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

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
    waiting_for_category_name = State()
    waiting_for_category_title = State()
    waiting_for_category_desc = State()
    waiting_for_category_password = State()
    waiting_for_user_id_grant = State()
    waiting_for_new_category_name = State()
    waiting_for_new_category_title = State()
    waiting_for_new_category_desc = State()
    waiting_for_new_category_password = State()
    waiting_for_content_edit_title = State()
    waiting_for_content_edit_desc = State()
    waiting_for_category_icon = State()

class UserStates(StatesGroup):
    waiting_for_support_message = State()
    waiting_for_category_password = State()

# --- راه اندازی ---
bot = Bot(token=settings.BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
db = Database()
security = Security(db)

# --- توابع کمکی ---
async def safe_send_message(chat_id: int, text: str, **kwargs) -> Optional[types.Message]:
    """ارسال ایمن پیام"""
    try:
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

async def safe_send_protected_content(chat_id: int, content: Dict, caption: str = "") -> Optional[types.Message]:
    """ارسال محتوای محافظت شده"""
    try:
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

def ensure_directory_exists(directory_path: str):
    """اطمینان از وجود پوشه"""
    try:
        from pathlib import Path
        Path(directory_path).mkdir(parents=True, exist_ok=True)
        return True
    except Exception as e:
        print(f"خطا در ایجاد پوشه {directory_path}: {e}")
        return False

# --- کیبوردها ---
def get_cancel_keyboard():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="❌ انصراف")]], resize_keyboard=True)

def get_back_keyboard():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🔙 بازگشت به منوی اصلی")]], resize_keyboard=True)

async def get_user_main_keyboard(user_id: int) -> ReplyKeyboardMarkup:
    """ایجاد کیبورد دینامیک بر اساس دسترسی کاربر"""
    try:
        categories = await db.get_all_categories()
        keyboard_buttons = []
        current_row = []

        # اضافه کردن دکمه‌های دسته‌ها
        for category in categories:
            icon = category.get('icon', '📁')
            title = category['title']

            # اگر دسته قفل‌دار است، بررسی دسترسی کاربر
            if category.get('is_locked', False):
                has_access = await db.has_category_access(user_id, category['name'])
                if has_access:
                    button_text = f"🔓 {icon} {title}"
                else:
                    button_text = f"🔒 {icon} {title}"
            else:
                button_text = f"{icon} {title}"

            current_row.append(KeyboardButton(text=button_text))

            # اگر ردیف پر شد، به کیبورد اضافه کن و ردیف جدید شروع کن
            if len(current_row) == 2:
                keyboard_buttons.append(current_row)
                current_row = []

        # اگر دکمه‌ای در ردیف آخر باقی مانده
        if current_row:
            keyboard_buttons.append(current_row)

        # اضافه کردن دکمه‌های ثابت
        keyboard_buttons.append([KeyboardButton(text="👤 پروفایل من")])
        keyboard_buttons.append([KeyboardButton(text="💬 پشتیبانی")])

        return ReplyKeyboardMarkup(keyboard=keyboard_buttons, resize_keyboard=True)
        
    except Exception as e:
        logger.error(f"خطا در ایجاد کیبورد کاربر: {e}")
        # fallback به کیبورد پیش‌فرض
        return ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="📚 آموزش نگرش"), KeyboardButton(text="🔗 آموزش بلاکچین")],
                [KeyboardButton(text="👥 آموزش رفرال"), KeyboardButton(text="👤 پروفایل من")],
                [KeyboardButton(text="💬 پشتیبانی")]
            ],
            resize_keyboard=True
        )

def get_admin_main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔧 پنل مدیریت")],
            [KeyboardButton(text="📊 آمار سریع"), KeyboardButton(text="👥 کاربران جدید")],
            [KeyboardButton(text="➕ افزودن محتوا"), KeyboardButton(text="📝 مدیریت محتوا")],
            [KeyboardButton(text="📂 مدیریت دسته‌ها"), KeyboardButton(text="🔒 مدیریت دسترسی")],
            [KeyboardButton(text="💬 پیام‌های پشتیبانی"), KeyboardButton(text="📨 پیام همگانی")]
        ],
        resize_keyboard=True
    )

def get_admin_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 کاربران در انتظار تایید", callback_data="pending_users")],
        [InlineKeyboardButton(text="📊 آمار کلی", callback_data="statistics")],
        [InlineKeyboardButton(text="👤 لیست کاربران", callback_data="users_list")],
        [InlineKeyboardButton(text="➕ افزودن محتوا", callback_data="add_content")],
        [InlineKeyboardButton(text="📝 مدیریت محتوا", callback_data="manage_content")],
        [InlineKeyboardButton(text="📂 مدیریت دسته‌ها", callback_data="manage_categories")],
        [InlineKeyboardButton(text="🔒 مدیریت دسترسی", callback_data="manage_access")],
        [InlineKeyboardButton(text="📂 مدیریت زیرمجموعه‌ها", callback_data="manage_subcategories")],
        [InlineKeyboardButton(text="📨 پیام همگانی", callback_data="broadcast")],
        [InlineKeyboardButton(text="🔍 جستجوی کاربر", callback_data="search_user")],
        [InlineKeyboardButton(text="💬 پیام‌های پشتیبانی", callback_data="support_messages")]
    ])

def get_support_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✉️ ارسال پیام جدید", callback_data="new_support_message")],
        [InlineKeyboardButton(text="📞 راه‌های ارتباطی", callback_data="contact_info")],
        [InlineKeyboardButton(text="❓ سوالات متداول", callback_data="faq")],
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data="back_to_main")]
    ])

# --- مدیریت انصراف ---
async def handle_cancel(message: types.Message, state: FSMContext) -> bool:
    """مدیریت انصراف در همه state ها"""
    if message.text == "❌ انصراف":
        await state.clear()
        if settings.is_admin(message.from_user.id):
            await message.answer("عملیات لغو شد.", reply_markup=get_admin_main_keyboard())
        else:
            keyboard = await get_user_main_keyboard(message.from_user.id)
            await message.answer("عملیات لغو شد.", reply_markup=keyboard)
        return True
    return False

# --- هندلر start ---
@dp.message(Command("start"))
async def start_handler(message: types.Message, state: FSMContext):
    await state.clear()

    if settings.is_admin(message.from_user.id):
        await message.answer(
            f"👋 سلام ادمین عزیز!\nشما به عنوان مدیر سیستم شناخته شده‌اید.\nاز منوی زیر استفاده کنید:",
            reply_markup=get_admin_main_keyboard()
        )
        await db.log_activity(message.from_user.id, "admin_start", "ورود ادمین")
        return

    user = await db.get_user(message.from_user.id)
    if user:
        if user['status'] == 'approved':
            keyboard = await get_user_main_keyboard(message.from_user.id)
            await message.answer(
                f"سلام {user['first_name']} عزیز! 👋\nبه ربات آموزشی خوش آمدید. از منوی زیر استفاده کنید:",
                reply_markup=keyboard
            )
            await db.update_last_activity(message.from_user.id)
        elif user['status'] == 'pending':
            await message.answer("⏳ درخواست شما در حال بررسی است.\nلطفا صبور باشید.")
        elif user['status'] == 'rejected':
            await message.answer("❌ متاسفانه درخواست شما رد شده است.\nبرای اطلاعات بیشتر با پشتیبانی تماس بگیرید.")
        else:
            await message.answer("❌ دسترسی شما محدود شده است.")
    else:
        await message.answer(
            settings.WELCOME_MESSAGE + "\n\nبرای ثبت نام، اطلاعات زیر را به ترتیب وارد کنید."
        )
        await message.answer("لطفا نام خود را وارد کنید:", reply_markup=get_cancel_keyboard())
        await state.set_state(RegistrationStates.waiting_for_name)
        await db.log_activity(message.from_user.id, "start", "شروع ثبت نام")

# --- ثبت نام ---
@dp.message(RegistrationStates.waiting_for_name)
async def process_name(message: types.Message, state: FSMContext):
    if await handle_cancel(message, state):
        return

    if len(message.text) < 2 or len(message.text) > 50:
        await message.answer("❌ نام باید بین 2 تا 50 کاراکتر باشد. لطفا دوباره وارد کنید:")
        return

    await state.update_data(first_name=message.text)
    await message.answer("لطفا نام خانوادگی خود را وارد کنید:")
    await state.set_state(RegistrationStates.waiting_for_lastname)

@dp.message(RegistrationStates.waiting_for_lastname)
async def process_lastname(message: types.Message, state: FSMContext):
    if await handle_cancel(message, state):
        return

    if len(message.text) < 2 or len(message.text) > 50:
        await message.answer("❌ نام خانوادگی باید بین 2 تا 50 کاراکتر باشد. لطفا دوباره وارد کنید:")
        return

    await state.update_data(last_name=message.text)
    await message.answer("لطفا کد NFT خود را وارد کنید:")
    await state.set_state(RegistrationStates.waiting_for_nft_code)

@dp.message(RegistrationStates.waiting_for_nft_code)
async def process_nft_code(message: types.Message, state: FSMContext):
    if await handle_cancel(message, state):
        return

    await state.update_data(nft_code=message.text)
    await message.answer("لطفا آدرس ولت خود را وارد کنید:")
    await state.set_state(RegistrationStates.waiting_for_wallet)

@dp.message(RegistrationStates.waiting_for_wallet)
async def process_wallet(message: types.Message, state: FSMContext):
    if await handle_cancel(message, state):
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
            "✅ ثبت نام شما با موفقیت انجام شد!\n\n⏳ درخواست شما در انتظار بررسی ادمین است.\nبه محض تایید، اطلاع رسانی خواهد شد.",
            reply_markup=types.ReplyKeyboardRemove()
        )

        admin_message = f"""🆕 درخواست ثبت نام جدید:

👤 نام: {data['first_name']} {data['last_name']}
🆔 آیدی: {message.from_user.id}
📱 یوزرنیم: @{message.from_user.username or 'ندارد'}
🎯 کد NFT: {data['nft_code']}
💳 آدرس ولت: {message.text}
📅 زمان: {datetime.now().strftime('%Y-%m-%d %H:%M')}"""

        approve_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ تایید", callback_data=f"approve_{message.from_user.id}"),
             InlineKeyboardButton(text="❌ رد", callback_data=f"reject_{message.from_user.id}")],
            [InlineKeyboardButton(text="👤 مشاهده پروفایل", callback_data=f"view_profile_{message.from_user.id}")]
        ])

        for admin_id in settings.ADMIN_IDS:
            await safe_send_message(admin_id, admin_message, reply_markup=approve_keyboard)

        await db.log_activity(message.from_user.id, "registration", "تکمیل ثبت نام")
    else:
        await message.answer(
            "❌ خطا در ثبت نام!\nلطفا دوباره با دستور /start تلاش کنید.",
            reply_markup=types.ReplyKeyboardRemove()
        )

    await state.clear()

# --- callbacks تایید/رد ---
@dp.callback_query(F.data.startswith("approve_"))
async def approve_user(callback: types.CallbackQuery):
    if not settings.is_admin(callback.from_user.id):
        await callback.answer("دسترسی ندارید!", show_alert=True)
        return

    user_id = int(callback.data.split("_")[1])
    success = await db.update_user_status(user_id, "approved")

    if success:
        keyboard = await get_user_main_keyboard(user_id)
        await safe_send_message(
            user_id,
            "🎉 تبریک! درخواست شما تایید شد.\nاکنون می‌توانید از تمام امکانات ربات استفاده کنید.",
            reply_markup=keyboard
        )

        await callback.message.edit_text(
            callback.message.text + f"\n\n✅ توسط {callback.from_user.first_name} تایید شد."
        )
        await db.log_activity(user_id, "approved", f"توسط ادمین {callback.from_user.id}")
    else:
        await callback.answer("خطا در تایید کاربر!", show_alert=True)

@dp.callback_query(F.data.startswith("reject_"))
async def reject_user(callback: types.CallbackQuery):
    if not settings.is_admin(callback.from_user.id):
        await callback.answer("دسترسی ندارید!", show_alert=True)
        return

    user_id = int(callback.data.split("_")[1])
    success = await db.update_user_status(user_id, "rejected")

    if success:
        await safe_send_message(
            user_id,
            "❌ متاسفانه درخواست شما رد شد.\nبرای اطلاعات بیشتر با پشتیبانی تماس بگیرید."
        )
        await callback.message.edit_text(
            callback.message.text + f"\n\n❌ توسط {callback.from_user.first_name} رد شد."
        )
        await db.log_activity(user_id, "rejected", f"توسط ادمین {callback.from_user.id}")
    else:
        await callback.answer("خطا در رد کاربر!", show_alert=True)

# --- ورود به پنل مدیریت ---
@dp.message(Command("panel"))
async def admin_panel(message: types.Message):
    if not settings.is_admin(message.from_user.id):
        await message.answer("❌ شما به این بخش دسترسی ندارید.")
        return

    await message.answer(
        "🔧 پنل مدیریت ربات\n\nاز گزینه‌های زیر استفاده کنید:",
        reply_markup=get_admin_keyboard()
    )

@dp.message(F.text == "🔧 پنل مدیریت")
async def admin_panel_button(message: types.Message):
    if not settings.is_admin(message.from_user.id):
        await message.answer("❌ شما به این بخش دسترسی ندارید.")
        return
    await admin_panel(message)

# --- آمار سریع برای ادمین ---
@dp.message(F.text == "📊 آمار سریع")
async def quick_stats(message: types.Message):
    if not settings.is_admin(message.from_user.id):
        await message.answer("❌ شما به این بخش دسترسی ندارید.")
        return

    try:
        stats = await db.get_statistics()
        stats_text = f"""📊 آمار سریع:

👥 کل کاربران: {stats.get('total_users', 0)}
✅ تایید شده: {stats.get('approved_users', 0)}
⏳ در انتظار: {stats.get('pending_users', 0)}
🚫 مسدود شده: {stats.get('blocked_users', 0)}
📚 تعداد محتوا: {stats.get('total_content', 0)}
📈 فعالیت امروز: {stats.get('today_activities', 0)}

📅 آخرین بروزرسانی: {datetime.now().strftime('%Y-%m-%d %H:%M')}"""

        await message.answer(stats_text)
    except Exception as e:
        logger.error(f"خطا در دریافت آمار: {e}")
        await message.answer("❌ خطا در دریافت آمار. لطفا دوباره تلاش کنید.")

# --- نمایش کاربران جدید تایید نشده ---
@dp.message(F.text == "👥 کاربران جدید")
async def new_users_button(message: types.Message):
    if not settings.is_admin(message.from_user.id):
        await message.answer("❌ شما به این بخش دسترسی ندارید.")
        return

    try:
        users = await db.get_pending_users()
        if not users:
            await message.answer("✅ هیچ کاربری در انتظار تایید نیست.")
            return

        await message.answer(f"👥 {len(users)} کاربر در انتظار تایید:")

        for user in users[:10]:
            text = f"""👤 {user['first_name']} {user['last_name']}
🆔 آیدی: {user['user_id']}
🎯 کد NFT: {user['nft_code']}
💳 ولت: {user['wallet_address'][:20]}...
📅 ثبت نام: {user['join_date'][:10]}"""

            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✅ تایید", callback_data=f"approve_{user['user_id']}"),
                 InlineKeyboardButton(text="❌ رد", callback_data=f"reject_{user['user_id']}")],
                [InlineKeyboardButton(text="👤 پروفایل", callback_data=f"view_profile_{user['user_id']}")]
            ])

            await message.answer(text, reply_markup=keyboard)
            await asyncio.sleep(0.1)

    except Exception as e:
        logger.error(f"خطا در دریافت کاربران جدید: {e}")
        await message.answer("❌ خطا در دریافت اطلاعات کاربران.")

# --- افزودن محتوا ---
@dp.message(F.text == "➕ افزودن محتوا")
async def add_content_button(message: types.Message, state: FSMContext):
    if not settings.is_admin(message.from_user.id):
        await message.answer("❌ شما به این بخش دسترسی ندارید.")
        return

    await message.answer(
        "📎 لطفا فایل آموزشی را ارسال کنید:\n\nفرمت‌های پشتیبانی شده:\n• عکس (JPG, PNG)\n• ویدیو (MP4)\n• سند (PDF, DOC)",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(AdminStates.waiting_for_content_file)

# --- دریافت فایل‌های محتوا ---
@dp.message(AdminStates.waiting_for_content_file, F.photo)
async def receive_photo_content(message: types.Message, state: FSMContext):
    if not settings.is_admin(message.from_user.id):
        return

    file = message.photo[-1]
    file_id = file.file_id
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    file_path = f"{settings.CONTENT_DIR}/photo_{timestamp}.jpg"

    ensure_directory_exists(settings.CONTENT_DIR)
    await bot.download(file, destination=file_path)
    await state.update_data(file_type='photo', file_path=file_path, file_id=file_id)

    categories = await db.get_all_categories()
    keyboard = []
    for cat in categories:
        keyboard.append([InlineKeyboardButton(text=f"{cat.get('icon', '📁')} {cat['title']}", callback_data=f"cat_{cat['name']}")])

    await message.answer("📂 دسته‌بندی را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))
    await state.set_state(AdminStates.waiting_for_category)

@dp.message(AdminStates.waiting_for_content_file, F.video)
async def receive_video_content(message: types.Message, state: FSMContext):
    if not settings.is_admin(message.from_user.id):
        return

    file = message.video
    file_id = file.file_id
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    file_path = f"{settings.CONTENT_DIR}/video_{timestamp}.mp4"

    ensure_directory_exists(settings.CONTENT_DIR)
    await bot.download(file, destination=file_path)
    await state.update_data(file_type='video', file_path=file_path, file_id=file_id)

    categories = await db.get_all_categories()
    keyboard = []
    for cat in categories:
        keyboard.append([InlineKeyboardButton(text=f"{cat.get('icon', '📁')} {cat['title']}", callback_data=f"cat_{cat['name']}")])

    await message.answer("📂 دسته‌بندی را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))
    await state.set_state(AdminStates.waiting_for_category)

@dp.message(AdminStates.waiting_for_content_file, F.document)
async def receive_document_content(message: types.Message, state: FSMContext):
    if not settings.is_admin(message.from_user.id):
        return

    file = message.document
    file_id = file.file_id
    file_ext = file.file_name.split('.')[-1] if file.file_name else 'pdf'
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    file_path = f"{settings.CONTENT_DIR}/document_{timestamp}.{file_ext}"

    ensure_directory_exists(settings.CONTENT_DIR)
    await bot.download(file, destination=file_path)
    await state.update_data(file_type='document', file_path=file_path, file_id=file_id)

    categories = await db.get_all_categories()
    keyboard = []
    for cat in categories:
        keyboard.append([InlineKeyboardButton(text=f"{cat.get('icon', '📁')} {cat['title']}", callback_data=f"cat_{cat['name']}")])

    await message.answer("📂 دسته‌بندی را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))
    await state.set_state(AdminStates.waiting_for_category)

@dp.message(AdminStates.waiting_for_content_file)
async def handle_cancel_in_content(message: types.Message, state: FSMContext):
    if await handle_cancel(message, state):
        return
    await message.answer("لطفا یک فایل (عکس، ویدیو یا سند) ارسال کنید.")

# --- انتخاب دسته و زیرمجموعه ---
@dp.callback_query(AdminStates.waiting_for_category, F.data.startswith("cat_"))
async def category_selected(callback: types.CallbackQuery, state: FSMContext):
    category = callback.data.replace("cat_", "")
    await state.update_data(category=category)

    subcategories = await db.get_subcategories(category)
    if subcategories:
        keyboard = []
        for sub in subcategories:
            keyboard.append([InlineKeyboardButton(text=f"📁 {sub['name']}", callback_data=f"sub_{sub['name']}")])
        keyboard.append([InlineKeyboardButton(text="📄 محتوای اصلی دسته", callback_data="main_category")])

        await callback.message.answer("📁 زیرمجموعه را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))
        await state.set_state(AdminStates.waiting_for_subcategory)
    else:
        await callback.message.answer("📝 عنوان محتوا را وارد کنید:", reply_markup=get_cancel_keyboard())
        await state.set_state(AdminStates.waiting_for_title)

    await callback.answer()

@dp.callback_query(AdminStates.waiting_for_subcategory, F.data.startswith("sub_"))
async def subcategory_selected(callback: types.CallbackQuery, state: FSMContext):
    subcategory = callback.data.replace("sub_", "")
    await state.update_data(subcategory=subcategory)
    await callback.message.answer("📝 عنوان محتوا را وارد کنید:", reply_markup=get_cancel_keyboard())
    await state.set_state(AdminStates.waiting_for_title)
    await callback.answer()

@dp.callback_query(AdminStates.waiting_for_subcategory, F.data == "main_category")
async def main_category_selected(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(subcategory=None)
    await callback.message.answer("📝 عنوان محتوا را وارد کنید:", reply_markup=get_cancel_keyboard())
    await state.set_state(AdminStates.waiting_for_title)
    await callback.answer()

@dp.message(AdminStates.waiting_for_title)
async def process_content_title(message: types.Message, state: FSMContext):
    if await handle_cancel(message, state):
        return

    await state.update_data(title=message.text)
    await message.answer("📄 توضیحات محتوا را وارد کنید (اختیاری - برای رد کردن 'خیر' بنویسید):")
    await state.set_state(AdminStates.waiting_for_description)

@dp.message(AdminStates.waiting_for_description)
async def process_content_description(message: types.Message, state: FSMContext):
    if await handle_cancel(message, state):
        return

    data = await state.get_data()
    description = None if message.text.lower() in ['خیر', 'نه', 'no'] else message.text

    content_data = {
        'title': data['title'],
        'description': description,
        'file_type': data['file_type'],
        'file_path': data['file_path'],
        'file_id': data['file_id'],
        'category': data['category'],
        'subcategory': data.get('subcategory'),
        'uploaded_by': message.from_user.id
    }

    success = await db.add_content(content_data)

    if success:
        await message.answer(
            f"✅ محتوا '{data['title']}' با موفقیت اضافه شد!",
            reply_markup=get_admin_main_keyboard()
        )
        await db.log_activity(message.from_user.id, "add_content", f"افزودن محتوا: {data['title']}")
    else:
        await message.answer("❌ خطا در افزودن محتوا!", reply_markup=get_admin_main_keyboard())

    await state.clear()

# === مدیریت دسته‌ها ===
@dp.message(F.text == "📂 مدیریت دسته‌ها")
async def manage_categories_button(message: types.Message):
    if not settings.is_admin(message.from_user.id):
        await message.answer("❌ شما به این بخش دسترسی ندارید.")
        return
    
    categories = await db.get_all_categories()
    
    keyboard = []
    for cat in categories:
        lock_emoji = "🔒" if cat.get('is_locked', False) else "🔓"
        keyboard.append([InlineKeyboardButton(
            text=f"{lock_emoji} {cat['title']}", 
            callback_data=f"edit_cat_{cat['name']}"
        )])
    
    keyboard.append([InlineKeyboardButton(text="➕ ایجاد دسته جدید", callback_data="new_category")])
    keyboard.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin_back")])
    
    await message.answer(
        "📂 مدیریت دسته‌ها:\n\n🔒 = رمزدار\n🔓 = آزاد",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )

@dp.callback_query(F.data == "manage_categories")
async def manage_categories_callback(callback: types.CallbackQuery):
    if not settings.is_admin(callback.from_user.id):
        await callback.answer("دسترسی ندارید!", show_alert=True)
        return
    
    categories = await db.get_all_categories()
    
    keyboard = []
    for cat in categories:
        lock_emoji = "🔒" if cat.get('is_locked', False) else "🔓"
        keyboard.append([InlineKeyboardButton(
            text=f"{lock_emoji} {cat['title']}", 
            callback_data=f"edit_cat_{cat['name']}"
        )])
    
    keyboard.append([InlineKeyboardButton(text="➕ ایجاد دسته جدید", callback_data="new_category")])
    keyboard.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin_back")])
    
    await callback.message.answer(
        "📂 مدیریت دسته‌ها:\n\n🔒 = رمزدار\n🔓 = آزاد",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
    await callback.answer()

# --- ایجاد دسته جدید ---
@dp.callback_query(F.data == "new_category")
async def new_category_start(callback: types.CallbackQuery, state: FSMContext):
    if not settings.is_admin(callback.from_user.id):
        await callback.answer("دسترسی ندارید!", show_alert=True)
        return
    
    await callback.message.answer(
        "📝 نام انگلیسی دسته جدید را وارد کنید:\n(مثال: programming)",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(AdminStates.waiting_for_new_category_name)
    await callback.answer()

@dp.message(AdminStates.waiting_for_new_category_name)
async def process_new_category_name(message: types.Message, state: FSMContext):
    if await handle_cancel(message, state):
        return
    
    name = message.text.lower().strip()
    
    if not name.replace('_', '').isalnum():
        await message.answer("❌ نام فقط باید شامل حروف انگلیسی و _ باشد:")
        return
    
    existing = await db.get_category(name)
    if existing:
        await message.answer("❌ این نام قبلاً استفاده شده است. نام دیگری انتخاب کنید:")
        return
    
    await state.update_data(category_name=name)
    await message.answer("📝 عنوان فارسی دسته را وارد کنید:")
    await state.set_state(AdminStates.waiting_for_new_category_title)

@dp.message(AdminStates.waiting_for_new_category_title)
async def process_new_category_title(message: types.Message, state: FSMContext):
    if await handle_cancel(message, state):
        return
    
    await state.update_data(category_title=message.text)
    await message.answer("📄 توضیحات دسته را وارد کنید (اختیاری - برای رد کردن 'خیر' بنویسید):")
    await state.set_state(AdminStates.waiting_for_new_category_desc)

@dp.message(AdminStates.waiting_for_new_category_desc)
async def process_new_category_desc(message: types.Message, state: FSMContext):
    if await handle_cancel(message, state):
        return
    
    desc = None if message.text.lower() in ['خیر', 'نه', 'no'] else message.text
    await state.update_data(category_desc=desc)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔓 دسته آزاد", callback_data="cat_type_open")],
        [InlineKeyboardButton(text="🔒 دسته رمزدار", callback_data="cat_type_locked")],
        [InlineKeyboardButton(text="❌ انصراف", callback_data="admin_back")]
    ])
    
    await message.answer("🔐 نوع دسته را انتخاب کنید:", reply_markup=keyboard)

@dp.callback_query(F.data == "cat_type_open")
async def create_open_category(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    
    success = await db.add_category(
        name=data['category_name'],
        title=data['category_title'],
        description=data.get('category_desc'),
        icon='📁',
        is_locked=False
    )
    
    if success:
        await callback.message.answer(f"✅ دسته آزاد '{data['category_title']}' با موفقیت ایجاد شد!")
        await db.log_activity(callback.from_user.id, "create_category", f"ایجاد دسته آزاد: {data['category_name']}")
    else:
        await callback.message.answer("❌ خطا در ایجاد دسته!")
    
    await state.clear()
    await callback.answer()

@dp.callback_query(F.data == "cat_type_locked")
async def create_locked_category_ask_password(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "🔒 رمز عبور برای دسته رمزدار را وارد کنید:",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(AdminStates.waiting_for_new_category_password)
    await callback.answer()

@dp.message(AdminStates.waiting_for_new_category_password)
async def process_new_category_password(message: types.Message, state: FSMContext):
    if await handle_cancel(message, state):
        return
    
    data = await state.get_data()
    
    success = await db.add_category(
        name=data['category_name'],
        title=data['category_title'],
        description=data.get('category_desc'),
        icon='🔒',
        is_locked=True,
        password=message.text
    )
    
    if success:
        await message.answer(
            f"✅ دسته رمزدار '{data['category_title']}' با موفقیت ایجاد شد!\n🔑 رمز: {message.text}",
            reply_markup=get_admin_main_keyboard()
        )
        await db.log_activity(message.from_user.id, "create_category", f"ایجاد دسته رمزدار: {data['category_name']}")
    else:
        await message.answer("❌ خطا در ایجاد دسته!", reply_markup=get_admin_main_keyboard())
    
    await state.clear()

# --- ویرایش دسته ---
@dp.callback_query(F.data.startswith("edit_cat_"))
async def edit_category(callback: types.CallbackQuery):
    if not settings.is_admin(callback.from_user.id):
        await callback.answer("دسترسی ندارید!", show_alert=True)
        return
    
    category_name = callback.data.replace("edit_cat_", "")
    category = await db.get_category(category_name)
    
    if not category:
        await callback.answer("دسته یافت نشد!", show_alert=True)
        return
    
    lock_status = "🔒 رمزدار" if category.get('is_locked', False) else "🔓 آزاد"
    
    text = f"""📂 ویرایش دسته: {category['title']}

🆔 نام: {category['name']}
📝 توضیحات: {category.get('description', 'ندارد')}
🔐 وضعیت: {lock_status}
📅 ایجاد: {category['created_date'][:10]}"""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔐 تغییر رمز", callback_data=f"change_pass_{category_name}")],
        [InlineKeyboardButton(text="🔓/🔒 تغییر وضعیت", callback_data=f"toggle_lock_{category_name}")],
        [InlineKeyboardButton(text="👥 مدیریت دسترسی", callback_data=f"manage_access_{category_name}")],
        [InlineKeyboardButton(text="🗑 حذف دسته", callback_data=f"delete_cat_{category_name}")],
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data="manage_categories")]
    ])
    
    await callback.message.answer(text, reply_markup=keyboard)
    await callback.answer()

# --- مدیریت دسترسی ---
@dp.message(F.text == "🔒 مدیریت دسترسی")
async def manage_access_button(message: types.Message):
    if not settings.is_admin(message.from_user.id):
        await message.answer("❌ شما به این بخش دسترسی ندارید.")
        return
    
    categories = await db.get_all_categories()
    locked_categories = [cat for cat in categories if cat.get('is_locked', False)]
    
    if not locked_categories:
        await message.answer("❌ هیچ دسته رمزداری وجود ندارد.")
        return
    
    keyboard = []
    for cat in locked_categories:
        keyboard.append([InlineKeyboardButton(
            text=f"🔒 {cat['title']}", 
            callback_data=f"manage_access_{cat['name']}"
        )])
    
    keyboard.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin_back")])
    
    await message.answer(
        "🔒 انتخاب دسته برای مدیریت دسترسی:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )

@dp.callback_query(F.data.startswith("manage_access_"))
async def manage_access_category(callback: types.CallbackQuery):
    if not settings.is_admin(callback.from_user.id):
        await callback.answer("دسترسی ندارید!", show_alert=True)
        return
    
    category_name = callback.data.replace("manage_access_", "")
    category = await db.get_category(category_name)
    
    if not category:
        await callback.answer("دسته یافت نشد!", show_alert=True)
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ اعطای دسترسی به کاربر", callback_data=f"grant_access_{category_name}")],
        [InlineKeyboardButton(text="👥 لیست کاربران دارای دسترسی", callback_data=f"list_access_{category_name}")],
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data="manage_categories")]
    ])
    
    await callback.message.answer(
        f"🔒 مدیریت دسترسی دسته: {category['title']}",
        reply_markup=keyboard
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("grant_access_"))
async def grant_access_start(callback: types.CallbackQuery, state: FSMContext):
    category_name = callback.data.replace("grant_access_", "")
    await state.update_data(target_category=category_name)
    
    await callback.message.answer(
        "👤 آیدی عددی کاربر را وارد کنید:",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(AdminStates.waiting_for_user_id_grant)
    await callback.answer()

@dp.message(AdminStates.waiting_for_user_id_grant)
async def process_grant_access(message: types.Message, state: FSMContext):
    if await handle_cancel(message, state):
        return
    
    try:
        user_id = int(message.text)
    except ValueError:
        await message.answer("❌ آیدی باید عدد باشد:")
        return
    
    user = await db.get_user(user_id)
    if not user:
        await message.answer("❌ کاربری با این آیدی یافت نشد:")
        return
    
    data = await state.get_data()
    category_name = data['target_category']
    category = await db.get_category(category_name)
    
    if not category:
        await message.answer("❌ دسته یافت نشد!", reply_markup=get_admin_main_keyboard())
        await state.clear()
        return
    
    success = await db.grant_category_access(user_id, category['id'])
    
    if success:
        await message.answer(
            f"✅ دسترسی به دسته '{category['title']}' برای کاربر {user['first_name']} {user['last_name']} (ID: {user_id}) اعطا شد!",
            reply_markup=get_admin_main_keyboard()
        )
        
        await safe_send_message(
            user_id,
            f"🎉 شما دسترسی به بخش '{category['title']}' را دریافت کردید!"
        )
        
        await db.log_activity(message.from_user.id, "grant_access", f"اعطای دسترسی {category_name} به {user_id}")
    else:
        await message.answer("❌ خطا در اعطای دسترسی!", reply_markup=get_admin_main_keyboard())
    
    await state.clear()

# --- تغییر وضعیت قفل دسته ---
@dp.callback_query(F.data.startswith("toggle_lock_"))
async def toggle_category_lock(callback: types.CallbackQuery, state: FSMContext):
    if not settings.is_admin(callback.from_user.id):
        await callback.answer("دسترسی ندارید!", show_alert=True)
        return
    
    category_name = callback.data.replace("toggle_lock_", "")
    category = await db.get_category(category_name)
    
    if category['is_locked']:
        success = await db.update_category(category_name, {'is_locked': False, 'password': None})
        if success:
            await callback.message.answer(f"✅ دسته '{category['title']}' اکنون آزاد است.")
    else:
        await state.update_data(category_to_lock=category_name)
        await callback.message.answer(
            f"🔒 رمز جدید برای دسته '{category['title']}' را وارد کنید:",
            reply_markup=get_cancel_keyboard()
        )
        await state.set_state(AdminStates.waiting_for_category_password)
        await callback.answer()
        return
    
    await callback.answer()

@dp.message(AdminStates.waiting_for_category_password)
async def process_category_lock_password(message: types.Message, state: FSMContext):
    if await handle_cancel(message, state):
        return
    
    data = await state.get_data()
    category_name = data['category_to_lock']
    
    success = await db.update_category(category_name, {
        'is_locked': True, 
        'password': message.text,
        'icon': '🔒'
    })
    
    if success:
        await message.answer(
            f"✅ دسته '{category_name}' اکنون رمزدار است.\n🔑 رمز: {message.text}",
            reply_markup=get_admin_main_keyboard()
        )
        await db.log_activity(message.from_user.id, "lock_category", f"قفل کردن دسته: {category_name}")
    else:
        await message.answer("❌ خطا در تنظیم رمز!", reply_markup=get_admin_main_keyboard())
    
    await state.clear()

# --- حذف دسته ---
@dp.callback_query(F.data.startswith("delete_cat_"))
async def delete_category_confirm(callback: types.CallbackQuery):
    if not settings.is_admin(callback.from_user.id):
        await callback.answer("دسترسی ندارید!", show_alert=True)
        return
    
    category_name = callback.data.replace("delete_cat_", "")
    category = await db.get_category(category_name)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ بله، حذف کن", callback_data=f"confirm_delete_{category_name}")],
        [InlineKeyboardButton(text="❌ انصراف", callback_data=f"edit_cat_{category_name}")]
    ])
    
    await callback.message.answer(
        f"⚠️ آیا مطمئن هستید که می‌خواهید دسته '{category['title']}' و تمام محتوای آن را حذف کنید؟\n\n❌ این عمل غیرقابل بازگشت است!",
        reply_markup=keyboard
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("confirm_delete_"))
async def delete_category_final(callback: types.CallbackQuery):
    category_name = callback.data.replace("confirm_delete_", "")
    
    success = await db.delete_category(category_name)
    
    if success:
        await callback.message.answer("✅ دسته با موفقیت حذف شد!")
        await db.log_activity(callback.from_user.id, "delete_category", f"حذف دسته: {category_name}")
    else:
        await callback.message.answer("❌ خطا در حذف دسته!")
    
    await callback.answer()

# --- دسترسی به دسته‌های رمزدار ---
@dp.message(F.text.contains("🔒"))
async def handle_locked_category(message: types.Message, state: FSMContext):
    """مدیریت دسترسی به دسته‌های رمزدار"""
    text = message.text.replace("🔒", "").strip()
    for emoji in ["📚", "🔗", "👥", "📁"]:
        text = text.replace(emoji, "").strip()

    categories = await db.get_all_categories()
    category = None
    for cat in categories:
        if cat['title'] in message.text or cat['name'] in text.lower():
            category = cat
            break

    if not category or not category.get('is_locked', False):
        await message.answer("❌ دسته مورد نظر یافت نشد.")
        return

    has_access = await db.has_category_access(message.from_user.id, category['name'])
    if has_access:
        await show_category_content(message, category['name'])
        return

    await state.update_data(locked_category=category['name'])
    await message.answer(f"🔒 برای دسترسی به «{category['title']}» لطفا رمز عبور را وارد کنید:", reply_markup=get_cancel_keyboard())
    await state.set_state(UserStates.waiting_for_category_password)

@dp.message(UserStates.waiting_for_category_password)
async def process_category_password(message: types.Message, state: FSMContext):
    if await handle_cancel(message, state):
        return

    data = await state.get_data()
    category_name = data.get('locked_category')

    if not category_name:
        await message.answer("❌ خطا در دریافت اطلاعات دسته.")
        await state.clear()
        return

    is_correct = await db.check_category_password(category_name, message.text)
    if is_correct:
        category = await db.get_category(category_name)
        if category:
            await db.grant_category_access(message.from_user.id, category['id'])
            keyboard = await get_user_main_keyboard(message.from_user.id)
            await message.answer("✅ رمز صحیح! دسترسی شما فعال شد.", reply_markup=keyboard)
            await show_category_content(message, category_name)
            await db.log_activity(message.from_user.id, "unlock_category", f"دسترسی به {category_name}")
        else:
            await message.answer("❌ خطا در دسترسی.")
    else:
        await message.answer("❌ رمز اشتباه است. دوباره تلاش کنید:")
        return

    await state.clear()

# --- نمایش محتوای دسته‌ها ---
async def show_category_content(message: types.Message, category_name: str):
    """نمایش محتوای یک دسته با حفاظت کامل"""
    try:
        category = await db.get_category(category_name)
        if category and category.get('is_locked', False):
            has_access = await db.has_category_access(message.from_user.id, category_name)
            if not has_access:
                await message.answer("❌ شما به این بخش دسترسی ندارید.")
                return

        contents = await db.get_content_by_category(category_name)
        subcategories = await db.get_subcategories(category_name)

        if not contents and not subcategories:
            await message.answer("این بخش هنوز محتوایی ندارد.")
            return

        if subcategories:
            keyboard = []
            for sub in subcategories:
                keyboard.append([InlineKeyboardButton(text=f"📁 {sub['name']}", callback_data=f"subcategory_{category_name}_{sub['name']}")])

            if contents:
                keyboard.append([InlineKeyboardButton(text="📄 محتوای اصلی", callback_data=f"main_content_{category_name}")])

            title = category['title'] if category else category_name
            await message.answer(f"📂 {title}\n\nزیرمجموعه‌ها را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))
        else:
            await show_content_list(message, contents, category_name)

    except Exception as e:
        logger.error(f"خطا در نمایش محتوای دسته: {e}")
        await message.answer("❌ خطا در بارگذاری محتوا.")

@dp.message(F.text.in_(["📚 آموزش نگرش", "🔗 آموزش بلاکچین", "👥 آموزش رفرال"]))
async def handle_category_access(message: types.Message):
    """مدیریت دسترسی به دسته‌ها"""
    category_map = {
        "📚 آموزش نگرش": "mindset",
        "🔗 آموزش بلاکچین": "blockchain",
        "👥 آموزش رفرال": "referral"
    }

    category_name = category_map.get(message.text)
    if category_name:
        await show_category_content(message, category_name)

# --- نمایش محتوا با حفاظت ---
async def show_content_list(message: types.Message, contents: List[Dict], category_name: str, subcategory: str = None):
    """نمایش لیست محتوا با حفاظت کامل"""
    if not contents:
        await message.answer("محتوایی یافت نشد.")
        return

    protection_message = f"""🔒 {settings.BOT_NAME} - محتوای محافظت شده

⚠️ توجه: این محتوا محافظت شده است
🚫 کپی، ذخیره و اسکرین‌شات غیرمجاز است
💎 فقط برای مشاهده در همین مکان

📚 محتوای دسته: {category_name}
{f'📁 زیرمجموعه: {subcategory}' if subcategory else ''}

🔽 محتوا در ادامه ارسال می‌شود..."""

    await message.answer(protection_message)
    await asyncio.sleep(1)

    for content in contents:
        caption = f"""📖 {content['title']}

{content['description'] or ''}

📅 تاریخ: {content['upload_date'][:10]}
🔒 محافظت شده توسط {settings.BOT_NAME}"""

        await safe_send_protected_content(message.from_user.id, content, caption)
        await asyncio.sleep(0.5)

        await db.log_activity(message.from_user.id, "view_content", f"مشاهده: {content['title']}")

# --- پشتیبانی ---
@dp.message(F.text == "💬 پشتیبانی")
async def support_menu(message: types.Message):
    user = await db.get_user(message.from_user.id)
    if not user or user['status'] != 'approved':
        await message.answer("ابتدا باید ثبت نام کنید و تایید شوید.")
        return

    await message.answer(
        "💬 بخش پشتیبانی\n\nچگونه می‌توانیم کمکتان کنیم؟",
        reply_markup=get_support_keyboard()
    )

@dp.callback_query(F.data == "new_support_message")
async def new_support_message(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("✉️ پیام خود را برای پشتیبانی بنویسید:", reply_markup=get_cancel_keyboard())
    await state.set_state(UserStates.waiting_for_support_message)
    await callback.answer()

@dp.message(UserStates.waiting_for_support_message)
async def process_support_message(message: types.Message, state: FSMContext):
    if await handle_cancel(message, state):
        return
    
    success = await db.add_support_message(message.from_user.id, message.text)
    
    if success:
        keyboard = await get_user_main_keyboard(message.from_user.id)
        await message.answer("✅ پیام شما ارسال شد. پشتیبانی در اسرع وقت پاسخ خواهد داد.", reply_markup=keyboard)
        
        user = await db.get_user(message.from_user.id)
        admin_message = f"""💬 پیام جدید پشتیبانی:

👤 کاربر: {user['first_name']} {user['last_name']}
🆔 آیدی: {message.from_user.id}
📝 پیام: {message.text}
📅 زمان: {datetime.now().strftime('%Y-%m-%d %H:%M')}"""
        
        for admin_id in settings.ADMIN_IDS:
            await safe_send_message(admin_id, admin_message)
        
        await db.log_activity(message.from_user.id, "support_message", "ارسال پیام پشتیبانی")
    else:
        await message.answer("❌ خطا در ارسال پیام. لطفا دوباره تلاش کنید.")
    
    await state.clear()

@dp.callback_query(F.data == "contact_info")
async def contact_info(callback: types.CallbackQuery):
    contact_text = """📞 راه‌های ارتباطی:

🌐 وبسایت: mahsen81.ir
📧 ایمیل: info@mahsen81.ir
📱 تلگرام: @mahsen81
🕐 ساعات کاری: 9:00 تا 18:00

💬 همچنین می‌توانید از همین قسمت پیام ارسال کنید."""
    
    await callback.message.answer(contact_text)
    await callback.answer()

@dp.callback_query(F.data == "faq")
async def faq(callback: types.CallbackQuery):
    faq_text = """❓ سوالات متداول:

🔹 چگونه ثبت نام کنم؟
پاسخ: با دستور /start فرآیند ثبت نام شروع می‌شود.

🔹 چرا درخواستم تایید نمی‌شود؟
پاسخ: ادمین درخواست‌ها را بررسی می‌کند. لطفا صبور باشید.

🔹 چگونه به بخش‌های رمزدار دسترسی پیدا کنم؟
پاسخ: رمز را از ادمین دریافت کنید و وارد بخش مورد نظر شوید.

🔹 مشکل فنی دارم، چه کنم؟
پاسخ: از بخش پشتیبانی پیام ارسال کنید."""
    
    await callback.message.answer(faq_text)
    await callback.answer()

@dp.callback_query(F.data == "back_to_main")
async def back_to_main(callback: types.CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    if user and user['status'] == 'approved':
        keyboard = await get_user_main_keyboard(callback.from_user.id)
        await callback.message.answer("🏠 منوی اصلی:", reply_markup=keyboard)
    await callback.answer()

# --- callbacks برای زیرمجموعه‌ها ---
@dp.callback_query(F.data.startswith("subcategory_"))
async def show_subcategory_content(callback: types.CallbackQuery):
    parts = callback.data.split("_", 2)
    category_name = parts[1]
    subcategory_name = parts[2]
    
    category = await db.get_category(category_name)
    if category and category.get('is_locked', False):
        has_access = await db.has_category_access(callback.from_user.id, category_name)
        if not has_access:
            await callback.answer("❌ شما به این بخش دسترسی ندارید.", show_alert=True)
            return
    
    contents = await db.get_content_by_category(category_name, subcategory_name)
    await show_content_list(callback.message, contents, category_name, subcategory_name)
    await callback.answer()

@dp.callback_query(F.data.startswith("main_content_"))
async def show_main_category_content(callback: types.CallbackQuery):
    category_name = callback.data.replace("main_content_", "")
    
    category = await db.get_category(category_name)
    if category and category.get('is_locked', False):
        has_access = await db.has_category_access(callback.from_user.id, category_name)
        if not has_access:
            await callback.answer("❌ شما به این بخش دسترسی ندارید.", show_alert=True)
            return
    
    contents = await db.get_content_by_category(category_name)
    await show_content_list(callback.message, contents, category_name)
    await callback.answer()

# --- مشاهده پروفایل کاربر ---
@dp.message(F.text == "👤 پروفایل من")
async def user_profile(message: types.Message):
    user = await db.get_user(message.from_user.id)
    if not user:
        await message.answer("شما ثبت نام نشده‌اید.")
        return
    
    try:
        user_stats = await db.get_user_statistics(message.from_user.id) if hasattr(db, 'get_user_statistics') else {}
    except:
        user_stats = {}
    
    txt = f"""👤 پروفایل من

🆔 آیدی: {user['user_id']}
👤 نام: {user['first_name']} {user['last_name']}
🎯 کد NFT: {user['nft_code']}
💳 آدرس ولت: {user['wallet_address']}
📅 عضویت: {user['join_date'][:10]}
✅ وضعیت: {user['status']}

📊 آمار شما:
🔍 بازدید محتوا: {user_stats.get('content_views', 0)}
📅 آخرین فعالیت: {user['last_activity'][:16] if user['last_activity'] else 'نامشخص'}"""
    
    await message.answer(txt)

# --- مشاهده پروفایل توسط ادمین ---
@dp.callback_query(F.data.startswith("view_profile_"))
async def admin_view_profile(callback: types.CallbackQuery):
    if not settings.is_admin(callback.from_user.id):
        await callback.answer("❌ دسترسی ندارید!", show_alert=True)
        return

    user_id = int(callback.data.split("_")[2])
    user = await db.get_user(user_id)

    if not user:
        await callback.answer("❌ کاربر یافت نشد", show_alert=True)
        return

    txt = f"""👤 پروفایل کاربر:

🆔 آیدی: {user['user_id']}
👤 نام: {user['first_name']} {user['last_name']}
🎯 کد NFT: {user['nft_code']}
💳 آدرس ولت: {user['wallet_address']}
📅 عضویت: {user['join_date']}
✅ وضعیت: {user['status']}
🚫 مسدود: {'بله' if user['is_blocked'] else 'خیر'}
📅 آخرین فعالیت: {user['last_activity'] or 'نامشخص'}"""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✉️ ارسال پیام", callback_data=f"admin_dm_{user_id}")],
        [InlineKeyboardButton(text="🔒 تغییر دسترسی", callback_data=f"manage_user_access_{user_id}")],
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin_back")]
    ])
    
    await callback.message.answer(txt, reply_markup=keyboard)
    await callback.answer()

@dp.callback_query(F.data.startswith("admin_dm_"))
async def admin_direct_message_start(callback: types.CallbackQuery, state: FSMContext):
    if not settings.is_admin(callback.from_user.id):
        await callback.answer("دسترسی ندارید!", show_alert=True)
        return
    
    user_id = int(callback.data.split("_")[-1])
    await state.update_data(dm_target=user_id)
    await callback.message.answer(f"✉️ پیام مورد نظر برای کاربر {user_id} را وارد نمایید:", reply_markup=get_cancel_keyboard())
    await state.set_state(AdminStates.waiting_for_admin_reply)
    await callback.answer()

@dp.message(AdminStates.waiting_for_admin_reply)
async def admin_direct_message_send(message: types.Message, state: FSMContext):
    if await handle_cancel(message, state):
        return

    data = await state.get_data()
    target = data.get('dm_target')

    if not target:
        await message.answer("❌ خطا: هدف پیام مشخص نیست!")
        await state.clear()
        return

    try:
        await safe_send_message(target, f"📬 پیام از مدیریت:\n\n{message.text}")
        await message.answer("✅ پیام با موفقیت ارسال شد", reply_markup=get_admin_main_keyboard())
        await db.log_activity(message.from_user.id, "admin_message", f"پیام به کاربر {target}")
    except Exception as e:
        logger.error(f"خطا در ارسال پیام ادمین: {e}")
        await message.answer("❌ خطا در ارسال پیام", reply_markup=get_admin_main_keyboard())

    await state.clear()

@dp.callback_query(F.data == "admin_back")
async def admin_back(callback: types.CallbackQuery):
    await callback.message.answer("🔧 پنل مدیریت:", reply_markup=get_admin_keyboard())
    await callback.answer()

# --- handler پیش‌فرض ---
@dp.message()
async def fallback_handler(message: types.Message):
    if settings.is_admin(message.from_user.id):
        await message.answer(
            "دستور ناشناس! از دکمه‌های پنل مدیریت استفاده کنید.",
            reply_markup=get_admin_main_keyboard()
        )
    else:
        user = await db.get_user(message.from_user.id)
        if user and user['status'] == 'approved':
            # بررسی اینکه آیا پیام مربوط به دسته‌ای است که در کیبورد وجود دارد
            categories = await db.get_all_categories()
            for category in categories:
                if category['title'] in message.text:
                    await show_category_content(message, category['name'])
                    return
            
            keyboard = await get_user_main_keyboard(message.from_user.id)
            await message.answer(
                "پیام یا فرمان شما شناخته نشد! لطفا از منوی پایین استفاده کنید.",
                reply_markup=keyboard
            )
        else:
            await message.answer(
                "لطفا ابتدا ثبت نام کنید. از دستور /start استفاده کنید.",
                reply_markup=types.ReplyKeyboardRemove()
            )

# --- راه‌اندازی اصلی ---
async def main():
    """راه‌اندازی اصلی ربات"""
    try:
        # ایجاد پوشه‌های مورد نیاز
        ensure_directory_exists(settings.CONTENT_DIR)
        ensure_directory_exists(settings.LOG_DIR)
        
        # راه‌اندازی دیتابیس
        await db.init_db()
        logger.info("✅ دیتابیس راه‌اندازی شد.")
        
        # اطلاع رسانی شروع ربات
        logger.info(f"🤖 ربات {settings.BOT_NAME} شروع به کار کرد")
        logger.info(f"👮‍♂️ ادمین‌ها: {settings.ADMIN_IDS}")
        
        # شروع polling
        await dp.start_polling(bot)
        
    except Exception as e:
        logger.error(f"خطا در راه‌اندازی ربات: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
