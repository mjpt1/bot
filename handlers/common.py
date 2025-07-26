import asyncio
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from typing import Optional

from config import settings
from database import Database
from keyboards import Keyboards
from states import *
from utils import MessageUtils, ValidationUtils

router = Router()
db = Database()

# مدیریت انصراف عمومی
async def handle_cancel(message: types.Message, state: FSMContext) -> bool:
    """مدیریت انصراف در همه state ها"""
    if message.text in ["❌ انصراف", "🔙 بازگشت" "/cancel"]:
        await state.clear()
        
        if settings.is_admin(message.from_user.id):
            await message.answer(
                "عملیات لغو شد.", 
                reply_markup=Keyboards.get_admin_main_keyboard()
            )
        else:
            await message.answer(
                "عملیات لغو شد.", 
                reply_markup=Keyboards.get_main_keyboard()
            )
        return True
    return False

@router.message(Command("start"))
async def start_handler(message: types.Message, state: FSMContext):
    """هندلر شروع"""
    await state.clear()
    
    # بررسی وضعیت نگهداری
    maintenance_mode = await db.get_setting('maintenance_mode', False)
    if maintenance_mode and not settings.is_admin(message.from_user.id):
        await message.answer(
            "🔧 سیستم در حال عمیر و نگهداری است.\nلطفا بعداً مراجعه کنید."
        )
        return

    # بررسی ادمین
    if settings.is_admin(message.from_user.id):
        await message.answer(
            f"👋 سلامادمین عزیز!\nبه پنل مدیریت {settings.BOT_NAME} خوش آمدید.",
            reply_markup=Keyboards.get_admin_main_keyboard()
        )
        await db.log_activity(message.from_user.id, "admin_start", details="ورود ادمین")
        return

    # بررسی کاربر موجود
    user = await db.get_user(message.from_user.id)
    
    if user:
        await handle_existing_user(message, user)
    else:
        await start_registration(message, state)

async def handle_existing_user(message: types.Message, user: dict):
    """مدیریت کاربران موجود"""
    if user['is_blocked']:
        await message.answer("🚫 ساب شما مسدود شده است.\nبرای اطلاعات بیشتر با پشتیبانی تماس بگیرید.")
        return
    
    if user['status'] == 'approved':
        welcome_text = f"سلام {user['first_name']} عزیز! 👋\n
        welcome_text += f"به {settings.BOT_NAME} خوش آمدید.\n\n"
        
        # نمایش اطلاعات VIP
        if user.get('is_vip', False):
            welcome_text += "⭐ شما عضو VIP هستید!\n"
        
        welcome_text += "از منوی زیر استفاده کنید:"
        
        await message.answer(welcome_text, reply_markup=Keyboards.get_main_keyboard())
        await db.update_last_activity(message.from_user.id)
        await db.log_activity(message.from_user.id, "user_start", details="ورود کاربر")
        
    elif user['status'] == 'pending':
        await message.answer(
            "⏳ درخواست شما در حال بررسی است.\n"
            "به محض تایید توسط ادمین، اطلاع‌رسانی خواهد شد."
        )
    elif user['status'] == 'rejected':
        await message.answer(
            "❌ متأسفانه درخواست شما رد شده است.\n"
            "برای اطلاعات بیشتر با پشتیبانی تماس بگیرید."
        )

async def start_registration(message: types.Message, state: FSMContext):
    """شروع فرآیند ثبت نام"""
    registration_enabled = await db.get_setting('registration_enabled', True)
    if not registration_enabled:
        await message.answer(
            "❌ امکان ثبت نام جدید در حال حاضر غیرفعال است.\n"
            "لطفا بعداً مراجعه کنید."
        )
        return
    
    await message.answer(
        f"{settings.WELCOME_MESSAGE}\n\n"
        "برای ثبت نام، اطلاعات زیر را به ترتیب وارد کنید.\n"
        "⚠️ لطفا اطلاعات را دقیق وارد کنید."
    )
    
    await message.answer(
        "لطفا نام خود را وارد کنید:",
        reply_markup=Keyboards.get_cancel_keyboard()
    )
    
    await state.set_state(RegistrationStates.waiting_for_name)
    await db.log_activity(message.from_user.id, "registration_start", details="شروع ثبت نام")

@router.message(Command("help"))
async def help_handler(message: types.Message):
    """راهنمای استفاده"""
    if settings.is_admin(message.from_user.id):
        help_text = """🔧 راهنمای نل مدیریت:

👥 مدیریت کاربرا - تایید، رد، مسدودی
� مدیریت محتوا - آپلود، ویرایش، حذف
📂 مدیرت دسته‌ها - ایجاد، ویرایش دسته
🔒 مدیرت دسترسی - کنترل دسترسی کاربران
💬 پشتبانی - پاسخ به پیام‌های کاربران
📨 یام همگانی - ارسال اعلان
🧪 تست سستم - بررسی عملکرد
📊 آمار کام - گزارش‌های تفصیلی"""
    else:
        help_text = f"""📚 راهنمای اسفاده از {settings.BOT_NAME}:

� آموزش نگرش - محتوای آموزشی ذهنیت
� آموزش بلاکچین - آموزش‌های فنی
👥 آموزش فرال - روش‌های معرفی
⭐ محتوای VIP - محتوای ویژه
👤 پروفایل م - اطلاعات حساب
� جستجو - جستجو در محتوا
💬 پتیبانی - ارتباط با پشتیبانی
📊 آمار م - آمار فعالیت شما

دستورات مفید:
/start - شروع یا بازگشت به منو
/help - نمایش این راهنما
/cancel - لغو عملیات جاری"""
    
    await message.answer(help_text)

@router.message(Command("cancel"))
async def cancel_handler(message: types.Message, state: FSMContext):
    """لغو عملیات"""
    await handle_cancel(message, state)

@router.message(F.text == "🔙 بازگش به منوی اصلی")
async def back_to_main(message: types.Message, state: FSMContext):
    """بازگشت به منوی اصلی"""
    await state.clear()
    
    if settings.is_admin(message.from_user.id):
        await message.answer(
            "بازگشت به پنل مدیریت",
            reply_markup=Keyboards.get_admin_main_keyboard()
        )
    else:
        await message.answer(
            "بازگشت به منوی اصلی",
            reply_markup=Keyboards.get_main_keyboard()
        )

# هندلر عمومی برای پیام‌های ناشناخته
@router.message()
async def unknown_message_handler(message: types.Message, state: FSMContext):
    """مدیریت پیام‌های ناشناخته"""
    current_state = await state.get_state()
    
    # اگر در حالت خاصی هستیم، پیام راهنما ندهیم
    if current_state:
        return
    
    if settings.is_admin(message.from_user.id):
        await message.answer(
            "دستور ناشناخته! از منوی مدیریت استفاده کنید.",
            reply_markup=Keyboards.get_admin_main_keyboard()
        )
    else:
        user = await db.get_user(message.from_user.id)
        if user and user['status'] == 'approved':
            await message.answer(
                "پیام شما درک نشد! از منوی اصلی استفاده کنید.",
                reply_markup=Keyboards.get_main_keyboard()
            )
        else:
            await message.answer(
                "برای استفاده از ربات، ابتدا دستور /start را ارسال کنید."
            )
