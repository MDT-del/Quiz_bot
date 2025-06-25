import logging
import sys
from threading import Thread

from admin_panel import app  # آبجکت Flask شما
from database import create_tables
from bot import bot  # آبجکت TeleBot شما
from config import Config

# تنظیمات لاگینگ پایه (اگر قبلاً در main.py یا جای دیگری به طور کامل انجام نشده)
# اگر main.py دیگر به عنوان نقطه ورود اصلی برای همه چیز استفاده نمی‌شود،
# بهتر است basicConfig در اینجا یا در ابتدای admin_panel.py/bot.py باشد.
# با فرض اینکه basicConfig در main.py (که دیگر اجرا نمی‌شود) بود، آن را اینجا می‌آوریم.
logging.basicConfig(
    level=Config.LOG_LEVEL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(Config.LOG_FILE_PATH, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def run_bot_thread():
    """ربات تلگرام را در یک ترد جداگانه اجرا می‌کند."""
    logger.info("🤖 ربات تلگرام در حال راه‌اندازی از wsgi.py است...")
    try:
        bot.infinity_polling()
    except Exception as e:
        logger.exception("[خطای ترد ربات در wsgi.py] مشکلی در اجرای ربات رخ داد:")

# اجرای وظایف اولیه قبل از شروع Gunicorn
logger.info("🚀 wsgi.py: برنامه در حال شروع به کار است...")

try:
    logger.info("🔄 wsgi.py: در حال بررسی و ایجاد جداول دیتابیس (در صورت نیاز)...")
    create_tables()
    logger.info("✅ wsgi.py: جداول دیتابیس با موفقیت بررسی/ایجاد شدند.")
except Exception as e:
    logger.exception("❌ wsgi.py: خطای بحرانی در ایجاد جداول دیتابیس. Gunicorn ممکن است شروع شود اما ربات با مشکل مواجه خواهد شد.")
    # در اینجا برنامه متوقف نمی‌شود تا Gunicorn بتواند پنل وب را اجرا کند،
    # اما خطای دیتابیس باید جدی گرفته شود.

# راه‌اندازی ترد ربات
if __name__ != "__main__": # این شرط برای جلوگیری از اجرای دوباره ترد هنگام reload توسط Gunicorn است
    logger.info("🧵 wsgi.py: ترد ربات تلگرام در حال راه‌اندازی است...")
    bot_thread = Thread(target=run_bot_thread, name="TelegramBotThreadDaemon", daemon=True)
    bot_thread.start()
    logger.info("🧵 wsgi.py: ترد ربات تلگرام شروع به کار کرد.")

# متغیر app که Gunicorn از آن استفاده خواهد کرد
# app از admin_panel ایمپورت شده است.
# gunicorn --bind 0.0.0.0:8080 wsgi:app
