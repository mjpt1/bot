from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.types import InputMediaPhoto, InputMediaVideo, InputMediaDocument
import asyncio

from database import Database
from keyboards import Keyboards
from states import UserStates
from utils import MessageUtils, ContentUtils
from config import settings

router = Router()
db = Database()

@router.message(F.text.in_(["📚 آموزش نگرش", "🔗 آموزش بلاکچین", "👥 آموزش رفرال", "⭐ محتوای VIP"]))
async def handle_category_selection(message: types.Message, state: FSMContext):
    """انتخاب دسته توسط کاربر"""
    # نقشه‌ی متن به شناسه دسته
    category_map = {
        "📚 آموزش نگرش": "mindset",
        "🔗 آموزش بلاکچین": "blockchain", 
        "👥 آموزش رفرال": "referral",
        "⭐ محتوای VIP": "vip"
    }
    
    category_name = category_map.get(message.text)
    if not category_name:
        return
    
    # دریافت اطلاعات دسته
    category = await db.get_category(category_name)
    if not category:
        await message.answer("❌ دسته مورد نظر یافت نشد.")
        return
    
    # بررسی دسترسی
    if not await check_category_access(message.from_user.id, category):
        return
    
    # نمایش محتوای دسته
    await show_category_content(message, category, state)

async def check_category_access(user_id: int, category: dict) -> bool:
    """بررسی دسترسی کاربر به دسته"""
    # بررسی وضعیت کاربر
    user = await db.get_user(user_id)
    if not user or user['status'] != 'approved':
        return False
    
    # بررسی VIP
    if category.get('is_vip_only', False) and not user.get('is_vip', False):
        await MessageUtils.send_no_vip_access()
        return False
    
    # بررسی قفل
    if category.get('is_locked', False):
        has_access = await db.has_category_access(user_id, category['id'])
        if not has_access:
            await request_category_password(user_id, category)
            return False
    
    return True

async def request_category_password(user_id: int, category: dict):
    """درخواست رمز دسته"""
    from bot import bot
    
    await bot.send_message(
        user_id,
        f"🔒 برای دسترسی به «{category['title']}» نیاز به رمز عبور دارید.\n"
        "لطفا رمز را وارد کنید:",
        reply_markup=Keyboards.get_cancel_keyboard()
    )
    
    state = FSMContext.from_user(user_id)  # این باید درست شود
    await state.update_data(locked_category_id=category['id'])
    await state.set_state(UserStates.waiting_for_category_password)

@router.message(UserStates.waiting_for_category_password)
async def process_category_password(message: types.Message, state: FSMContext):
    """پردازش رمز دسته"""
    from handlers.common import handle_cancel
    if await handle_cancel(message, state):
        return
    
    data = await state.get_data()
    category_id = data.get('locked_category_id')
    
    if not category_id:
        await message.answer("❌ خطا در دریافت اطلاعات دسته.")
        await state.clear()
        return
    
    # بررسی رمز
    is_correct = await db.check_category_password(category_id, message.text)
    
    if is_correct:
        # اعطای دسترسی
        await db.grant_category_access(message.from_user.id, category_id)
        await message.answer(
            "✅ رمز صحیح! دسترسی شما فعال شد.",
            reply_markup=Keyboards.get_main_keyboard()
        )
        
        # نمایش محتوای دسته
        category = await db.get_category(str(category_id))
        if category:
            await show_category_content(message, category, state)
        
        await db.log_activity(
            message.from_user.id,
            "category_unlocked",
            "categories",
            category_id,
            f"دسترسی به دسته {category['name']}"
        )
    else:
        await message.answer("❌ رمز اشتباه است. دوباره تلاش کنید:")
        return  # ادامه در همان state
    
    await state.clear()

