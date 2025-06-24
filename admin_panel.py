from flask import Flask, render_template, request, redirect, flash, request, get_flashed_messages, url_for, abort, session
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
# from database import get_all_users, set_user_premium # Removed duplicate import
from bot import send_payment_confirmation, send_admin_response_to_user
# send_main_keyboard might not be needed in admin_panel, can be removed if unused.
# For now, keeping it to avoid breaking if it's called somewhere unexpectedly, but should be reviewed.
from bot import send_main_keyboard
from zarinpal_payment.zarinpal import ZarinPal # Assuming this is a custom or third-party library path
import jdatetime
from datetime import datetime
from config import Config
import os
from werkzeug.utils import secure_filename
import traceback # Keep for specific error handling if needed, though logger.error with exc_info=True is good
import json # Keep for JSON operations if any
import logging
import uuid # Keep for generating unique IDs

# TODO: Add CSRF protection for all POST forms (e.g., using Flask-WTF)
# from flask_wtf.csrf import CSRFProtect
# csrf = CSRFProtect(app)


app = Flask(__name__)
app.secret_key = Config.SECRET_KEY

# Configure logger for this module
# logging.basicConfig should ideally be called once in main.py
logger = logging.getLogger(__name__)

# Initialize tables if they don't exist.
# This is usually fine for development but consider migrations for production.
create_tables()

# Flask App Configurations
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

# --- Helper function for date conversion ---
def _to_shamsi(g_date_obj, date_format="%Y/%m/%d - %H:%M"):
    """Converts a Gregorian datetime object to a Shamsi string."""
    if g_date_obj and isinstance(g_date_obj, datetime):
        try:
            # Ensure g_date_obj is naive if it's timezone-aware, or handle timezone appropriately
            if g_date_obj.tzinfo is not None:
                 g_date_obj = g_date_obj.replace(tzinfo=None) # Make naive for jdatetime
            return jdatetime.datetime.fromgregorian(datetime=g_date_obj).strftime(date_format)
        except (ValueError, TypeError) as e:
            logger.warning(f"Could not convert date {g_date_obj} to Shamsi: {e}")
            return "تاریخ نامشخص"
    return None # Or "نامشخص" or "" depending on desired output for None/invalid dates

# --- Question Management ---
@app.route('/questions')
@admin_required
def manage_questions():
    questions_data = get_questions() # Assumes get_questions returns list of dicts
    # No date conversion needed for questions list view typically
    return render_template('questions.html', questions=questions_data)

def _handle_media_upload(media_file):
    """Handles media file upload and returns media_path and media_type."""
    media_path, media_type = None, None
    if media_file and media_file.filename != '' and allowed_file(media_file.filename):
        filename = secure_filename(media_file.filename)
        # Ensure UPLOAD_FOLDER exists
        if not os.path.exists(app.config['UPLOAD_FOLDER']):
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            logger.info(f"Created UPLOAD_FOLDER at {app.config['UPLOAD_FOLDER']}")

        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

        # Avoid overwriting existing files by making filename unique if necessary
        base, ext = os.path.splitext(filename)
        counter = 1
        while os.path.exists(file_path):
            filename = f"{base}_{counter}{ext}"
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            counter += 1

        media_file.save(file_path)
        media_path = os.path.join('media', filename)  # Relative path for DB and URL generation
        media_type = get_media_type(filename.rsplit('.', 1)[1].lower())
        logger.info(f"Media file {filename} uploaded to {file_path}. DB path: {media_path}, type: {media_type}")
    elif media_file and media_file.filename != '':
        # File was provided but not allowed
        flash(f"نوع فایل '{media_file.filename}' مجاز نیست. فایل‌های مجاز: {', '.join(app.config['ALLOWED_EXTENSIONS'])}", "warning")
    return media_path, media_type

