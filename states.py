from aiogram.fsm.state import State, StatesGroup

class RegistrationStates(StatesGroup):
    """حالات مربوط به ثبت نام"""
    waiting_for_name = State()
    waiting_for_lastname = State()
    waiting_for_nft_code = State()
    waiting_for_wallet = State()

class UserStates(StatesGroup):
    """حالات مربوط به کاربران عادی"""
    waiting_for_support_message = State()
    waiting_for_category_password = State()
    browsing_content = State()
    viewing_profile = State()

class AdminStates(StatesGroup):
    """حالات مربوط به مدیریت"""
    # مدیریت محتوا
    waiting_for_content_file = State()
    waiting_for_category = State()
    waiting_for_subcategory = State()
    waiting_for_subcategory_choice = State()
    waiting_for_new_subcategory_name = State()
    waiting_for_new_subcategory_desc = State()
    waiting_for_title = State()
    waiting_for_description = State()
    
    # مدیریت کاربران
    waiting_for_user_search = State()
    waiting_for_admin_reply = State()
    waiting_for_user_id_grant = State()
    managing_users = State()
    
    # مدیریت دسته‌ها
    waiting_for_category_name = State()
    waiting_for_category_title = State()
    waiting_for_category_desc = State()
    waiting_for_category_password = State()
    managing_categories = State()
    
    # سایر عملیات
    waiting_for_broadcast_message = State()
    waiting_for_edit_choice = State()
    waiting_for_new_content = State()
    managing_content = State()
    managing_subcategories = State()
    waiting_for_backup_confirm = State()
