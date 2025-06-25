# gunicorn.conf.py
import logging
import sys
from threading import Thread
import os # برای خواندن متغیرهای محیطی Gunicorn

# ایمپورت‌های لازم از پروژه شما
from database import create_tables
from bot import bot # آبجکت TeleBot شما
from config import Config
import time # برای sleep
import mysql.connector # برای اتصال تست مستقیم

# logger را برای این فایل هم تعریف می‌کنیم
# اطمینان از اینکه لاگینگ پایه قبلاً تنظیم شده (مثلاً در wsgi.py یا اینجا)
if not logging.getLogger().hasHandlers(): # جلوگیری از تنظیم چندباره
    log_level_str = os.environ.get('LOG_LEVEL', Config.LOG_LEVEL) # استفاده از Config برای مقدار پیش‌فرض
    # تبدیل رشته سطح لاگ به مقدار عددی متناظر در logging
    numeric_level = getattr(logging, log_level_str.upper(), logging.INFO)
    logging.basicConfig(
        level=numeric_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(Config.LOG_FILE_PATH, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
logger = logging.getLogger(__name__) # لاگر برای این ماژول

def run_bot_thread_gunicorn():
    logger.info("🤖 Gunicorn: ربات تلگرام در حال راه‌اندازی از طریق هوک when_ready است...")
    try:
        # none_stop=True برای جلوگیری از توقف در برخی خطاها و تلاش مجدد
        # timeout و long_polling_timeout را هم می‌توان برای کنترل بهتر تنظیم کرد
        bot.infinity_polling(none_stop=True, timeout=30, long_polling_timeout=30)
    except Exception as e:
        logger.exception("[Gunicorn: خطای ترد ربات] مشکلی در اجرای ربات رخ داد:")

def check_db_connection(max_retries=12, delay_seconds=5): # افزایش تعداد تلاش‌ها و تاخیر اولیه
    logger.info("در حال بررسی اولیه اتصال به دیتابیس...")
    for attempt in range(max_retries):
        try:
            conn_test_args = {
                'host': Config.MYSQL_HOST,
                'user': Config.MYSQL_USER,
                'password': Config.MYSQL_PASSWORD,
                'database': Config.MYSQL_DB,
                'connection_timeout': 10 # اضافه کردن timeout برای اتصال
            }
            # logger.debug(f"تلاش برای اتصال با: {conn_test_args}")
            conn = mysql.connector.connect(**conn_test_args)
            conn.close()
            logger.info("اتصال اولیه به دیتابیس با موفقیت برقرار شد.")
            return True
        except mysql.connector.Error as err:
            logger.warning(f"تلاش {attempt + 1}/{max_retries} برای اتصال به دیتابیس ناموفق بود: {err}")
            if attempt < max_retries - 1:
                logger.info(f"تلاش مجدد پس از {delay_seconds} ثانیه...")
                time.sleep(delay_seconds)
            else:
                logger.error("عدم موفقیت در برقراری اتصال اولیه به دیتابیس پس از چندین تلاش.")
                return False
        except Exception as e: # سایر خطاهای احتمالی
            logger.error(f"خطای پیش‌بینی نشده در check_db_connection تلاش {attempt + 1}: {e}", exc_info=True)
            if attempt < max_retries - 1:
                time.sleep(delay_seconds)
            else:
                return False
    return False


def when_ready(server):
    # این هوک فقط یک بار توسط پروسس master Gunicorn پس از بارگذاری برنامه اجرا می‌شود.
    logger.info("🚀 Gunicorn: سرور آماده است. اجرای وظایف اولیه...")

    if not check_db_connection():
        logger.critical("❌ Gunicorn: اتصال اولیه به دیتابیس برقرار نشد. برنامه ممکن است به درستی کار نکند یا متوقف شود.")
        # server.stop() # در صورت نیاز Gunicorn را متوقف کنید
        # return # یا فقط از ادامه راه‌اندازی ربات و جداول جلوگیری کنید
        # فعلا اجازه می‌دهیم Gunicorn ادامه دهد تا پنل وب (حداقل) در دسترس باشد، اما ربات و دیتابیس مشکل خواهند داشت.
    else:
        try:
            logger.info("🔄 Gunicorn: در حال بررسی و ایجاد جداول دیتابیس...")
            create_tables()
            logger.info("✅ Gunicorn: جداول دیتابیس با موفقیت بررسی/ایجاد شدند.")
        except Exception as e:
            logger.exception("❌ Gunicorn: خطای بحرانی در ایجاد جداول دیتابیس.")

        logger.info("🧵 Gunicorn: ترد ربات تلگرام در حال راه‌اندازی است...")
        bot_thread = Thread(target=run_bot_thread_gunicorn, name="TelegramBotThreadGunicorn", daemon=True)
        bot_thread.start()
        logger.info("🧵 Gunicorn: ترد ربات تلگرام شروع به کار کرد.")

# --- تنظیمات Gunicorn ---
# این مقادیر می‌توانند از طریق متغیرهای محیطی یا مستقیم تنظیم شوند
# مقادیر پیش‌فرض اگر در CMD Dockerfile یا متغیر محیطی تنظیم نشده باشند
bind = os.environ.get('GUNICORN_BIND', '0.0.0.0:8080')
workers = int(os.environ.get('GUNICORN_WORKERS', '2')) # کاهش به ۲ برای تست اولیه، می‌توانید بعداً افزایش دهید
timeout = int(os.environ.get('GUNICORN_TIMEOUT', '120'))
# worker_class = os.environ.get('GUNICORN_WORKER_CLASS', 'sync') # sync پیش‌فرض است
# accesslog = os.environ.get('GUNICORN_ACCESSLOG', '-') # لاگ دسترسی Gunicorn
# errorlog = os.environ.get('GUNICORN_ERRORLOG', '-')   # لاگ خطای خود Gunicorn
# loglevel = os.environ.get('GUNICORN_LOGLEVEL', 'info') # سطح لاگ خود Gunicorn

# برای استفاده از لاگینگ پایتون برای Gunicorn (اختیاری اما برای یکپارچگی خوب است)
# logconfig_dict = {
#     'version': 1,
#     'disable_existing_loggers': False, # مهم برای اینکه لاگرهای دیگر غیرفعال نشوند
#     'formatters': {
#         'default': {
#             'format': '%(asctime)s [%(process)d] [%(levelname)s] %(message)s',
#             'datefmt': '[%Y-%m-%d %H:%M:%S %z]',
#         }
#     },
#     'handlers': {
#         'console': {
#             'class': 'logging.StreamHandler',
#             'formatter': 'default',
#             'stream': 'ext://sys.stdout'
#         },
#         'error_file_handler': {
#             'class': 'logging.handlers.RotatingFileHandler',
#             'formatter': 'default',
#             'filename': Config.LOG_FILE_PATH, # استفاده از مسیر لاگ پروژه
#             'maxBytes': 10485760,  # 10MB
#             'backupCount': 20,
#             'encoding': 'utf8'
#         }
#     },
#     'loggers': {
#         'gunicorn.error': {
#             'handlers': ['console', 'error_file_handler'],
#             'level': os.environ.get('GUNICORN_LOGLEVEL', 'INFO').upper(),
#             'propagate': False,
#         },
#         'gunicorn.access': {
#             'handlers': ['console', 'error_file_handler'], # لاگ دسترسی هم به فایل برود
#             'level': os.environ.get('GUNICORN_LOGLEVEL', 'INFO').upper(),
#             'propagate': False,
#         }
#     },
#     'root': { # تنظیم لاگر ریشه برای گرفتن لاگ‌های برنامه شما
#         'level': Config.LOG_LEVEL.upper(),
#         'handlers': ['console', 'error_file_handler']
#     }
# }

logger.info(f"Gunicorn bind: {bind}")
logger.info(f"Gunicorn workers: {workers}")
