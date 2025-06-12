from flask import Flask, render_template, redirect, flash, request, get_flashed_messages, url_for, abort, session
from database import (add_question, get_questions, create_tables,
                      get_question_by_id, update_question, delete_question,
                      get_all_test_results, delete_test_result, get_top_users,
                      get_all_support_messages, get_all_users,
                      get_support_message_by_id, is_user_premium,
                      update_support_message_response, delete_support_message,
                      update_support_message_status, set_user_premium,
                      get_total_user_count, get_total_question_count,
                      get_recent_quiz_count, update_payment_status,
                      get_payment_by_authority)
from bot import send_payment_confirmation
from bot import send_main_keyboard
import jdatetime
from datetime import datetime
from config import Config
import os
from werkzeug.utils import secure_filename
from bot import send_admin_response_to_user
import traceback
import json
import logging

app = Flask(__name__)
app.secret_key = Config.SECRET_KEY

logging.basicConfig(
    level=Config.LOG_LEVEL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(Config.LOG_FILE_PATH),
        logging.StreamHandler()
    ])
logger = logging.getLogger(__name__)

create_tables()

app.config['UPLOAD_FOLDER'] = Config.UPLOAD_FOLDER
app.config['ALLOWED_EXTENSIONS'] = Config.ALLOWED_EXTENSIONS
app.config['MAX_CONTENT_LENGTH'] = Config.MAX_CONTENT_LENGTH


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


def get_media_type(extension):
    audio_extensions = {'mp3', 'wav', 'ogg'}
    video_extensions = {'mp4', 'avi', 'mov'}
    image_extensions = {'jpg', 'jpeg', 'png', 'gif'}
    if extension in audio_extensions:
        return 'audio'
    elif extension in video_extensions:
        return 'video'
    elif extension in image_extensions:
        return 'image'
    return None


def admin_required(f):

    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session or not session['logged_in']:
            flash('لطفاً برای دسترسی به پنل ادمین وارد شوید.', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)

    decorated_function.__name__ = f.__name__
    return decorated_function


@app.route('/')
def index():
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username == Config.ADMIN_USERNAME and password == Config.ADMIN_PASSWORD:
            session['logged_in'] = True
            flash('با موفقیت وارد شدید!', 'success')
            logger.info(f"Admin user '{username}' logged in successfully.")
            return redirect(url_for('dashboard'))
        else:
            flash('نام کاربری یا رمز عبور اشتباه است.', 'danger')
            logger.warning(f"Failed login attempt for username: {username}")
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    flash('شما از حساب کاربری خارج شدید.', 'info')
    logger.info("Admin user logged out.")
    return redirect(url_for('login'))


@app.route('/dashboard')
@admin_required
def dashboard():
    """داشبورد را با آمارهای کلیدی نمایش می‌دهد."""
    total_users = get_total_user_count()
    total_questions = get_total_question_count()
    recent_quizzes = get_recent_quiz_count(24)  # آمار ۲۴ ساعت گذشته

    stats = {
        'total_users': total_users,
        'total_questions': total_questions,
        'recent_quizzes': recent_quizzes
    }
    return render_template('dashboard.html', stats=stats)

@app.route('/api/php/payment-callback', methods=['POST'])
def php_payment_callback():
    """
    این API Endpoint فقط توسط اسکریپت verify.php فراخوانی می‌شود.
    نتیجه تراکنش را دریافت و اشتراک کاربر را فعال می‌کند.
    """
    # ۱. بررسی کلید مخفی برای امنیت
    auth_header = request.headers.get('Authorization')
    if not auth_header or 'Bearer ' not in auth_header:
        logger.warning("PHP Callback: Missing or invalid Authorization header.")
        abort(401) # Unauthorized

    token = auth_header.split(' ')[1]
    if token != Config.PHP_SECRET_KEY:
        logger.warning("PHP Callback: Invalid secret key.")
        abort(403) # Forbidden
    
    # ۲. دریافت و پردازش داده‌های JSON
    data = request.json
    if not data:
        logger.error("PHP Callback: No JSON data received.")
        return jsonify({"status": "error", "message": "No data"}), 400

    authority = data.get('order_id')
    ref_id = data.get('ref_id')
    status = data.get('status')
    
    if not authority or status != 'completed':
        logger.warning(f"PHP Callback: Incomplete data received: {data}")
        return jsonify({"status": "error", "message": "Incomplete data"}), 400

    payment_record = get_payment_by_authority(authority)
    if not payment_record:
        logger.error(f"PHP Callback: Payment record not found for authority {authority}")
        return jsonify({"status": "error", "message": "Order not found"}), 404

    # اگر پرداخت قبلاً تکمیل شده، دوباره کاری نکن
    if payment_record['status'] == 'completed':
        logger.info(f"PHP Callback: Payment for authority {authority} already completed.")
        return jsonify({"status": "already_completed"})

    try:
        user_id = payment_record['user_id']
        duration = 30  # ۳۰ روز اشتراک
        
        # ۳. آپدیت دیتابیس و فعال‌سازی اشتراک
        update_payment_status(authority, 'completed')
        set_user_premium(user_id, duration_days=duration)
        
        # ۴. ارسال پیام تایید به کاربر
        send_payment_confirmation(user_id, duration)
        
        logger.info(f"Payment successful via PHP callback for user {user_id}, authority {authority}")
        return jsonify({"status": "success"})

    except Exception as e:
        logger.error(f"Error processing PHP callback for authority {authority}: {e}", exc_info=True)
        return jsonify({"status": "error", "message": "Internal server error"}), 500
    
