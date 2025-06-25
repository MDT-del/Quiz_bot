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
    # این بخش دیگر به طور مستقیم توسط Gunicorn اجرا نخواهد شد.
    # wsgi.py اکنون مسئول راه‌اندازی اولیه و اجرای ترد ربات است.
    # این بخش می‌تواند برای اجرای محلی ربات (بدون Gunicorn) یا برای تست استفاده شود.
    # logger.info("🚀 main.py: برنامه در حال شروع به کار است (اجرای مستقیم)...")

    # # ۰. ایجاد جداول دیتابیس در صورت عدم وجود
    # try:
    #     logger.info("🔄 main.py: در حال بررسی و ایجاد جداول دیتابیس (در صورت نیاز)...")
    #     create_tables()
    #     logger.info("✅ main.py: جداول دیتابیس با موفقیت بررسی/ایجاد شدند.")
    # except Exception as e:
    #     logger.exception("❌ main.py: خطای بحرانی در ایجاد جداول دیتابیس.")
    #     sys.exit(1)

    # # ۱. ربات تلگرام را اجرا کنید (در ترد اصلی یا ترد جداگانه اگر پنل همزمان اجرا می‌شود)
    # logger.info("🤖 main.py: ربات تلگرام در حال راه‌اندازی است (اجرای مستقیم)...")
    # run_bot() # این تابع شامل bot.infinity_polling() است

    # # اگر می‌خواهید پنل Flask را همزمان با ربات در حالت توسعه اجرا کنید (بدون Gunicorn)
    # # می‌توانید کد مربوط به app.run() را از کامنت خارج کنید و ترد ربات را مانند قبل استفاده کنید.
    # # bot_thread = Thread(target=run_bot, name="TelegramBotThreadDirect", daemon=True)
    # # bot_thread.start()
    # # logger.info("🧵 main.py: ترد ربات تلگرام (اجرای مستقیم) شروع به کار کرد.")
    # # logger.info("🖥️ main.py: پنل مدیریت فلسک (اجرای مستقیم) در حال راه‌اندازی است...")
    # # try:
    # #     app.run(host=Config.WEB_HOST, port=Config.WEB_PORT, debug=True) # debug=True برای توسعه
    # # except Exception as e:
    # #     logger.exception("[خطای پنل مدیریت در main.py (اجرای مستقیم)]")

    logger.info("main.py به طور مستقیم اجرا شد. برای اجرای کامل با Gunicorn، از wsgi:app استفاده کنید.")
    # برای سادگی، فعلا فقط یک پیام لاگ می‌کنیم اگر main.py مستقیم اجرا شود.
    # اگر نیاز به اجرای ربات به تنهایی از اینجا دارید، بخش run_bot() را از کامنت خارج کنید.
    pass