async def show_category_content(message: types.Message, category: dict, state: FSMContext):
    """نمایش محتوای دسته"""
    try:
        # دریافت زیرمجموعه‌ها
        subcategories = await db.get_subcategories(category['id'])
        
        # دریافت محتوای اصلی دسته
        main_content = await db.get_content_by_category(category['id'], subcategory_id=0)
        
        if not subcategories and not main_content:
            await message.answer(
                f"📂 {category['title']}\n\n"
                "این بخش هنوز محتوایی ندارد.\n"
                "به زودی محتوای جدید اضافه خواهد شد."
            )
            return
        
        # ساخت کیبورد
        keyboard_buttons = []
        
        # زیرمجموعه‌ها
        for subcategory in subcategories:
            content_count = subcategory.get('content_count', 0)
            button_text = f"📁 {subcategory['title']}"
            if content_count > 0:
                button_text += f" ({content_count})"
            
            keyboard_buttons.append([
                types.InlineKeyboardButton(
                    text=button_text,
                    callback_data=f"subcategory_{category['id']}_{subcategory['id']}"
                )
            ])
        
        # محتوای اصلی
        if main_content:
            keyboard_buttons.append([
                types.InlineKeyboardButton(
                    text=f"📄 محتوای اصلی ({len(main_content)})",
                    callback_data=f"main_content_{category['id']}"
                )
            ])
        
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        
        description = category.get('description', '')
        content_text = f"📂 {category['title']}\n\n"
        if description:
            content_text += f"{description}\n\n"
        content_text += "محتوای مورد نظر را انتخاب کنید:"
        
        await message.answer(content_text, reply_markup=keyboard)
        
        # ثبت فعالیت
        await db.log_activity(
            message.from_user.id,
            "category_viewed",
            "categories", 
            category['id'],
            f"مشاهده دسته {category['title']}"
        )
        
    except Exception as e:
        print(f"خطا در نمایش محتوای دسته: {e}")
        await message.answer("❌ خطا در بارگذاری محتوا.")

@router.callback_query(F.data.startswith("subcategory_"))
async def handle_subcategory_selection(callback: types.CallbackQuery):
    """انتخاب زیرمجموعه"""
    try:
        _, category_id, subcategory_id = callback.data.split("_")
        category_id = int(category_id)
        subcategory_id = int(subcategory_id)
        
        # دریافت محتوای زیرمجموعه
        content_list = await db.get_content_by_category(category_id, subcategory_id)
        
        if not content_list:
            await callback.answer("این زیرمجموعه محتوایی ندارد.", show_alert=True)
            return
        
        # نمایش محتوا
        await show_content_list(callback.message, content_list, category_id, subcategory_id)
        await callback.answer()
        
    except Exception as e:
        print(f"خطا در انتخاب زیرمجموعه: {e}")
        await callback.answer("خطا در بارگذاری محتوا.", show_alert=True)

@router.callback_query(F.data.startswith("main_content_"))
async def handle_main_content(callback: types.CallbackQuery):
    """نمایش محتوای اصلی دسته"""
    try:
        category_id = int(callback.data.split("_")[2])
        
        content_list = await db.get_content_by_category(category_id, subcategory_id=0)
        
        if not content_list:
            await callback.answer("محتوایی یافت نشد.", show_alert=True)
            return
        
        await show_content_list(callback.message, content_list, category_id)
        await callback.answer()
        
    except Exception as e:
        print(f"خطا در نمایش محتوای اصلی: {e}")
        await callback.answer("خطا در بارگذاری محتوا.", show_alert=True)