@app.route('/add_question', methods=['GET', 'POST'])
@admin_required
def add_question_route():
    if request.method == 'POST':
        try:
            question_text = request.form['question_text']
            question_type = request.form.get('question_type', 'multiple_choice') # Default if not provided
            skill = request.form.get('skill')
            correct_answer_str = request.form.get('correct_answer')

            if not all([question_text, question_type, skill, correct_answer_str]):
                flash("لطفاً تمام فیلدهای الزامی (متن سوال، نوع، مهارت، شماره گزینه صحیح) را پر کنید.", "danger")
                return redirect(url_for('add_question_route'))

            correct_answer = int(correct_answer_str)

            level = request.form.get('level')
            if question_type == 'جامع':
                level = 'جامع'
            elif not level: # Skill quiz requires a level
                flash("برای آزمون مهارتی، انتخاب سطح الزامی است.", "danger")
                return redirect(url_for('add_question_route'))

            options = [opt.strip() for opt_key, opt in request.form.items() if opt_key.startswith('option') and opt.strip()]
            if not options or len(options) < 2:
                flash("حداقل دو گزینه برای سوال باید وارد شود.", "danger")
                return redirect(url_for('add_question_route'))
            if correct_answer < 0 or correct_answer >= len(options):
                flash("شماره گزینه صحیح نامعتبر است.", "danger")
                return redirect(url_for('add_question_route'))


            media_path, media_type = None, None
            if 'media_file' in request.files:
                 media_file = request.files['media_file']
                 media_path, media_type = _handle_media_upload(media_file)
                 # If _handle_media_upload flashed a warning about file type, we might want to stop
                 if media_file and media_file.filename != '' and not media_path: # Attempted upload failed validation
                     return redirect(url_for('add_question_route'))


            add_question(question_text, options, correct_answer, level, skill,
                         media_path, media_type, question_type)
            flash("سوال جدید با موفقیت اضافه شد!", "success")
            return redirect(url_for('manage_questions'))

        except ValueError:
            flash("شماره گزینه صحیح باید یک عدد باشد.", "danger")
            logger.warning("ValueError adding question, likely incorrect correct_answer format.", exc_info=True)
        except Exception as e:
            flash(f"خطا در افزودن سوال: {str(e)}", "danger")
            logger.error(f"Error adding question: {e}", exc_info=True)
        # Fall through to render template again, preserving some form data if possible (not implemented here)
        return redirect(url_for('add_question_route'))


    return render_template('add_question.html',
                           quiz_skills=Config.QUIZ_SKILLS,
                           quiz_levels=Config.QUIZ_LEVELS)


