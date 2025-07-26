from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from typing import List, Dict, Optional
from config import settings

class Keyboards:
    """کلاس مدیریت کیبوردها"""
    
    @staticmethod
    def get_cancel_keyboard():
        """کیبورد انصراف"""
        return ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="❌ انصراف")]],
            resize_keyboard=True,
            one_time_keyboard=True
        )
    
    @staticmethod
    def get_back_keyboard():
        """کیبورد بازگشت"""
        return ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="🔙 بازگشت به منوی اصلی")]],
            resize_keyboard=True
        )
    
    @staticmethod
    def get_main_keyboard():
        """کیبورد اصلی کاربران"""
        return ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="📚 آموزش نگرش"), KeyboardButton(text="🔗 آموزش بلاکچین")],
                [KeyboardButton(text="👥 آموزش رفرال"), KeyboardButton(text="⭐ محتوای VIP")],
                [KeyboardButton(text="👤 پروفایل من"), KeyboardButton(text="💬 پشتیبانی")],
                [KeyboardButton(text="🔙 بازگشت به منوی اصلی")]
            ],
            resize_keyboard=True
        )
    
    @staticmethod
    def get_admin_main_keyboard():
        """کیبورد اصلی ادمین"""
        return ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="🔧 پنل مدیریت کلی")],
                [KeyboardButton(text="👥 مدیریت کاربران"), KeyboardButton(text="📚 مدیریت محتوا")],
                [KeyboardButton(text="📊 آمار و گزارش"), KeyboardButton(text="📨 پیام همگانی")],
                [KeyboardButton(text="🔧 تنظیمات سیستم"), KeyboardButton(text="💾 پشتیبان‌گیری")],
                [KeyboardButton(text="🔙 بازگشت به منوی اصلی")]
            ],
            resize_keyboard=True
        )
    
    @staticmethod
    def get_admin_panel_keyboard():
        """کیبورد پنل مدیریت"""
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👥 کاربران در انتظار تایید", callback_data="pending_users")],
            [InlineKeyboardButton(text="📊 آمار کلی", callback_data="statistics")],
            [InlineKeyboardButton(text="👤 لیست کاربران", callback_data="users_list")],
            [InlineKeyboardButton(text="🔍 جستجوی کاربر", callback_data="search_user")],
            [InlineKeyboardButton(text="➕ افزودن محتوا", callback_data="add_content")],
            [InlineKeyboardButton(text="📝 مدیریت محتوا", callback_data="manage_content")],
            [InlineKeyboardButton(text="📂 مدیریت دسته‌ها", callback_data="manage_categories")],
            [InlineKeyboardButton(text="🔒 مدیریت دسترسی", callback_data="manage_access")],
            [InlineKeyboardButton(text="📂 زیرمجموعه‌ها", callback_data="manage_subcategories")],
            [InlineKeyboardButton(text="💬 پیام‌های پشتیبانی", callback_data="support_messages")],
            [InlineKeyboardButton(text="🔄 بروزرسانی", callback_data="refresh_panel")]
        ])
    
    @staticmethod
    def get_user_management_keyboard():
        """کیبورد مدیریت کاربران"""
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👥 کاربران در انتظار", callback_data="pending_users")],
            [InlineKeyboardButton(text="✅ کاربران تایید شده", callback_data="approved_users")],
            [InlineKeyboardButton(text="❌ کاربران رد شده", callback_data="rejected_users")],
            [InlineKeyboardButton(text="🚫 کاربران مسدود", callback_data="blocked_users")],
            [InlineKeyboardButton(text="🔍 جستجوی کاربر", callback_data="search_user")],
            [InlineKeyboardButton(text="📊 آمار کاربران", callback_data="user_stats")],
            [InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin_back")]
        ])
    
    @staticmethod
    def get_content_management_keyboard():
        """کیبورد مدیریت محتوا"""
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ افزودن محتوا", callback_data="add_content")],
            [InlineKeyboardButton(text="📝 ویرایش محتوا", callback_data="edit_content")],
            [InlineKeyboardButton(text="🗑️ حذف محتوا", callback_data="delete_content")],
            [InlineKeyboardButton(text="📂 مدیریت دسته‌ها", callback_data="manage_categories")],
            [InlineKeyboardButton(text="📁 زیرمجموعه‌ها", callback_data="manage_subcategories")],
            [InlineKeyboardButton(text="📊 آمار محتوا", callback_data="content_stats")],
            [InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin_back")]
        ])
    
    @staticmethod
    def get_category_selection_keyboard():
        """کیبورد انتخاب دسته‌بندی"""
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📚 آموزش نگرش", callback_data="cat_mindset")],
            [InlineKeyboardButton(text="🔗 آموزش بلاکچین", callback_data="cat_blockchain")],
            [InlineKeyboardButton(text="👥 آموزش رفرال", callback_data="cat_referral")],
            [InlineKeyboardButton(text="⭐ محتوای VIP", callback_data="cat_vip")],
            [InlineKeyboardButton(text="❌ انصراف", callback_data="cancel_operation")]
        ])
    
    @staticmethod
    def get_user_actions_keyboard(user_id: int):
        """کیبورد عملیات کاربر برای ادمین"""
        return InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ تایید", callback_data=f"approve_{user_id}"),
                InlineKeyboardButton(text="❌ رد", callback_data=f"reject_{user_id}")
            ],
            [InlineKeyboardButton(text="👤 مشاهده پروفایل", callback_data=f"view_profile_{user_id}")],
            [InlineKeyboardButton(text="✉️ ارسال پیام", callback_data=f"admin_dm_{user_id}")],
            [InlineKeyboardButton(text="🚫 مسدود/رفع مسدودی", callback_data=f"toggle_block_{user_id}")]
        ])
    
    @staticmethod
    def get_profile_keyboard():
        """کیبورد پروفایل کاربر"""
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📝 ویرایش پروفایل", callback_data="edit_profile")],
            [InlineKeyboardButton(text="📊 آمار فعالیت", callback_data="user_activity")],
            [InlineKeyboardButton(text="🔙 بازگشت", callback_data="back_to_main")]
        ])
    
    @staticmethod
    def get_support_keyboard():
        """کیبورد پشتیبانی"""
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💬 ارسال پیام جدید", callback_data="new_support_message")],
            [InlineKeyboardButton(text="📋 پیام‌های من", callback_data="my_support_messages")],
            [InlineKeyboardButton(text="❓ سوالات متداول", callback_data="faq")],
            [InlineKeyboardButton(text="🔙 بازگشت", callback_data="back_to_main")]
        ])
    
    @staticmethod
    def get_content_display_keyboard(category: str, subcategories: List[Dict]):
        """کیبورد نمایش محتوای دسته"""
        keyboard = []
        
        # زیرمجموعه‌ها
        for sub in subcategories:
            keyboard.append([InlineKeyboardButton(
                text=f"📁 {sub['name']}", 
                callback_data=f"subcategory_{category}_{sub['name']}"
            )])
        
        # محتوای اصلی دسته (در صورت وجود)
        keyboard.append([InlineKeyboardButton(
            text="📄 محتوای اصلی", 
            callback_data=f"main_content_{category}"
        )])
        
        # دکمه بازگشت
        keyboard.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data="back_to_main")])
        
        return InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    @staticmethod
    def get_stats_keyboard():
        """کیبورد آمار"""
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📊 آمار تفصیلی", callback_data="detailed_stats")],
            [InlineKeyboardButton(text="📈 نمودار فعالیت", callback_data="activity_chart")],
            [InlineKeyboardButton(text="💾 خروجی آمار", callback_data="export_stats")],
            [InlineKeyboardButton(text="🔄 بروزرسانی", callback_data="refresh_stats")],
            [InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin_back")]
        ])
    
    @staticmethod
    def get_broadcast_menu_keyboard():
        """کیبورد منوی پیام همگانی"""
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📢 همه کاربران", callback_data="broadcast_all")],
            [InlineKeyboardButton(text="✅ کاربران تایید شده", callback_data="broadcast_approved")],
            [InlineKeyboardButton(text="⭐ کاربران VIP", callback_data="broadcast_vip")],
            [InlineKeyboardButton(text="🎯 کاربران خاص", callback_data="broadcast_custom")],
            [InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin_back")]
        ])
    
    @staticmethod
    def get_confirm_keyboard(action: str, item_id: Optional[str] = None):
        """کیبورد تایید عملیات"""
        callback_data = f"confirm_{action}"
        if item_id:
            callback_data += f"_{item_id}"
        
        return InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ تایید", callback_data=callback_data),
                InlineKeyboardButton(text="❌ انصراف", callback_data="cancel_operation")
            ]
        ])
    
    @staticmethod
    def get_pagination_keyboard(current_page: int, total_pages: int, callback_prefix: str):
        """کیبورد صفحه‌بندی"""
        keyboard = []
        
        if total_pages > 1:
            row = []
            
            if current_page > 1:
                row.append(InlineKeyboardButton(text="⬅️", callback_data=f"{callback_prefix}_page_{current_page-1}"))
            
            row.append(InlineKeyboardButton(text=f"{current_page}/{total_pages}", callback_data="current_page"))
            
            if current_page < total_pages:
                row.append(InlineKeyboardButton(text="➡️", callback_data=f"{callback_prefix}_page_{current_page+1}"))
            
            keyboard.append(row)
        
        keyboard.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin_back")])
        
        return InlineKeyboardMarkup(inline_keyboard=keyboard)