async def show_content_list(message: types.Message, content_list: list, category_id: int, subcategory_id: int = None):
    """نمایش لیست محتوا با حفاظت"""
    try:
        # پیام حفاظت
        protection_message = f"""🔒 {settings.BOT_NAME} - محتوای محافظت شده

⚠️ توجه مهم:
🚫 کپی، ذخیره و اسکرین‌شات ممنوع
📵 اشتراک‌گذاری محتوا ممنوع  
💎 فقط برای مشاهده شخصی

📊 تعداد محتوا: {len(content_list)}
🔽 محتوا در ادامه ارسال می‌شود..."""
        
        await message.answer(protection_message)
        await asyncio.sleep(1)
        
        # ارسال محتوا
        for i, content in enumerate(content_list, 1):
            await send_protected_content(message, content, i, len(content_list))
            await asyncio.sleep(0.5)  # تأخیر بین ارسال محتوا
            
            # ثبت بازدید
            await db.increment_content_view(
                content['id'],
                message.from_user.id,
                f"session_{message.from_user.id}_{category_id}"
            )
        
        # پیام پایانی
        final_message = f"""✅ تمام محتوا ارسال شد.

📊 آمار شما:
👀 {len(content_list)} محتوا مشاهده شد
🕐 زمان: {MessageUtils.format_datetime()}

💬 نظر یا سوالی داشتید؟ از بخش پشتیبانی استفاده کنید."""
        
        await message.answer(final_message)
        
    except Exception as e:
        print(f"خطا در نمایش لیست محتوا: {e}")
        await message.answer("❌ خطا در نمایش محتوا.")

async def send_protected_content(message: types.Message, content: dict, index: int, total: int):
    """ارسال محتوای محافظت شده"""
    try:
        from bot import bot
        
        # ساخت کپشن
        caption = f"""📝 {content['title']} ({index}/{total})

{content.get('description', '') or 'بدون توضیح'}

🏷 دسته: {content.get('category_title', 'نامشخص')}
{'📁 زیرمجموعه: ' + content.get('subcategory_title', '') if content.get('subcategory_title') else ''}
👀 بازدید: {content.get('view_count', 0)}
📅 {MessageUtils.format_date(content.get('upload_date', ''))}

🔒 محافظت شده - {settings.BOT_NAME}"""
        
        # ارسال بر اساس نوع فایل
        if content['file_type'] == 'photo':
            if content.get('file_id'):
                await bot.send_photo(
                    message.chat.id,
                    content['file_id'],
                    caption=caption,
                    protect_content=True,
                    has_spoiler=False
                )
            else:
                with open(content['file_path'], 'rb') as photo:
                    await bot.send_photo(
                        message.chat.id,
                        photo,
                        caption=caption,
                        protect_content=True,
                        has_spoiler=False
                    )
        
        elif content['file_type'] == 'video':
            if content.get('file_id'):
                await bot.send_video(
                    message.chat.id,
                    content['file_id'],
                    caption=caption,
                    protect_content=True,
                    has_spoiler=False
                )
            else:
                with open(content['file_path'], 'rb') as video:
                    await bot.send_video(
                        message.chat.id,
                        video,
                        caption=caption,
                        protect_content=True,
                        has_spoiler=False
                    )
        
        elif content['file_type'] in ['document', 'audio']:
            if content.get('file_id'):
                await bot.send_document(
                    message.chat.id,
                    content['file_id'],
                    caption=caption,
                    protect_content=True
                )
            else:
                with open(content['file_path'], 'rb') as doc:
                    await bot.send_document(
                        message.chat.id,
                        doc,
                        caption=caption,
                        protect_content=True
                    )
        
        elif content['file_type'] == 'text':
            text_content = f"{caption}\n\n📄 محتوای متنی:\n{content.get('text_content', '')}"
            await bot.send_message(
                message.chat.id,
                text_content,
                protect_content=True
            )
            
    except Exception as e:
        print(f"خطا در ارسال محتوای محافظت شده: {e}")
        await message.answer(f"❌ خطا در ارسال محتوا: {content['title']}")

