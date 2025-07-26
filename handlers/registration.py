from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
import re

from database import Database
from keyboards import Keyboards
from states import RegistrationStates
from utils import ValidationUtils, MessageUtils
from config import settings

router = Router()
db = Database()

@router.message(RegistrationStates.waiting_for_name)
async def process_name(message: types.Message, state: FSMContext):
    """پردازش نام"""
    from handlers.common import handle_cancel
    if await handle_cancel(message, state):
        return
    
    # اعتبارسنجی نام
    name = message.text.strip()
    if not ValidationUtils.validate_name(name):
        await message.answer(
            "❌ نام باید بین 2 تا 50 کاراکتر و فقط شامل حروف باشد.\n"
            "لطفا دوباره وارد کنید:"
        )
        return
    
    await state.update_data(first_name=name)
    await message.answer("✅ نام ثبت شد.\n\nحالا نام خانوادگی خود را وارد کنید:")
    await state.set_state(RegistrationStates.waiting_for_lastname)

@router.message(RegistrationStates.waiting_for_lastname)
async def process_lastname(message: types.Message, state: FSMContext):
    """پردازش نام خانوادگی"""
    from handlers.common import handle_cancel
    if await handle_cancel(message, state):
        return
    
    lastname = message.text.strip()
    if not ValidationUtils.validate_name(lastname):
        await message.answer(
            "❌ نام خانوادگی باید بین 2 تا 50 کاراکتر و فقط شامل حروف باشد.\n"
            "لطفا دوباره وارد کنید:"
        )
        return
    
    await state.update_data(last_name=lastname)
    await message.answer(
        "✅ نام خانوادگی ثبت شد.\n\n"
        "حالا کد NFT خود را وارد کنید:\n"
        "💡 این کد در متادیتای NFT شما موجود است."
    )
    await state.set_state(RegistrationStates.waiting_for_nft_code)

@router.message(RegistrationStates.waiting_for_nft_code)
async def process_nft_code(message: types.Message, state: FSMContext):
    """پردازش کد NFT"""
    from handlers.common import handle_cancel
    if await handle_cancel(message, state):
        return
    
    nft_code = message.text.strip()
    if not ValidationUtils.validate_nft_code(nft_code):
        await message.answer(
            "❌ کد NFT نامعتبر است.\n"
            "لطفا کد صحیح را وارد کنید:"
        )
        return
    
    # بررسی تکراری نبودن کد NFT
    existing_user = await db.execute_query(
        'SELECT user_id FROM users WHERE nft_code = ?',
        (nft_code,),
        fetch_one=True
    )
    
    if existing_user:
        await message.answer(
            "❌ این کد NFT قبلاً ثبت شده است.\n"
            "لطفا کد صحیح خود را وارد کنید:"
        )
        return
    
    await state.update_data(nft_code=nft_code)
    await message.answer(
        "✅ کد NFT ثبت شد.\n\n"
        "حالا آدرس کیف پول خود را وارد کنید:\n"
        "💡 آدرس کیف پول باید معتبر باشد."
    )
    await state.set_state(RegistrationStates.waiting_for_wallet)

@router.message(RegistrationStates.waiting_for_wallet)
async def process_wallet(message: types.Message, state: FSMContext):
    """پردازش آدرس کیف پول"""
    from handlers.common import handle_cancel
    if await handle_cancel(message, state):
        return
    
    wallet_address = message.text.strip()
    if not ValidationUtils.validate_wallet_address(wallet_address):
        await message.answer(
            "❌ آدرس کیف پول نامعتبر است.\n"
            "لطفا آدرس صحیح را وارد کنید:"
        )
        return
    
    await state.update_data(wallet_address=wallet_address)
    await message.answer(
        "✅ آدرس کیف پول ثبت شد.\n\n"
        "اگر کد رفرال دارید، وارد کنید.\n"
        "اگر ندارید، /skip را ارسال کنید:"
    )
    await state.set_state(RegistrationStates.waiting_for_referral_code)

@router.message(RegistrationStates.waiting_for_referral_code)
async def process_referral_code(message: types.Message, state: FSMContext):
    """پردازش کد رفرال"""
    from handlers.common import handle_cancel
    if await handle_cancel(message, state):
        return
    
    data = await state.get_data()
    referred_by = None
    
    if message.text.strip() != "/skip":
        referral_code = message.text.strip()
        
        # یافتن کاربر رفرال‌دهنده
        referrer = await db.get_user_by_referral(referral_code)
        if referrer:
            referred_by = referrer['user_id']
            await message.answer("✅ کد رفرال معتبر است!")
        else:
            await message.answer("⚠️ کد رفرال نامعتبر است، بدون رفرال ادامه می‌دهیم.")
    
    # تکمیل ثبت نام
    await complete_registration(message, state, data, referred_by)

async def complete_registration(message: types.Message, state: FSMContext, data: dict, referred_by: int = None):
    """تکمیل فرآیند ثبت نام"""
    user_data = {
        'user_id': message.from_user.id,
        'first_name': data['first_name'],
        'last_name': data['last_name'],
        'username': message.from_user.username,
        'wallet_address': data['wallet_address'],
        'nft_code': data['nft_code'],
        'nft_image_path': None,
        'access_code': 'NOT_REQUIRED',
        'referred_by': referred_by
    }
    
    success = await db.add_user(user_data)
    
    if success:
        # پیام موفقیت
        await message.answer(
            "🎉 ثbت نام با موفقیت انجام شد!\n\n"
            "⏳ درخواست شما در انتظار بررسی ادمین است.\n"
            "به محض تایید، اطلاع‌رسانی خواهد شد.\n\n"
            "🕐 معمولاً این فرآیند تا 24 ساعت طول می‌کشد.",
            reply_markup=types.ReplyKeyboardRemove()
        )
        
        # اطلاع به ادمین‌ها
        await notify_admins_new_user(message.from_user, data, referred_by)
        
        # ثبت فعالیت
        await db.log_activity(
            message.from_user.id,
            "registration_completed",
            "users",
            message.from_user.id,
            "تکمیل ثبت نام"
        )
        
    else:
        await message.answer(
            "❌ خطا در ثبت نام!\n"
            "لطفا دوباره با دستور /start تلاش کنید.",
            reply_markup=types.ReplyKeyboardRemove()
        )
    
    await state.clear()

async def notify_admins_new_user(user: types.User, data: dict, referred_by: int = None):
    """اطلاع‌رسانی به ادمین‌ها"""
    from bot import bot
    
    referrer_info = ""
    if referred_by:
        referrer = await db.get_user(referred_by)
        if referrer:
            referrer_info = f"\n👥 معرف: {referrer['first_name']} {referrer['last_name']} ({referred_by})"
    
    admin_message = f"""🆕 درخواست ثبت نام جدید:

👤 نام: {data['first_name']} {data['last_name']}
🆔 آیدی: {user.id}  
📱 یوزرنیم: @{user.username or 'ندارد'}
🎯 کد NFT: {data['nft_code']}
💳 آدرس کیف پول: {data['wallet_address'][:20]}...
📅 زمان: {MessageUtils.format_datetime()}
{referrer_info}"""
    
    keyboard = Keyboards.get_user_actions_keyboard(user.id)
    
    for admin_id in settings.ADMIN_IDS:
        try:
            await bot.send_message(admin_id, admin_message, reply_markup=keyboard)
        except Exception as e:
            print(f"خطا در ارسال به ادمین {admin_id}: {e}")
