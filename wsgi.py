# wsgi.py
# این فایل فقط باید آبجکت 'app' را برای Gunicorn فراهم کند.
# تمام کارهای اولیه (مانند ایجاد جداول و راه‌اندازی ترد ربات)
# و همچنین تنظیمات لاگینگ پایه، توسط gunicorn.conf.py (هوک when_ready) انجام می‌شود.

from admin_panel import app as flask_app # نام را تغییر می‌دهیم تا با متغیر application تداخل نکند
from whitenoise import WhiteNoise
import os

# آبجکت اپلیکیشن Flask که توسط Gunicorn استفاده خواهد شد
# WhiteNoise اپلیکیشن Flask را wrap می‌کند تا فایل‌های استاتیک را serve کند.
# پوشه static به طور خودکار توسط WhiteNoise شناسایی می‌شود اگر در کنار فایل اصلی برنامه باشد.
# برای اطمینان بیشتر، می‌توانیم مسیر مطلق به پوشه static را به WhiteNoise بدهیم.
# مسیر پوشه static ما /app/static است (چون UPLOAD_FOLDER در config.py به /app/static/media می‌رود)

# STATIC_ROOT مسیر مطلق به پوشه static شما در داخل کانتینر است.
# Flask به طور پیش‌فرض static_folder='static' را در نظر می‌گیرد.
# UPLOAD_FOLDER از config.py: os.path.join(os.path.dirname(config.__file__), 'static', 'media')
# که می‌شود /app/static/media
# پس ریشه static باید /app/static باشد.

# WhiteNoise به طور خودکار static_folder پیش‌فرض Flask را پیدا می‌کند.
# اگر فایل‌های شما در /app/static (و زیرپوشه‌های آن مانند /app/static/media) هستند،
# و URL ها با /static/ شروع می‌شوند، WhiteNoise باید به درستی کار کند.

application = WhiteNoise(flask_app)

# اضافه کردن فایل‌های موجود در UPLOAD_FOLDER به WhiteNoise اگر خارج از static_folder اصلی باشند
# یا اگر می‌خواهیم با پیشوند URL متفاوتی serve شوند.
# در اینجا، چون UPLOAD_FOLDER (/app/static/media) زیرمجموعه STATIC_FOLDER (/app/static) است،
# WhiteNoise باید به طور خودکار آن را پوشش دهد.
# با این حال، برای صراحت بیشتر و کنترل روی پیشوند URL، می‌توانیم اضافه کنیم:
# application.add_files(os.path.join(os.getcwd(), Config.UPLOAD_FOLDER), prefix='static/media/')
# Config.UPLOAD_FOLDER باید مسیر کامل باشد یا نسبت به جایی که برنامه اجرا می‌شود.
# os.getcwd() در داخل کانتینر /app خواهد بود.
# Config.UPLOAD_FOLDER از config.py: /app/static/media
# prefix='static/media/' یعنی URLها به صورت /static/media/filename خواهند بود.
# این با چیزی که در ربات استفاده می‌کنیم (Config.REPLIT_APP_URL + '/static/' + media_path) همخوانی دارد
# که media_path خودش 'media/filename.ext' است.

# اگر Config.UPLOAD_FOLDER مسیر کامل به /app/static/media باشد:
# application.add_files(Config.UPLOAD_FOLDER, prefix='static/media/')
# یا اگر Config.UPLOAD_FOLDER فقط 'static/media' (نسبی) باشد:
# application.add_files(os.path.join(os.getcwd(), 'static', 'media'), prefix='static/media/')

# با توجه به اینکه Flask به طور پیش‌فرض /static را برای پوشه static مپ می‌کند و
# UPLOAD_FOLDER شما زیرمجموعه آن است (static/media)،
# WhiteNoise(flask_app) به تنهایی باید کافی باشد.

# import logging
# logger = logging.getLogger(__name__)
# logger.info("wsgi.py: آبجکت 'application' (Flask app wrapped با WhiteNoise) آماده برای Gunicorn.")

# Gunicorn این فایل را ایمپورت می‌کند و به دنبال متغیری به نام application می‌گردد.
