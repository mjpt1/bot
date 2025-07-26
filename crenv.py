# ایجاد فایل .env جدید
env_content = """BOT_TOKEN=7587767500:AAHnaDeuQ-g27YkwbaWshqfYtMbhxMBDW70
ADMIN_IDS=8073439954,23994187
DATABASE_PATH=data/bot.db"""

with open('.env', 'w', encoding='utf-8', newline='\n') as f:
    f.write(env_content)

print("فایل .env جدید ایجاد شد")

# بررسی محتوا
with open('.env', 'r', encoding='utf-8') as f:
    print("\nمحتوای فایل:")
    print(f.read())
