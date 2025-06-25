# run_bot.py
import logging
import sys
from threading import Thread # اگر هنوز می‌خواهید در ترد جداگانه باشد، هرچند برای این سرویس مستقل شاید لازم نباشد

from database import create_tables
from bot import bot # آبجکت TeleBot شما
from config import Config

# تنظیمات لاگینگ پایه
# اطمینان از اینکه نام لاگر یا فایل لاگ با سرویس وب تداخل نکند اگر روی یک هاست هستند
# یا اینکه لاگ‌ها به stdout/stderr بروند که توسط داکر مدیریت شوند.
log_level_str = Config.LOG_LEVEL
numeric_level = getattr(logging, log_level_str.upper(), logging.INFO)
logging.basicConfig(
    level=numeric_level,
    format='%(asctime)s - %(name)s - BOT_SERVICE - %(levelname)s - %(message)s', # افزودن شناسه سرویس به فرمت لاگ
    handlers=[
        # برای سادگی در محیط داکر، می‌توان فقط به stdout لاگ کرد
        # logging.FileHandler(Config.LOG_FILE_PATH + "_bot", encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("quiz_bot_service") # نام لاگر برای این سرویس

def main():
    logger.info("🚀 سرویس ربات در حال شروع به کار است...")

    try:
        logger.info("🔄 سرویس ربات: در حال بررسی و ایجاد جداول دیتابیس (در صورت نیاز)...")
        create_tables() # این تابع باید idempotent باشد (IF NOT EXISTS)
        logger.info("✅ سرویس ربات: جداول دیتابیس با موفقیت بررسی/ایجاد شدند.")
    except Exception as e:
        logger.exception("❌ سرویس ربات: خطای بحرانی در ایجاد جداول دیتابیس.")
        # در اینجا می‌توان تصمیم گرفت که آیا ربات باید متوقف شود یا خیر
        # برای مثال، اگر دیتابیس برای عملکرد ربات حیاتی است:
        # logger.critical("ربات به دلیل عدم دسترسی به دیتابیس یا عدم ایجاد صحیح جداول، متوقف می‌شود.")
        # sys.exit(1)
        # اما اگر ربات می‌تواند بدون دیتابیس هم برخی کارها را انجام دهد یا منتظر بماند، می‌توان ادامه داد.
        # فعلاً اجازه می‌دهیم ادامه پیدا کند و خطای اتصال در خود bot.py مدیریت شود.
        pass


    logger.info("🤖 سرویس ربات: ربات تلگرام در حال راه‌اندازی است...")
    try:
        # none_stop=True: ربات در صورت بروز خطاهای قابل بازیابی (مانند مشکلات موقت شبکه) متوقف نمی‌شود.
        # timeout: زمان انتظار برای getUpdates (به ثانیه)
        # long_polling_timeout: زمان انتظار سمت سرور تلگرام برای long polling (به ثانیه)
        logger.info(f"شروع infinity_polling با none_stop=True, timeout={Config.BOT_POLLING_TIMEOUT if hasattr(Config, 'BOT_POLLING_TIMEOUT') else 30}, long_polling_timeout={Config.BOT_LONG_POLLING_TIMEOUT if hasattr(Config, 'BOT_LONG_POLLING_TIMEOUT') else 30}")
        bot.infinity_polling(
            none_stop=True,
            timeout=getattr(Config, 'BOT_POLLING_TIMEOUT', 30),
            long_polling_timeout=getattr(Config, 'BOT_LONG_POLLING_TIMEOUT', 30)
        )
    except Exception as e:
        logger.exception("[سرویس ربات: خطای نهایی در ترد ربات] مشکلی در اجرای ربات رخ داد و متوقف شد:")
    finally:
        logger.info("🏁 سرویس ربات به پایان رسید یا متوقف شد.")

if __name__ == '__main__':
    main()