@app.route('/payment-success')
def payment_success():
    ref_id = request.args.get('ref_id', 'N/A')
    return f"""
        <html><head><title>تایید پرداخت</title></head>
        <body style='font-family: sans-serif; text-align: center; padding-top: 50px;'>
            <h1>پرداخت شما با موفقیت تایید شد.</h1>
            <p>اشتراک ویژه شما فعال گردید. می‌توانید به ربات بازگردید.</p>
            <p><small>شماره پیگیری: {ref_id}</small></p>
        </body></html>
    """

@app.route('/payment-failed')
def payment_failed():
    reason = request.args.get('reason', 'unknown')
    error = request.args.get('error', 'خطای نامشخص')
    message = "<h1>پرداخت ناموفق بود.</h1>"
    if reason == 'cancelled':
        message = "<h1>پرداخت توسط شما لغو شد.</h1>"
    elif reason == 'verification_failed':
        message = f"<h1>خطا در تایید پرداخت: {error}</h1>"
        
    return f"""
        <html><head><title>پرداخت ناموفق</title></head>
        <body style='font-family: sans-serif; text-align: center; padding-top: 50px;'>
            {message}
            <p>در صورت کسر وجه از حساب شما، مبلغ تا ۷۲ ساعت آینده به حسابتان باز خواهد گشت.</p>
            <p><a href="tg://resolve?domain=YOUR_BOT_USERNAME">بازگشت به ربات</a></p>
        </body></html>
    """
    
@app.route('/questions')
@admin_required
def manage_questions():
    questions = get_questions()
    return render_template('questions.html', questions=questions)


@app.route('/add_question', methods=['GET', 'POST'])
@admin_required
def add_question_route():
    if request.method == 'POST':
        try:
            question_text = request.form['question_text']
            question_type = request.form.get('question_type')
            skill = request.form.get('skill')  # مهارت همیشه ارسال می‌شود
            correct_answer = int(request.form['correct_answer'])

            # منطق جدید برای دریافت سطح
            if question_type == 'جامع':
                level = 'جامع'  # برای سوالات جامع، یک مقدار پیش‌فرض برای سطح در نظر می‌گیریم
            else:  # برای آزمون مهارتی
                level = request.form.get('level')
                if not level:
                    flash("برای آزمون مهارتی، انتخاب سطح الزامی است.",
                          "danger")
                    return redirect(url_for('add_question_route'))

            options = []
            option_count_str = request.form.get('option_count')
            if option_count_str and option_count_str.isdigit():
                for i in range(int(option_count_str)):
                    option = request.form.get(f'option{i}')
                    if option:
                        options.append(option)

            # ... (بقیه کد آپلود فایل و ذخیره در دیتابیس بدون تغییر است)
            media_path, media_type = None, None
            media_file = request.files.get('media_file')
            # (این بخش طولانی است و نیازی به کپی مجدد نیست، کد فعلی شما درست است)

            add_question(question_text, options, correct_answer, level, skill,
                         media_path, media_type, question_type)

            flash("سوال جدید با موفقیت اضافه شد!", "success")
            return redirect(url_for('manage_questions'))

        except Exception as e:
            flash(f"خطا در افزودن سوال: {e}", "danger")
            logger.error(f"Error adding question: {e}", exc_info=True)
            return redirect(url_for('add_question_route'))

    return render_template('add_question.html',
                           quiz_skills=Config.QUIZ_SKILLS,
                           quiz_levels=Config.QUIZ_LEVELS)