@app.route('/edit_question/<int:question_id>', methods=['GET', 'POST'])
@admin_required
def edit_question_route(question_id):
    question = get_question_by_id(question_id) # Expects dict
    if not question:
        flash("سوال یافت نشد.", "danger")
        return redirect(url_for('manage_questions'))

    if request.method == 'POST':
        try:
            question_text = request.form['question_text']
            question_type = request.form.get('question_type', question.get('question_type'))
            skill = request.form.get('skill', question.get('skill'))
            correct_answer_str = request.form.get('correct_answer')

            if not all([question_text, question_type, skill, correct_answer_str]):
                flash("لطفاً تمام فیلدهای الزامی را پر کنید.", "danger")
                return redirect(url_for('edit_question_route', question_id=question_id))

            correct_answer = int(correct_answer_str)

            level = request.form.get('level', question.get('level'))
            if question_type == 'جامع':
                level = 'جامع'
            elif not level:
                flash("برای آزمون مهارتی، انتخاب سطح الزامی است.", "danger")
                return redirect(url_for('edit_question_route', question_id=question_id))

            options = [opt.strip() for opt_key, opt in request.form.items() if opt_key.startswith('option') and opt.strip()]
            if not options or len(options) < 2:
                flash("حداقل دو گزینه برای سوال باید وارد شود.", "danger")
                return redirect(url_for('edit_question_route', question_id=question_id))
            if correct_answer < 0 or correct_answer >= len(options):
                flash("شماره گزینه صحیح نامعتبر است.", "danger")
                return redirect(url_for('edit_question_route', question_id=question_id))

            media_path, media_type = question.get('media_path'), question.get('media_type')
            if 'media_file' in request.files:
                media_file = request.files['media_file']
                if media_file and media_file.filename != '': # New file uploaded
                    # Delete old media if it exists
                    if media_path:
                        old_media_disk_path = os.path.join(app.config['UPLOAD_FOLDER'], os.path.basename(media_path))
                        if os.path.exists(old_media_disk_path):
                            try:
                                os.remove(old_media_disk_path)
                                logger.info(f"Old media file {old_media_disk_path} deleted.")
                            except OSError as oe:
                                logger.error(f"Error deleting old media file {old_media_disk_path}: {oe}", exc_info=True)

                    new_media_path, new_media_type = _handle_media_upload(media_file)
                    if media_file and not new_media_path: # Upload validation failed
                        return redirect(url_for('edit_question_route', question_id=question_id))
                    media_path, media_type = new_media_path, new_media_type
                elif request.form.get('remove_media') == '1' and media_path: # Checkbox to remove media
                    old_media_disk_path = os.path.join(app.config['UPLOAD_FOLDER'], os.path.basename(media_path))
                    if os.path.exists(old_media_disk_path):
                        try:
                            os.remove(old_media_disk_path)
                            logger.info(f"Media file {old_media_disk_path} removed by user request.")
                        except OSError as oe:
                             logger.error(f"Error deleting media file {old_media_disk_path} by user request: {oe}", exc_info=True)
                    media_path, media_type = None, None


            update_question(question_id, question_text, options,
                            correct_answer, level, skill, question_type,
                            media_path, media_type)
            flash("سوال با موفقیت ویرایش شد!", "success")
            return redirect(url_for('manage_questions'))
        except ValueError:
            flash("شماره گزینه صحیح باید یک عدد باشد.", "danger")
            logger.warning(f"ValueError editing question ID {question_id}.", exc_info=True)
        except Exception as e:
            flash(f"خطا در ویرایش سوال: {str(e)}", "danger")
            logger.error(f"Error updating question ID {question_id}: {e}", exc_info=True)
        return redirect(url_for('edit_question_route', question_id=question_id))

    # Ensure options are passed as a list of strings for the template
    if isinstance(question.get('options'), str):
        try:
            question['options_list'] = json.loads(question['options'])
        except json.JSONDecodeError:
            question['options_list'] = []
            logger.warning(f"Could not parse options JSON for question ID {question_id} in edit view.")
    elif isinstance(question.get('options'), list):
         question['options_list'] = question['options']
    else:
        question['options_list'] = []

    return render_template('edit_question.html',
                           question=question,
                           quiz_skills=Config.QUIZ_SKILLS,
                           quiz_levels=Config.QUIZ_LEVELS)


@app.route('/delete_question/<int:question_id>', methods=['POST'])
@admin_required
def delete_question_route(question_id):
    try:
        question_to_delete = get_question_by_id(question_id) # Fetch before deleting to get media_path
        if question_to_delete and question_to_delete.get('media_path'):
            filename = os.path.basename(question_to_delete['media_path'])
            media_full_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            if os.path.exists(media_full_path):
                try:
                    os.remove(media_full_path)
                    logger.info(f"Associated media file {media_full_path} deleted for question {question_id}.")
                except OSError as oe:
                    logger.error(f"Error deleting media file {media_full_path} for question {question_id}: {oe}", exc_info=True)

        deleted = delete_question(question_id) # Assuming this returns True on success
        if deleted:
            flash("سوال با موفقیت حذف شد.", "success")
        else:
            flash("خطا در حذف سوال از دیتابیس.", "danger")
    except Exception as e:
        logger.error(f"Error deleting question ID {question_id}: {e}", exc_info=True)
        flash(f"خطای پیش‌بینی نشده در حذف سوال: {str(e)}", "danger")
    return redirect(url_for('manage_questions'))

# --- Test Results ---
@app.route('/test_results')
@admin_required
def view_test_results():
    results = get_all_test_results()
    for result in results:
        result['test_date_shamsi'] = _to_shamsi(result.get('test_date'))
    return render_template('test_results.html', results=results)