@router.message(F.text == "👤 پروفایل من")
async def show_user_profile(message: types.Message):
    """نمایش پروفایل کاربر"""
    user = await db.get_user(message.from_user.id)
    if not user:
        await message.answer("❌ اطلاعات کاربری یافت نشد.")
        return
    
    # دریافت آمار کاربر
    user_stats = await db.get_user_stats(message.from_user.id)
    
    status_text = {
        'pending': '⏳ در انتظار تایید',
        'approved': '✅ تایید شده',
        'rejected': '❌ رد شده',
        'blocked': '🚫 مسدود'
    }.get(user['status'], user['status'])
    
    profile_text = f"""👤 پروفایل شما:

🆔 آیدی: {user['user_id']}
👤 نام: {user['first_name']} {user['last_name']}
📱 یوزرنیم: @{user.get('username', 'ندارد')}
🎯 کد NFT: {user['nft_code']}
💳 کیف پول: {user['wallet_address'][:15]}...
📅 عضویت: {MessageUtils.format_date(user['join_date'])}
✅ وضعیت: {status_text}
{'⭐ VIP: بله' if user.get('is_vip', False) else ''}

📊 آمار فعالیت:
👀 بازدید محتوا: {user_stats.get('content_views', 0)}
💬 پیام پشتیبانی: {user_stats.get('support_messages', 0)}
👥 رفرال‌ها: {user_stats.get('referrals', 0)}
🕐 آخرین فعالیت: {MessageUtils.format_datetime(user['last_activity'])}

🔗 کد رفرال شما: {user.get('referral_code', 'ندارد')}"""
    
    await message.answer(profile_text)

@router.message(F.text == "💬 پشتیبانی")
async def start_support(message: types.Message, state: FSMContext):
    """شروع گفتگوی پشتیبانی"""
    support_enabled = await db.get_setting('support_enabled', True)
    if not support_enabled:
        await message.answer("❌ سیستم پشتیبانی در حال حاضر غیرفعال است.")
        return
    
    await message.answer(
        "💬 سیستم پشتیبانی\n\n"
        "پیام خود را بنویسید. می‌توانید متن، عکس، ویدیو یا فایل ارسال کنید.\n"
        "تیم پشتیبانی در اسرع وقت پاسخ خواهد داد.\n\n"
        "💡 برای لغو، دکمه انصراف را بزنید.",
        reply_markup=Keyboards.get_cancel_keyboard()
    )
    
    await state.set_state(UserStates.waiting_for_support_message)

@router.message(UserStates.waiting_for_support_message)
async def process_support_message(message: types.Message, state: FSMContext):
    """پردازش پیام پشتیبانی"""
    from handlers.common import handle_cancel
    if await handle_cancel(message, state):
        return
    
    try:
        message_text = ""
        message_type = "text"
        file_path = None
        file_id = None
        
        if message.text:
            message_text = message.text
            message_type = "text"
        elif message.photo:
            message_text = message.caption or "تصویر ارسالی"
            message_type = "photo"
            file_id = message.photo[-1].file_id
        elif message.video:
            message_text = message.caption or "ویدیو ارسالی"
            message_type = "video"
            file_id = message.video.file_id
        elif message.document:
            message_text = message.caption or f"سند: {message.document.file_name}"
            message_type = "document"
            file_id = message.document.file_id
        elif message.voice:
            message_text = "پیام صوتی"
            message_type = "voice"
            file_id = message.voice.file_id
        else:
            await message.answer("❌ نوع پیام پشتیبانی نشده. لطفا متن، عکس، ویدیو یا فایل ارسال کنید.")
            return
        
        # تشخیص اولویت پیام
        priority = "normal"
        urgent_keywords = ["فوری", "مهم", "urgent", "important", "مشکل", "خرابی", "باگ"]
        if any(keyword in message_text.lower() for keyword in urgent_keywords):
            priority = "high"
        
        # ذخیره پیام
        success = await db.add_support_message(
            message.from_user.id,
            message_text,
            message_type,
            file_path,
            file_id,
            priority
        )
        
        if success:
            await message.answer(
                "✅ پیام شما با موفقیت ارسال شد!\n\n"
                "🕐 تیم پشتیبانی در اسرع وقت پاسخ خواهد داد.\n"
                "📧 پاسخ از طریق همین ربات دریافت خواهید کرد.\n\n"
                f"🏷 اولویت: {priority}",
                reply_markup=Keyboards.get_main_keyboard()
            )
            
            # اطلاع به ادمین‌ها
            await notify_admins_support_message(message, message_text, priority)
            
        else:
            await message.answer(
                "❌ خطا در ارسال پیام!\nلطفا دوباره تلاش کنید.",
                reply_markup=Keyboards.get_main_keyboard()
            )
        
    except Exception as e:
        print(f"خطا در پردازش پیام پشتیبانی: {e}")
        await message.answer(
            "❌ خطا در پردازش پیام. لطفا دوباره تلاش کنید.",
            reply_markup=Keyboards.get_main_keyboard()
        )
    
    await state.clear()

