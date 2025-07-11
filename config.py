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

    # کد مرچنت زرین‌پال
    ZARINPAL_MERCHANT_CODE = os.environ.get('ZARINPAL_MERCHANT_CODE')

    # --- کلید مخفی برای ارتباط امن بین PHP و Python ---
    # این کلید باید در هر دو طرف (PHP و Python) یکسان باشد.
    PHP_SECRET_KEY = os.environ.get('PHP_SECRET_KEY', 'a-very-strong-secret-between-php-and-python')
    # --------------------------------------------------
    
    # تنظیمات دیتابیس
    # مسیر فایل دیتابیس SQLite
    # DATABASE_PATH = os.path.join(os.path.dirname(__file__), 'data', 'quiz.db')
    # تنظیمات جدید دیتابیس MySQL
    MYSQL_HOST = '127.0.0.1'
    MYSQL_USER = 'root'
    MYSQL_PASSWORD = 'H!dden686973'
    MYSQL_DB = 'quiz' # نام دیتابیسی که ساختیم
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
    REPLIT_APP_URL = os.environ.get('REPLIT_APP_URL', '')

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