@app.route('/delete_test_result/<int:test_id>', methods=['POST'])
@admin_required
def delete_test_result_route(test_id):
    try:
        deleted = delete_test_result(test_id)
        if deleted:
            flash("نتیجه آزمون با موفقیت حذف شد.", "success")
        else:
            flash("خطا در حذف نتیجه آزمون از دیتابیس.", "danger")
    except Exception as e:
        logger.error(f"Error deleting test result ID {test_id}: {e}", exc_info=True)
        flash(f"خطای پیش‌بینی نشده در حذف نتیجه آزمون: {str(e)}", "danger")
    return redirect(url_for('view_test_results'))

# --- Leaderboard ---
@app.route('/leaderboard')
@admin_required
def leaderboard():
    top_users_data = get_top_users(limit=100)
    return render_template('leaderboard.html', top_users=top_users_data)

# --- Support Messages ---
@app.route('/support_messages')
@admin_required
def view_support_messages():
    messages_data = get_all_support_messages()
    for message in messages_data:
        message['timestamp_shamsi'] = _to_shamsi(message.get('timestamp'))
        if message.get('media_path') and not message['media_path'].startswith(('http://', 'https://')):
            # Assuming media_path is relative like 'media/filename.jpg'
            # url_for('static', filename=...) is the correct way to generate URLs for static files
            message['media_url'] = url_for('static', filename=message['media_path'])
        else:
            message['media_url'] = message.get('media_path') # If it's already an absolute URL or None

    return render_template('support_messages.html', messages=messages_data)


@app.route('/respond_to_support/<int:message_id>', methods=['GET', 'POST'])
@admin_required
def respond_to_support(message_id):
    message = get_support_message_by_id(message_id)
    if not message:
        flash("پیام پشتیبانی یافت نشد.", "danger")
        return redirect(url_for('view_support_messages'))

    message['timestamp_shamsi'] = _to_shamsi(message.get('timestamp'), date_format="%Y/%m/%d - ساعت %H:%M")
    if message.get('media_path') and not message['media_path'].startswith(('http://', 'https://')):
        message['media_url'] = url_for('static', filename=message['media_path'])
    else:
        message['media_url'] = message.get('media_path')


    if request.method == 'POST':
        admin_response_text = request.form.get('admin_response', '').strip()
        if not admin_response_text:
            flash("متن پاسخ نمی‌تواند خالی باشد.", "warning")
            return render_template('respond_to_support.html', message=message)

        user_telegram_id = message.get('user_id')
        if not user_telegram_id:
            flash("شناسه کاربر برای ارسال پاسخ یافت نشد.", "danger")
            logger.error(f"User ID missing for support message ID {message_id}.")
            return redirect(url_for('view_support_messages'))

        try:
            response_sent = send_admin_response_to_user(user_telegram_id, admin_response_text)
            if response_sent:
                update_support_message_response(message_id, admin_response_text) # This updates timestamp too
                update_support_message_status(message_id, 'responded')
                flash("پاسخ با موفقیت ارسال و در دیتابیس ثبت گردید.", "success")
                logger.info(f"Admin response sent for support message ID {message_id} to user {user_telegram_id}.")
                return redirect(url_for('view_support_messages'))
            else:
                flash("خطا در ارسال پیام به کاربر از طریق ربات. پاسخ در دیتابیس ثبت نشد.", "danger")
                logger.warning(f"send_admin_response_to_user failed for user {user_telegram_id} from support message {message_id}.")
        except Exception as e:
            flash(f"خطای پیش‌بینی نشده در ارسال پاسخ: {str(e)}", "danger")
            logger.error(f"Error responding to support message ID {message_id}: {e}", exc_info=True)
        # Fall through to render template again if error

    return render_template('respond_to_support.html', message=message)


