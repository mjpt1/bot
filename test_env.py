import os
from pathlib import Path
from dotenv import load_dotenv

# مسیر فعلی
current_dir = Path.cwd()
print(f"مسیر فعلی: {current_dir}")

# بررسی وجود فایل .env
env_file = current_dir / '.env'
print(f"\nبررسی فایل .env در: {env_file}")
print(f"فایل وجود دارد: {env_file.exists()}")

if env_file.exists():
    # خواندن محتوای خام فایل
    with open(env_file, 'rb') as f:
        raw_content = f.read()
        print(f"\nاندازه فایل: {len(raw_content)} بایت")
        print(f"اولین 50 بایت (hex): {raw_content[:50].hex()}")
    
    # خواندن محتوا با encoding های مختلف
    for encoding in ['utf-8', 'utf-8-sig', 'utf-16', 'cp1256', 'windows-1256']:
        try:
            with open(env_file, 'r', encoding=encoding) as f:
                content = f.read()
                print(f"\n--- محتوا با {encoding} ---")
                print(repr(content[:100]))
                print("---")
        except:
            print(f"\nخطا در خواندن با {encoding}")

# بارگذاری با python-dotenv
load_dotenv(env_file, encoding='utf-8-sig')

# بررسی متغیرها
print(f"\n\nنتیجه بارگذاری:")
print(f"BOT_TOKEN: {os.getenv('BOT_TOKEN', 'NOT FOUND')}")
print(f"ADMIN_IDS: {os.getenv('ADMIN_IDS', 'NOT FOUND')}")
