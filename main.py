# --- main.py ---

import sys
import traceback
from threading import Thread
from bot import bot
from admin_panel import app
from config import Config


def run_bot():
    """
    این تابع ربات را در یک ترد (thread) جداگانه و در پس‌زمینه اجرا می‌کند
    تا با پنل مدیریت تداخل نداشته باشد.
    """
    try:
        print("🤖 ربات تلگرام در حال راه‌اندازی است...")
        bot.infinity_polling()
    except Exception as e:
        print(f"[خطای ترد ربات] مشکلی در اجرای ربات رخ داد: {e}",
              file=sys.stderr)
        traceback.print_exc()


if __name__ == '__main__':
    # ۱. ربات تلگرام را در یک ترد پس‌زمینه (background thread) اجرا کنید.
    # با تنظیم daemon=True، این ترد با بسته شدن برنامه اصلی (پنل فلسک) به طور خودکار بسته می‌شود.
    bot_thread = Thread(target=run_bot, daemon=True)
    bot_thread.start()

    # ۲. پنل مدیریت فلسک را در ترد اصلی (main thread) اجرا کنید.
    # Replit به طور خودکار این وب سرور را شناسایی کرده و آن را به صورت عمومی در دسترس قرار می‌دهد.
    print("🖥️ پنل مدیریت در حال راه‌اندازی است...")
    try:
        print("--- main.py: Attempting to run Flask app ---") # این خط را اضافه کنید
        app.run(
            host=Config.WEB_HOST,
            port=Config.WEB_PORT,
            debug=False)
    except Exception as e:
        print(f"[خطای پنل مدیریت] مشکلی در اجرای پنل مدیریت رخ داد: {e}",
              file=sys.stderr)
        traceback.print_exc()