@app.route('/edit_question/<int:question_id>', methods=['GET', 'POST'])
@admin_required
def edit_question_route(question_id):
    question = get_question_by_id(question_id)
    if not question:
        flash("سوال یافت نشد.", "danger")
        return redirect(url_for('manage_questions'))

    if request.method == 'POST':
        try:
            question_text = request.form['question_text']
            question_type = request.form.get('question_type')
            skill = request.form.get('skill')
            correct_answer = int(request.form['correct_answer'])

            # منطق جدید برای دریافت سطح
            if question_type == 'جامع':
                level = 'جامع'
            else:
                level = request.form.get('level')
                if not level:
                    flash("برای آزمون مهارتی، انتخاب سطح الزامی است.",
                          "danger")
                    return redirect(
                        url_for('edit_question_route',
                                question_id=question_id))

            options = []
            option_count_str = request.form.get('option_count')
            if option_count_str and option_count_str.isdigit():
                for i in range(int(option_count_str)):
                    option = request.form.get(f'option{i}')
                    if option:
                        options.append(option)

            # ... (بقیه منطق تابع ویرایش برای فایل رسانه و غیره بدون تغییر است)
            # (این بخش طولانی است و نیازی به کپی مجدد نیست، کد فعلی شما درست است)
            media_path = question['media_path']
            media_type = question['media_type']

            update_question(question_id, question_text, options,
                            correct_answer, level, skill, question_type,
                            media_path, media_type)
            flash("سوال با موفقیت ویرایش شد!", "success")
            return redirect(url_for('manage_questions'))
        except Exception as e:
            flash(f"خطا در ویرایش سوال: {e}", "danger")
            logger.error(f"Error updating question ID {question_id}: {e}",
                         exc_info=True)
            return redirect(
                url_for('edit_question_route', question_id=question_id))

    return render_template('edit_question.html',
                           question=question,
                           quiz_skills=Config.QUIZ_SKILLS,
                           quiz_levels=Config.QUIZ_LEVELS)


@app.route('/delete_question/<int:question_id>', methods=['POST'])
@admin_required
def delete_question_route(question_id):
    try:
        question = get_question_by_id(question_id)
        if question and question['media_path']:
            filename = os.path.basename(question['media_path'])
            media_full_path = os.path.join(app.config['UPLOAD_FOLDER'],
                                           filename)
            if os.path.exists(media_full_path):
                os.remove(media_full_path)
                logger.info(
                    f"Associated media file deleted: {media_full_path}")
        delete_question(question_id)
        flash("سوال با موفقیت حذف شد.", "success")
    except Exception as e:
        logger.error(f"Error deleting question ID {question_id}: {e}",
                     exc_info=True)
        flash(f"خطا در حذف سوال: {e}", "danger")
    return redirect(url_for('manage_questions'))


@app.route('/test_results')
@admin_required
def view_test_results():
    results = get_all_test_results()
    for result in results:
        if result.get('test_date'):
            try:
                g_date = datetime.strptime(result['test_date'].split('.')[0],
                                           "%Y-%m-%d %H:%M:%S")
                # تاریخ و ساعت را با هم نمایش می‌دهیم
                result['test_date_shamsi'] = jdatetime.datetime.fromgregorian(
                    datetime=g_date).strftime("%Y/%m/%d - %H:%M")
            except (ValueError, TypeError):
                result['test_date_shamsi'] = "نامشخص"
        else:
            result['test_date_shamsi'] = None

    return render_template('test_results.html', results=results)


@app.route('/delete_test_result/<int:test_id>', methods=['POST'])
@admin_required
def delete_test_result_route(test_id):
    try:
        delete_test_result(test_id)
        flash("نتیجه آزمون با موفقیت حذف شد.", "success")
    except Exception as e:
        logger.error(f"Error deleting test result ID {test_id}: {e}",
                     exc_info=True)
        flash(f"خطا در حذف نتیجه آزمون: {e}", "danger")
    return redirect(url_for('view_test_results'))


@app.route('/leaderboard')
@admin_required
def leaderboard():
    top_users = get_top_users(limit=100)
    return render_template('leaderboard.html', top_users=top_users)


@app.route('/support_messages')
@admin_required
def view_support_messages():
    messages = get_all_support_messages()
    for message in messages:
        if message.get('timestamp'):
            try:
                g_date = datetime.strptime(message['timestamp'].split('.')[0],
                                           "%Y-%m-%d %H:%M:%S")
                message['timestamp_shamsi'] = jdatetime.datetime.fromgregorian(
                    datetime=g_date).strftime("%Y/%m/%d - %H:%M")
            except (ValueError, TypeError):
                message['timestamp_shamsi'] = "نامشخص"
        else:
            message['timestamp_shamsi'] = None

    return render_template('support_messages.html', messages=messages)