async def notify_admins_support_message(message: types.Message, message_text: str, priority: str):
    """اطلاع‌رسانی پیام پشتیبانی به ادمین‌ها"""
    try:
        from bot import bot
        
        user = await db.get_user(message.from_user.id)
        if not user:
            return
        
        priority_emoji = {"low": "🔵", "normal": "🟡", "high": "🔴", "urgent": "🚨"}.get(priority, "🟡")
        
        admin_message = f"""💬 پیام پشتیبانی جدید:

{priority_emoji} اولویت: {priority.upper()}

👤 کاربر: {user['first_name']} {user['last_name']}
🆔 آیدی: {message.from_user.id}
📱 یوزرنیم: @{message.from_user.username or 'ندارد'}
🕐 زمان: {MessageUtils.format_datetime()}

💬 پیام:
{message_text[:500]}{"..." if len(message_text) > 500 else ""}"""
        
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="💬 پاسخ", callback_data=f"reply_support_{message.from_user.id}")],
            [types.InlineKeyboardButton(text="👤 پروفایل", callback_data=f"view_profile_{message.from_user.id}")]
        ])
        
        for admin_id in settings.ADMIN_IDS:
            try:
                await bot.send_message(admin_id, admin_message, reply_markup=keyboard)
                
                # ارسال فایل در صورت وجود
                if message.photo:
                    await bot.send_photo(admin_id, message.photo[-1].file_id, caption="📎 تصویر پیوست")
                elif message.video:
                    await bot.send_video(admin_id, message.video.file_id, caption="📎 ویدیو پیوست")
                elif message.document:
                    await bot.send_document(admin_id, message.document.file_id, caption="📎 فایل پیوست")
                elif message.voice:
                    await bot.send_voice(admin_id, message.voice.file_id, caption="📎 پیام صوتی")
                    
            except Exception as e:
                print(f"خطا در ارسال پیام پشتیبانی به ادمین {admin_id}: {e}")
                
    except Exception as e:
        print(f"خطا در اطلاع‌رسانی پیام پشتیبانی: {e}")

@router.message(F.text == "🔍 جستجو")
async def start_search(message: types.Message, state: FSMContext):
    """شروع جستجو"""
    await message.answer(
        "🔍 جستجو در محتوا\n\n"
        "کلمه کلیدی مورد نظر را وارد کنید:\n"
        "💡 می‌توانید در عنوان، توضیحات و تگ‌ها جستجو کنید.",
        reply_markup=Keyboards.get_cancel_keyboard()
    )
    
    await state.set_state(UserStates.waiting_for_search_query)

