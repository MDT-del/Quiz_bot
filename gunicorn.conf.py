# gunicorn.conf.py
import logging
import sys
from threading import Thread
import os # برای خواندن متغیرهای محیطی Gunicorn

# ایمپورت‌های لازم از پروژه شما
# دیگر نیازی به create_tables و bot در اینجا نیست چون توسط run_bot.py مدیریت می‌شوند
# from database import create_tables
# from bot import bot
from config import Config
# import time # برای sleep
# import mysql.connector # برای اتصال تست مستقیم

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

# def run_bot_thread_gunicorn(): # دیگر نیازی به این تابع در اینجا نیست
#     logger.info("🤖 Gunicorn: ربات تلگرام در حال راه‌اندازی از طریق هوک when_ready است...")
#     try:
#         bot.infinity_polling(none_stop=True, timeout=30, long_polling_timeout=30)
#     except Exception as e:
#         logger.exception("[Gunicorn: خطای ترد ربات] مشکلی در اجرای ربات رخ داد:")

# def check_db_connection(max_retries=12, delay_seconds=5): # این تابع هم دیگر اینجا لازم نیست
#     logger.info("در حال بررسی اولیه اتصال به دیتابیس...")
#     # ... (منطق بررسی اتصال) ...
#     return True


def when_ready(server):
    # این هوک فقط یک بار توسط پروسس master Gunicorn پس از بارگذاری برنامه اجرا می‌شود.
    logger.info("🚀 Gunicorn (web service): سرور آماده است.")

    # دیگر نیازی به بررسی اتصال دیتابیس یا ایجاد جداول یا راه‌اندازی ربات در اینجا نیست.
    # این کارها توسط سرویس bot (run_bot.py) و خود سرویس web (هنگام نیاز به دیتابیس) انجام می‌شود.
    # اگر سرویس web نیاز به بررسی اولیه دیتابیس دارد، می‌تواند اینجا انجام شود،
    # اما create_tables بهتر است توسط یک سرویس یکتا انجام شود یا idempotent باشد.
    # با توجه به اینکه run_bot.py هم create_tables را اجرا می‌کند، اینجا می‌توان آن را حذف کرد
    # یا مطمئن بود که IF NOT EXISTS به درستی کار می‌کند.

    # logger.info("🔄 Gunicorn (web service): بررسی اولیه اتصال دیتابیس...")
    # if not check_db_connection(): # اگر تابع check_db_connection هنوز وجود دارد
    #     logger.critical("❌ Gunicorn (web service): اتصال اولیه به دیتابیس برقرار نشد.")
    # else:
    #     logger.info("✅ Gunicorn (web service): اتصال اولیه به دیتابیس موفق بود.")
    #     # ممکن است بخواهید create_tables را اینجا هم اجرا کنید اگر وب سرور اولین مصرف کننده است
    #     # اما با توجه به depends_on در docker-compose، سرویس bot همزمان یا کمی بعدتر اجرا می‌شود.
    pass # فعلا کار خاصی در when_ready برای سرویس وب انجام نمی‌دهیم.


# --- تنظیمات Gunicorn ---
# این مقادیر می‌توانند از طریق متغیرهای محیطی یا مستقیم تنظیم شوند یا از CMD Dockerfile بیایند.
# مقادیر پیش‌فرض اگر در CMD Dockerfile یا متغیر محیطی تنظیم نشده باشند
bind = os.environ.get('GUNICORN_BIND', '0.0.0.0:8080')
workers = int(os.environ.get('GUNICORN_WORKERS', '1')) # همچنان 1 برای تست نگه داشته شده، بعدا می‌توانید افزایش دهید
timeout = int(os.environ.get('GUNICORN_TIMEOUT', '300')) # افزایش به 300 ثانیه
# worker_class = os.environ.get('GUNICORN_WORKER_CLASS', 'sync') # sync پیش‌فرض است
# accesslog = os.environ.get('GUNICORN_ACCESSLOG', '-') # لاگ دسترسی Gunicorn
# errorlog = os.environ.get('GUNICORN_ERRORLOG', '-')   # لاگ خطای خود Gunicorn
loglevel = os.environ.get('GUNICORN_LOGLEVEL', 'info') # سطح لاگ خود Gunicorn (می‌تواند debug باشد)

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
logger.info(f"Gunicorn timeout: {timeout}")