@app.route('/respond_to_support/<int:message_id>', methods=['GET', 'POST'])
@admin_required
def respond_to_support(message_id):
    message = get_support_message_by_id(message_id)
    if not message:
        flash("پیام پشتیبانی یافت نشد.", "danger")
        return redirect(url_for('view_support_messages'))

    # تبدیل تاریخ برای نمایش در صفحه
    if message.get('timestamp'):
        try:
            g_date = datetime.strptime(message['timestamp'].split('.')[0],
                                       "%Y-%m-%d %H:%M:%S")
            message['timestamp_shamsi'] = jdatetime.datetime.fromgregorian(
                datetime=g_date).strftime("%Y/%m/%d - ساعت %H:%M")
        except (ValueError, TypeError):
            message['timestamp_shamsi'] = "نامشخص"
    else:
        message['timestamp_shamsi'] = None

    if request.method == 'POST':
        admin_response_text = request.form['admin_response']
        user_telegram_id = message['user_id']
        try:
            send_admin_response_to_user(user_telegram_id, admin_response_text)
            update_support_message_response(message_id, admin_response_text)
            update_support_message_status(message_id, 'responded')
            flash("پاسخ با موفقیت ارسال شد و در دیتابیس ثبت گردید.", "success")
            return redirect(url_for('view_support_messages'))
        except Exception as e:
            flash(f"خطا در ارسال پاسخ یا ثبت در دیتابیس: {e}", "danger")
            logger.error(
                f"Error responding to support message ID {message_id}: {e}",
                exc_info=True)

    return render_template('respond_to_support.html', message=message)


@app.route('/delete_support_message/<int:message_id>', methods=['POST'])
@admin_required
def delete_support_message_route(message_id):
    try:
        delete_support_message(message_id)
        flash("پیام پشتیبانی با موفقیت حذف شد.", "success")
    except Exception as e:
        logger.error(f"Error deleting support message ID {message_id}: {e}",
                     exc_info=True)
        flash(f"خطا در حذف پیام پشتیبانی: {e}", "danger")
    return redirect(url_for('view_support_messages'))


@app.route('/users')
@admin_required
def manage_users():
    """صفحه مدیریت کاربران را با تاریخ‌های شمسی نمایش می‌دهد."""
    users = get_all_users()
    for user in users:
        # تبدیل تاریخ انقضای اشتراک
        if user.get('premium_expires_at'):
            try:
                g_date = datetime.strptime(
                    user['premium_expires_at'].split('.')[0],
                    "%Y-%m-%d %H:%M:%S")
                user[
                    'premium_expires_at_shamsi'] = jdatetime.datetime.fromgregorian(
                        datetime=g_date).strftime("%Y/%m/%d")
            except (ValueError, TypeError):
                user['premium_expires_at_shamsi'] = "نامشخص"
        else:
            user['premium_expires_at_shamsi'] = None

        # تبدیل تاریخ عضویت
        if user.get('join_date'):
            try:
                g_date = datetime.strptime(user['join_date'].split('.')[0],
                                           "%Y-%m-%d %H:%M:%S")
                user['join_date_shamsi'] = jdatetime.datetime.fromgregorian(
                    datetime=g_date).strftime("%Y/%m/%d")
            except (ValueError, TypeError):
                user['join_date_shamsi'] = "نامشخص"
        else:
            user['join_date_shamsi'] = None

    return render_template('users.html', users=users)


@app.route('/toggle_premium/<int:user_id>', methods=['POST'])
@admin_required
def toggle_premium(user_id):
    """وضعیت کاربری ویژه یک کاربر را تغییر می‌دهد."""
    duration_str = request.form.get('duration', '30')  # به طور پیش‌فرض ۳۰ روزه

    # اگر دکمه "لغو دسترسی" زده شده باشد
    if 'revoke' in request.form:
        duration_days = 0
    else:
        try:
            duration_days = int(duration_str)
            if duration_days <= 0:
                flash("مدت زمان باید یک عدد مثبت باشد.", "danger")
                return redirect(url_for('manage_users'))
        except ValueError:
            flash("لطفاً یک عدد معتبر برای مدت زمان وارد کنید.", "danger")
            return redirect(url_for('manage_users'))

    set_user_premium(user_id, duration_days)

    if duration_days > 0:
        flash(
            f"اشتراک ویژه برای کاربر {user_id} به مدت {duration_days} روز فعال شد.",
            "success")
    else:
        flash(f"اشتراک ویژه کاربر {user_id} لغو شد.", "info")

    return redirect(url_for('manage_users'))


if __name__ == '__main__':
    pass
