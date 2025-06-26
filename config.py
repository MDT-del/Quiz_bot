import os

class Config:
    """
    کلاس Config برای مدیریت تنظیمات برنامه از طریق متغیرهای محیطی.
    این رویکرد امنیت و انعطاف پذیری بیشتری را در استقرار فراهم می کند.
    """
    # تنظیمات مربوط به توکن ربات و شناسهٔ ادمین
    TOKEN = os.environ.get(
        'BOT_TOKEN')  # توکن ربات تلگرام، حتماً باید تنظیم شود
    CHANNEL_ID = os.environ.get(
        'CHANNEL_ID', '')  # شناسه‌ی کانال تلگرام (اختیاری، مثلاً @YourChannel)
    # لیست شناسه‌های عددی ادمین‌های تلگرام، با کاما جدا شده در متغیر محیطی
    ADMIN_IDS = [
        int(id) for id in os.environ.get('ADMIN_IDS', '').split(',')
        if id.strip().isdigit()
    ]

    QUIZ_COOLDOWN_HOURS = 24  # مثلاً 24 ساعت برای محدودیت آزمون جامع

    # ZARINPAL_MERCHANT_CODE = os.environ.get('ZARINPAL_MERCHANT_CODE') # دیگر استفاده نمی‌شود
    # PHP_SECRET_KEY = os.environ.get('PHP_SECRET_KEY', 'your-default-php-secret-key-if-not-in-env') # دیگر استفاده نمی‌شود
    
    # تنظیمات دیتابیس
    # مسیر فایل دیتابیس SQLite
    # DATABASE_PATH = os.path.join(os.path.dirname(__file__), 'data', 'quiz.db')
    # تنظیمات جدید دیتابیس MySQL
    # این مقادیر از متغیرهای محیطی خوانده می‌شوند که توسط docker-compose.yml تنظیم می‌شوند.
    MYSQL_HOST = os.environ.get('MYSQL_HOST', 'db')  # 'db' نام سرویس دیتابیس در docker-compose.yml است
    MYSQL_USER = os.environ.get('MYSQL_USER', 'root')
    MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD', 'H!dden686973') # رمز عبور پیش‌فرض اگر متغیر محیطی تنظیم نشده باشد
    MYSQL_DB = os.environ.get('MYSQL_DB', 'quiz') # نام دیتابیس پیش‌فرض اگر متغیر محیطی تنظیم نشده باشد
    MAX_QUESTIONS = 100  # حداکثر تعداد سوالات در هر آزمون برای ربات

    # تنظیمات پنل مدیریت وب (Flask)
    WEB_HOST = '0.0.0.0'  # هاست که پنل مدیریت روی آن اجرا می‌شود (0.0.0.0 برای دسترسی از همه جا)
    WEB_PORT = 8080  # پورت پنل مدیریت
    # کلید مخفی برای سشن‌های Flask (برای امنیت و جلوگیری از دستکاری سشن‌ها)
    SECRET_KEY = os.environ.get('SECRET_KEY',
                                'your-super-secret-key-please-change-this')

    # --- خطوط جدید اضافه شده برای رفع خطا ---
    # نام کاربری و رمز عبور برای ورود به پنل ادمین
    ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME',
                                    'admin')  # نام کاربری پیش‌فرض: admin
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD',
                                    'password')  # رمز عبور پیش‌فرض: password
    # ----------------------------------------

    # تنظیمات آپلود فایل
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'static', 'media')
    ALLOWED_EXTENSIONS = {
        'mp3', 'wav', 'ogg', 'mp4', 'avi', 'mov', 'jpg', 'jpeg', 'png', 'gif'
    }
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # حداکثر حجم فایل 50 مگابایت

    # آدرس پایه پنل وب برای ساخت لینک فایل‌های رسانه‌ای
    # در Replit این آدرس به صورت خودکار ساخته می‌شود. اگر نیاز بود آن را در Secrets تنظیم کنید.
    # یک پیش‌فرض مناسب برای توسعه محلی اگر متغیر محیطی تنظیم نشده باشد.
    REPLIT_APP_URL = os.environ.get('REPLIT_APP_URL', 'http://localhost:8080')

    # NEW: تعریف سطوح دشواری
    QUIZ_LEVELS = ["آسان", "متوسط", "سخت"]

    # NEW: تعریف مهارت‌ها (اینجا QUIZ_SKILLS را اضافه کردیم)
    QUIZ_SKILLS = ["گرامر", "لغت", "درک مطلب", "مکالمه"]

    # NEW: تنظیمات لاگینگ
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO').upper()
    LOG_FILE_PATH = os.path.join(os.path.dirname(__file__), 'app.log')
    
    # NEW: تنظیمات کاربران ویژه
    PREMIUM_FEATURES = {
        "مهارتی": "دسترسی به آزمون‌های مهارتی نامحدود و پیشرفته",
        "آمار_پیشرفته": "مشاهده آمار دقیق‌تر عملکرد",
        "سوالات_بیشتر": "امکان شرکت در آزمون‌هایی با تعداد سوالات بیشتر"
    }