@router.message(UserStates.waiting_for_search_query)
async def process_search_query(message: types.Message, state: FSMContext):
    """پردازش جستجو"""
    from handlers.common import handle_cancel
    if await handle_cancel(message, state):
        return
    
    query = message.text.strip()
    if len(query) < 2:
        await message.answer("❌ جستجو باید حداقل 2 کاراکتر باشد.")
        return
    
    # جستجو در محتوا
    results = await db.search_content(query, limit=20)
    
    if not results:
        await message.answer(
            f"❌ هیچ نتیجه‌ای برای '{query}' یافت نشد.\n\n"
            "💡 نکات جستجو:\n"
            "• از کلمات کلیدی مختلف استفاده کنید\n"
            "• غلط املایی را بررسی کنید\n"
            "• از کلمات ساده‌تر استفاده کنید",
            reply_markup=Keyboards.get_main_keyboard()
        )
        await state.clear()
        return
    
    # نمایش نتایج
    results_text = f"🔍 نتایج جستجو برای '{query}':\n\n"
    results_text += f"📊 {len(results)} نتیجه یافت شد:\n\n"
    
    keyboard_buttons = []
    
    for i, result in enumerate(results[:10], 1):  # نمایش 10 نتیجه اول
        results_text += f"{i}. 📝 {result['title']}\n"
        results_text += f"   📂 {result.get('category_title', 'نامشخص')}"
        if result.get('subcategory_title'):
            results_text += f" > {result['subcategory_title']}"
        results_text += f"\n   👀 {result.get('view_count', 0)} بازدید\n\n"
        
        keyboard_buttons.append([
            types.InlineKeyboardButton(
                text=f"📄 {result['title'][:30]}...",
                callback_data=f"view_content_{result['id']}"
            )
        ])
    
    if len(results) > 10:
        results_text += f"... و {len(results) - 10} نتیجه دیگر"
    
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    await message.answer(
        results_text,
        reply_markup=keyboard
    )
    
    await message.answer(
        "روی هر محتوا کلیک کنید تا مشاهده کنید:",
        reply_markup=Keyboards.get_main_keyboard()
    )
    
    # ثبت فعالیت جستجو
    await db.log_activity(
        message.from_user.id,
        "content_search",
        details=f"جستجو: {query} - {len(results)} نتیجه"
    )
    
    await state.clear()

@router.callback_query(F.data.startswith("view_content_"))
async def view_single_content(callback: types.CallbackQuery):
    """مشاهده یک محتوای خاص"""
    try:
        content_id = int(callback.data.split("_")[2])
        
        content = await db.get_content(content_id)
        if not content:
            await callback.answer("محتوا یافت نشد.", show_alert=True)
            return
        
        # بررسی دسترسی
        category = await db.get_category(str(content['category_id']))
        if category and not await check_category_access(callback.from_user.id, category):
            await callback.answer("شما به این محتوا دسترسی ندارید.", show_alert=True)
            return
        
        # ارسال محتوا
        await send_protected_content(callback.message, content, 1, 1)
        
        # ثبت بازدید
        await db.increment_content_view(
            content_id,
            callback.from_user.id,
            f"single_view_{callback.from_user.id}"
        )
        
        await callback.answer("✅ محتوا ارسال شد.")
        
    except Exception as e:
        print(f"خطا در مشاهده محتوا: {e}")
        await callback.answer("خطا در بارگذاری محتوا.", show_alert=True)

@router.message(F.text == "📊 آمار من")
async def show_user_statistics(message: types.Message):
    """نمایش آمار کاربر"""
    user_stats = await db.get_user_stats(message.from_user.id)
    
    # دریافت فعالیت‌های اخیر
    recent_activities = await db.get_user_activities(message.from_user.id, limit=5)
    
    stats_text = f"""📊 آمار فعالیت شما:

👀 تعداد بازدید محتوا: {user_stats.get('content_views', 0)}
💬 پیام‌های پشتیبانی: {user_stats.get('support_messages', 0)}
👥 تعداد رفرال‌ها: {user_stats.get('referrals', 0)}

🕐 آخرین فعالیت‌ها:"""
    
    if recent_activities:
        for activity in recent_activities:
            action_text = {
                'content_viewed': '👀 مشاهده محتوا',
                'category_viewed': '📂 ورود به دسته', 
                'support_message_sent': '💬 ارسال پیام پشتیبانی',
                'category_unlocked': '🔓 باز کردن دسته',
                'content_search': '🔍 جستجو'
            }.get(activity['action'], activity['action'])
            
            stats_text += f"\n• {action_text} - {MessageUtils.format_datetime(activity['timestamp'])}"
    else:
        stats_text += "\nهنوز فعالیتی ثبت نشده."
    
    await message.answer(stats_text)
