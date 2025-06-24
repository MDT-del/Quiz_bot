# --- main.py ---

import sys
import traceback
from threading import Thread
import logging # Added
from database import create_tables # Added
from bot import bot
from admin_panel import app
from config import Config

# Configure logging at the entry point of the application
# This basicConfig should be the only one. Other modules use logging.getLogger(__name__)
logging.basicConfig(
    level=Config.LOG_LEVEL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(Config.LOG_FILE_PATH, encoding='utf-8'), # Added encoding
        logging.StreamHandler(sys.stdout) # Ensure logs go to stdout as well
    ]
)
logger = logging.getLogger(__name__)


def run_bot():
    """
    این تابع ربات را در یک ترد (thread) جداگانه و در پس‌زمینه اجرا می‌کند
    تا با پنل مدیریت تداخل نداشته باشد.
    """
    try:
        logger.info("🤖 ربات تلگرام در حال راه‌اندازی است...")
        bot.infinity_polling()
    except Exception as e:
        logger.exception("[خطای ترد ربات] مشکلی در اجرای ربات رخ داد:") # logger.exception includes traceback


if __name__ == '__main__':
    logger.info("🚀 برنامه در حال شروع به کار است...")

    # ۰. ایجاد جداول دیتابیس در صورت عدم وجود
    try:
        logger.info("🔄 در حال بررسی و ایجاد جداول دیتابیس (در صورت نیاز)...")
        create_tables()
        logger.info("✅ جداول دیتابیس با موفقیت بررسی/ایجاد شدند.")
    except Exception as e:
        logger.exception("❌ خطای بحرانی در ایجاد جداول دیتابیس. برنامه متوقف می‌شود.")
        sys.exit(1) # Exit if database setup fails

    # ۱. ربات تلگرام را در یک ترد پس‌زمینه (background thread) اجرا کنید.
    # با تنظیم daemon=True، این ترد با بسته شدن برنامه اصلی (پنل فلسک) به طور خودکار بسته می‌شود.
    bot_thread = Thread(target=run_bot, name="TelegramBotThread", daemon=True)
    bot_thread.start()
    logger.info("🧵 ترد ربات تلگرام شروع به کار کرد.")

    # ۲. پنل مدیریت فلسک را در ترد اصلی (main thread) اجرا کنید.
    logger.info("🖥️ پنل مدیریت در حال راه‌اندازی است...")
    try:
        # استفاده از سرور WSGI مناسب‌تر برای پروداکشن است، اما برای توسعه app.run کافیست.
        # مثال با waitess:
        # from waitress import serve
        # serve(app, host=Config.WEB_HOST, port=Config.WEB_PORT)
        app.run(
            host=Config.WEB_HOST,
            port=Config.WEB_PORT,
            debug=False # debug=False برای محیط پروداکشن/استیجینگ
        )
    except Exception as e:
        logger.exception("[خطای پنل مدیریت] مشکلی در اجرای پنل مدیریت رخ داد:")

    logger.info(" برنامه به پایان رسید.")