@app.route('/delete_support_message/<int:message_id>', methods=['POST'])
@admin_required
def delete_support_message_route(message_id):
    try:
        # Optionally, delete associated media file if stored locally and not referenced elsewhere
        message_to_delete = get_support_message_by_id(message_id)
        if message_to_delete and message_to_delete.get('media_path'):
            # Basic check: only delete if it seems to be a local static path
            if message_to_delete['media_path'].startswith('media/'):
                 filename = os.path.basename(message_to_delete['media_path'])
                 media_full_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                 if os.path.exists(media_full_path):
                    try:
                        os.remove(media_full_path)
                        logger.info(f"Associated media file {media_full_path} deleted for support message {message_id}.")
                    except OSError as oe:
                        logger.error(f"Error deleting media file {media_full_path} for support message {message_id}: {oe}", exc_info=True)

        deleted = delete_support_message(message_id)
        if deleted:
            flash("پیام پشتیبانی با موفقیت حذف شد.", "success")
        else:
            flash("خطا در حذف پیام پشتیبانی از دیتابیس.", "danger")
    except Exception as e:
        logger.error(f"Error deleting support message ID {message_id}: {e}", exc_info=True)
        flash(f"خطای پیش‌بینی نشده در حذف پیام پشتیبانی: {str(e)}", "danger")
    return redirect(url_for('view_support_messages'))

# --- User Management ---
@app.route('/users')
@admin_required
def manage_users():
    users_data = get_all_users()
    for user in users_data:
        user['premium_expires_at_shamsi'] = _to_shamsi(user.get('premium_expires_at'), date_format="%Y/%m/%d")
        user['join_date_shamsi'] = _to_shamsi(user.get('join_date'), date_format="%Y/%m/%d")
    return render_template('users.html', users=users_data)


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


@app.route('/verify_payment')
def verify_payment():
    authority = request.args.get('Authority')
    status = request.args.get('Status')

    if not authority or not status:
        return "<h1>اطلاعات پرداخت ناقص است.</h1>"

    payment_record = get_payment_by_authority(authority)
    if not payment_record:
        return "<h1>سفارش یافت نشد!</h1>"

    if status == 'NOK':
        update_payment_status(authority, 'failed')
        return "<h1>پرداخت ناموفق بود یا توسط شما لغو شد.</h1>"

    if status == 'OK':
        amount = payment_record['amount']

        # راه‌اندازی کلاس زرین‌پال (callback_url اینجا نیاز نیست ولی برای هماهنگی می‌نویسیم)
        zarinpal = ZarinPal(
            merchant_id=Config.ZARINPAL_MERCHANT_CODE,
            callback_url=f"{Config.REPLIT_APP_URL}/verify_payment",
            sandbox=False)

        try:
            # --- تغییر ۴: نام متد به payment_verify تغییر کرده است ---
            verify_response = zarinpal.payment_verify(amount=amount,
                                                      authority=authority)

            # ساختار پاسخ تایید را بررسی می‌کنیم (ممکن است داخل data باشد)
            # با یک print ساده می‌توانید ساختار دقیق آن را ببینید: print(verify_response)
            verify_data = verify_response.get("data", {})

            if verify_data.get("code") in [100, 101
                                           ]:  # 100=موفق, 101=قبلا تایید شده
                user_id = payment_record['user_id']
                duration = 30
                ref_id = verify_data.get('ref_id', 'N/A')

                # به‌روزرسانی وضعیت در دیتابیس
                update_payment_status(authority, 'completed')

                # فعال کردن اشتراک کاربر
                set_user_premium(user_id, duration_days=duration)

                # ارسال پیام تایید به کاربر از طریق ربات
                send_payment_confirmation(user_id, duration)

                return f"""
                    <html><head><title>تایید پرداخت</title></head>
                    <body style='font-family: sans-serif; text-align: center; padding-top: 50px;'>
                        <h1>پرداخت شما با موفقیت تایید شد.</h1>
                        <p>اشتراک ویژه شما فعال گردید. می‌توانید به ربات بازگردید.</p>
                        <p><small>شماره پیگیری: {ref_id}</small></p>
                    </body></html>
                    """
            else:
                error_message = verify_response.get("errors", {}).get(
                    "message", "خطای نامشخص")
                update_payment_status(authority, 'verification_failed')
                return f"<h1>خطا در تایید پرداخت: {error_message} (کد: {verify_data.get('code')})</h1>"

        except Exception as e:
            return f"<h1>خطای پیش‌بینی نشده در سیستم: {e}</h1>"

    return "<h1>وضعیت نامشخص.</h1>"


if __name__ == '__main__':
    pass

print("--- admin_panel.py: File imported and setup complete ---"
      )  # این خط را اضافه کنید
