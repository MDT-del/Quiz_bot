from flask import Flask, render_template, request, redirect, flash, url_for, abort, session, jsonify
from database import (
    add_question, get_questions, create_tables, get_question_by_id, update_question, delete_question,
    get_all_test_results, delete_test_result, get_top_users, get_all_support_messages, get_all_users,
    get_support_message_by_id, update_support_message_response, delete_support_message,
    update_support_message_status, set_user_premium, get_total_user_count, get_total_question_count,
    get_recent_quiz_count, update_payment_status, get_payment_by_authority
)
from bot import send_payment_confirmation, send_admin_response_to_user, send_main_keyboard
import jdatetime
from datetime import datetime
from config import Config
import os
from werkzeug.utils import secure_filename
import logging
import uuid
import json # برای پارس کردن آپشن‌ها در روت ویرایش اگر به صورت JSON باشند

# TODO: Add CSRF protection for all POST forms (e.g., using Flask-WTF)

app = Flask(__name__, template_folder='Templates')
app.secret_key = Config.SECRET_KEY

logger = logging.getLogger(__name__)

try:
    # create_tables() # این تابع توسط run_bot.py فراخوانی می‌شود. اگر وب سرور هم نیاز به اطمینان از وجود جداول دارد، می‌توان آن را اینجا هم فراخوانی کرد.
    # با توجه به depends_on در docker-compose، سرویس bot (که create_tables را اجرا می‌کند) باید قبل یا همزمان با web آماده شود.
    # برای جلوگیری از فراخوانی چندباره غیرضروری، فعلا اینجا کامنت می‌کنیم.
    logger.info("admin_panel.py: App initialized. Database tables should be handled by bot service or an init step.")
except Exception as e:
    logger.error(f"admin_panel.py: Error during initial setup (if create_tables was called): {e}", exc_info=True)


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
    if extension in audio_extensions: return 'audio'
    elif extension in video_extensions: return 'video'
    elif extension in image_extensions: return 'image'
    return None

def _to_shamsi(g_date_obj, date_format="%Y/%m/%d - %H:%M"):
    if g_date_obj and isinstance(g_date_obj, datetime):
        try:
            if g_date_obj.tzinfo is not None: g_date_obj = g_date_obj.replace(tzinfo=None)
            return jdatetime.datetime.fromgregorian(datetime=g_date_obj).strftime(date_format)
        except (ValueError, TypeError) as e:
            logger.warning(f"Could not convert date {g_date_obj} to Shamsi: {e}")
            return "تاریخ نامشخص"
    return None

def admin_required(f):
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session or not session['logged_in']:
            flash('لطفاً برای دسترسی به پنل ادمین وارد شوید.', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

def _handle_media_upload(media_file):
    logger.debug("--- _handle_media_upload: تابع شروع شد ---")
    if not media_file or not media_file.filename:
        logger.debug("_handle_media_upload: فایلی انتخاب نشده یا نام فایل خالی است.")
        return None, None

    logger.debug(f"_handle_media_upload: فایل دریافتی: {media_file.filename}, ContentType: {media_file.content_type}, ContentLength: {media_file.content_length}")

    if not allowed_file(media_file.filename):
        flash(f"نوع فایل '{media_file.filename}' مجاز نیست. فایل‌های مجاز: {', '.join(app.config['ALLOWED_EXTENSIONS'])}", "warning")
        logger.warning(f"_handle_media_upload: آپلود ناموفق برای '{media_file.filename}': نوع فایل نامعتبر.")
        return None, None

    original_filename = secure_filename(media_file.filename)
    logger.debug(f"_handle_media_upload: نام فایل اصلی پس از secure_filename: {original_filename}")
    base, ext = os.path.splitext(original_filename)

    upload_folder_abs_path = app.config['UPLOAD_FOLDER']
    logger.debug(f"_handle_media_upload: مسیر پوشه آپلود مطلق: {upload_folder_abs_path}")

    if not os.path.exists(upload_folder_abs_path):
        try:
            os.makedirs(upload_folder_abs_path, exist_ok=True)
            logger.info(f"_handle_media_upload: پوشه آپلود در {upload_folder_abs_path} ایجاد شد.")
        except OSError as e:
            logger.error(f"_handle_media_upload: خطا در ایجاد پوشه آپلود '{upload_folder_abs_path}': {e}", exc_info=True)
            flash(f"خطا در ایجاد پوشه آپلود روی سرور: {e}", "danger")
            return None, None

    filename_to_save = original_filename
    file_path_to_save_on_disk = os.path.join(upload_folder_abs_path, filename_to_save)
    logger.debug(f"_handle_media_upload: مسیر اولیه برای ذخیره: {file_path_to_save_on_disk}")

    counter = 1
    while os.path.exists(file_path_to_save_on_disk):
        logger.debug(f"_handle_media_upload: فایل در مسیر '{file_path_to_save_on_disk}' از قبل وجود دارد. در حال ساخت نام جدید...")
        filename_to_save = f"{base}_{counter}{ext}"
        file_path_to_save_on_disk = os.path.join(upload_folder_abs_path, filename_to_save)
        logger.debug(f"_handle_media_upload: نام و مسیر جدید برای ذخیره: {filename_to_save}, {file_path_to_save_on_disk}")
        counter += 1

    logger.info(f"_handle_media_upload: تصمیم نهایی برای ذخیره فایل با نام '{filename_to_save}' در مسیر '{file_path_to_save_on_disk}'")

    try:
        logger.debug(f"_handle_media_upload: در حال تلاش برای اجرای media_file.save('{file_path_to_save_on_disk}')...")
        media_file.save(file_path_to_save_on_disk)
        logger.info(f"_handle_media_upload: دستور media_file.save() برای '{file_path_to_save_on_disk}' اجرا شد.")

        if not os.path.exists(file_path_to_save_on_disk):
            logger.error(f"_handle_media_upload: فایل '{filename_to_save}' پس از ذخیره در مسیر '{file_path_to_save_on_disk}' وجود ندارد!")
            flash(f"خطا: فایل '{original_filename}' پس از آپلود روی سرور یافت نشد.", "danger")
            return None, None

        file_size = os.path.getsize(file_path_to_save_on_disk)
        logger.info(f"_handle_media_upload: فایل '{filename_to_save}' در مسیر '{file_path_to_save_on_disk}' با حجم {file_size} بایت ذخیره شد.")

        if file_size == 0:
            logger.error(f"_handle_media_upload: فایل '{filename_to_save}' پس از ذخیره، حجم صفر دارد.")
            flash(f"خطا در ذخیره فایل رسانه '{original_filename}'. فایل خالی ذخیره شد.", "danger")
            try:
                os.remove(file_path_to_save_on_disk)
                logger.info(f"_handle_media_upload: فایل خالی '{file_path_to_save_on_disk}' حذف شد.")
            except OSError as del_err:
                logger.error(f"_handle_media_upload: خطا در حذف فایل خالی '{file_path_to_save_on_disk}': {del_err}")
            return None, None

        media_path_for_db = os.path.join('media', filename_to_save)
        media_type = get_media_type(filename_to_save.rsplit('.', 1)[1].lower())

        logger.info(f"_handle_media_upload: فایل رسانه '{original_filename}' با نام نهایی '{filename_to_save}' با موفقیت پردازش شد. مسیر دیتابیس: '{media_path_for_db}', نوع: {media_type}")
        return media_path_for_db, media_type

    except Exception as e:
        logger.error(f"_handle_media_upload: خطای پیش‌بینی نشده در ذخیره فایل رسانه '{original_filename}' به نام '{filename_to_save}': {e}", exc_info=True)
        flash(f"خطای پیش‌بینی نشده در ذخیره فایل رسانه: {e}", "danger")
        if os.path.exists(file_path_to_save_on_disk):
            try:
                os.remove(file_path_to_save_on_disk)
                logger.info(f"_handle_media_upload: فایل ناقص '{file_path_to_save_on_disk}' پس از خطا حذف شد.")
            except OSError as del_err:
                 logger.error(f"_handle_media_upload: خطا در حذف فایل ناقص '{file_path_to_save_on_disk}' پس از خطا: {del_err}")
        return None, None

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
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
    total_users = get_total_user_count()
    total_questions = get_total_question_count()
    recent_quizzes = get_recent_quiz_count(24)
    stats = {
        'total_users': total_users,
        'total_questions': total_questions,
        'recent_quizzes': recent_quizzes
    }
    return render_template('dashboard.html', stats=stats)

@app.route('/questions')
@admin_required
def manage_questions():
    questions_data = get_questions()
    return render_template('questions.html', questions=questions_data)

@app.route('/add_question', methods=['GET', 'POST'])
@admin_required
def add_question_route():
    if request.method == 'POST':
        try:
            question_text = request.form['question_text']
            question_type = request.form.get('question_type', 'multiple_choice')
            skill = request.form.get('skill')
            correct_answer_str = request.form.get('correct_answer')

            if not all([question_text, question_type, skill, correct_answer_str]):
                flash("لطفاً تمام فیلدهای الزامی (متن سوال، نوع، مهارت، شماره گزینه صحیح) را پر کنید.", "danger")
                return redirect(url_for('add_question_route'))

            correct_answer = int(correct_answer_str)
            level = request.form.get('level')
            if question_type == 'جامع':
                level = 'جامع'
            elif not level:
                flash("برای آزمون مهارتی، انتخاب سطح الزامی است.", "danger")
                return redirect(url_for('add_question_route'))

            # اصلاح شده برای جلوگیری از خواندن option_count و سایر فیلدهای ناخواسته به عنوان یک گزینه
            options = []
            # استخراج گزینه‌ها بر اساس ترتیب عددی در نام فیلد (option0, option1, ...)
            i = 0
            while True:
                option_key = f'option{i}'
                if option_key in request.form:
                    value = request.form.get(option_key, '').strip()
                    if value: # فقط مقادیر غیرخالی را اضافه کن
                        options.append(value)
                    else: # اگر یک گزینه خالی در وسط باشد، متوقف می‌شویم یا می‌توانیم ادامه دهیم و خالی‌ها را نادیده بگیریم
                        # برای حفظ ترتیب و جلوگیری از گزینه‌های خالی ناخواسته، بهتر است اگر خالی بود، متوقف شویم
                        # یا اینکه کاربر باید تمام گزینه‌های مورد نظر را پر کند.
                        # فعلا فرض می‌کنیم کاربر گزینه‌های متوالی را پر می‌کند.
                        pass # یا break اگر نمی‌خواهید گزینه‌های خالی بعدی را هم چک کنید
                else:
                    # اولین optionX که پیدا نشد، یعنی گزینه‌های بیشتری وجود ندارد.
                    break
                i += 1

            logger.debug(f"Parsed options in add_question: {options}")

            if not options or len(options) < 2:
                flash("حداقل دو گزینه برای سوال باید وارد شود و گزینه‌ها نمی‌توانند خالی باشند.", "danger")
                return redirect(url_for('add_question_route'))
            if correct_answer < 0 or correct_answer >= len(options):
                flash("شماره گزینه صحیح نامعتبر است.", "danger")
                return redirect(url_for('add_question_route'))

            media_path, media_type = None, None
            if 'media_file' in request.files:
                 media_file = request.files['media_file']
                 if media_file and media_file.filename != '':
                     media_path, media_type = _handle_media_upload(media_file)
                     if not media_path and media_file.filename : # آپلود ناموفق بود اما فایلی انتخاب شده بود
                         return redirect(url_for('add_question_route'))

            add_question(question_text, options, correct_answer, level, skill,
                         media_path, media_type, question_type)
            flash("سوال جدید با موفقیت اضافه شد!", "success")
            return redirect(url_for('manage_questions'))

        except ValueError:
            flash("شماره گزینه صحیح باید یک عدد باشد یا فرمت گزینه‌ها نامعتبر است.", "danger")
            logger.warning("ValueError adding question.", exc_info=True)
        except Exception as e:
            flash(f"خطا در افزودن سوال: {str(e)}", "danger")
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

            # اصلاح شده برای جلوگیری از خواندن option_count و سایر فیلدهای ناخواسته به عنوان یک گزینه
            options = []
            i = 0
            while True:
                option_key = f'option{i}'
                if option_key in request.form:
                    value = request.form.get(option_key, '').strip()
                    if value:
                        options.append(value)
                else:
                    break
                i += 1
            logger.debug(f"Parsed options in edit_question: {options}")

            if not options or len(options) < 2:
                flash("حداقل دو گزینه برای سوال باید وارد شود و گزینه‌ها نمی‌توانند خالی باشند.", "danger")
                return redirect(url_for('edit_question_route', question_id=question_id))
            if correct_answer < 0 or correct_answer >= len(options):
                flash("شماره گزینه صحیح نامعتبر است.", "danger")
                return redirect(url_for('edit_question_route', question_id=question_id))

            current_media_path, current_media_type = question.get('media_path'), question.get('media_type')
            new_media_path, new_media_type = current_media_path, current_media_type

            if 'media_file' in request.files:
                media_file = request.files['media_file']
                if media_file and media_file.filename != '':
                    if current_media_path:
                        old_media_disk_path = os.path.join(app.config['UPLOAD_FOLDER'], os.path.basename(current_media_path))
                        if os.path.exists(old_media_disk_path):
                            try: os.remove(old_media_disk_path); logger.info(f"فایل رسانه قدیمی {old_media_disk_path} حذف شد.")
                            except OSError as oe: logger.error(f"خطا در حذف فایل رسانه قدیمی {old_media_disk_path}: {oe}", exc_info=True)

                    uploaded_path, uploaded_type = _handle_media_upload(media_file)
                    if not uploaded_path and media_file.filename: # آپلود ناموفق بود اما فایلی انتخاب شده بود
                        return redirect(url_for('edit_question_route', question_id=question_id))
                    new_media_path, new_media_type = uploaded_path, uploaded_type

            elif request.form.get('remove_media') == '1' and current_media_path:
                old_media_disk_path = os.path.join(app.config['UPLOAD_FOLDER'], os.path.basename(current_media_path))
                if os.path.exists(old_media_disk_path):
                    try: os.remove(old_media_disk_path); logger.info(f"فایل رسانه {old_media_disk_path} به درخواست کاربر حذف شد.")
                    except OSError as oe: logger.error(f"خطا در حذف فایل رسانه {old_media_disk_path}: {oe}", exc_info=True); flash("خطا در حذف فایل رسانه از سرور.", "warning")
                new_media_path, new_media_type = None, None

            update_question(question_id, question_text, options, correct_answer, level, skill, question_type, new_media_path, new_media_type)
            flash("سوال با موفقیت ویرایش شد!", "success")
            return redirect(url_for('manage_questions'))
        except ValueError:
            flash("شماره گزینه صحیح باید یک عدد باشد یا فرمت گزینه‌ها نامعتبر است.", "danger")
            logger.warning(f"ValueError editing question ID {question_id}.", exc_info=True)
        except Exception as e:
            flash(f"خطا در ویرایش سوال: {str(e)}", "danger")
            logger.error(f"Error updating question ID {question_id}: {e}", exc_info=True)
        return redirect(url_for('edit_question_route', question_id=question_id))

    # برای نمایش گزینه‌ها در فرم ویرایش، اگر به صورت JSON ذخیره شده‌اند، آنها را پارس می‌کنیم.
    # این کار قبلاً در database.py انجام می‌شد، اما برای اطمینان اینجا هم بررسی می‌کنیم.
    question_options = question.get('options', [])
    if isinstance(question_options, str):
        try:
            question['options_list'] = json.loads(question_options)
        except json.JSONDecodeError:
            question['options_list'] = []
            logger.warning(f"Could not parse options JSON for question ID {question_id} in edit view: {question_options}")
    elif isinstance(question_options, list):
         question['options_list'] = question_options
    else:
        question['options_list'] = [] # یا مقدار پیش‌فرض دیگر

    return render_template('edit_question.html', question=question, quiz_skills=Config.QUIZ_SKILLS, quiz_levels=Config.QUIZ_LEVELS)

@app.route('/delete_question/<int:question_id>', methods=['POST'])
@admin_required
def delete_question_route(question_id):
    try:
        question_to_delete = get_question_by_id(question_id)
        if question_to_delete and question_to_delete.get('media_path'):
            filename = os.path.basename(question_to_delete['media_path'])
            media_full_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            if os.path.exists(media_full_path):
                try: os.remove(media_full_path); logger.info(f"Associated media file {media_full_path} deleted for question {question_id}.")
                except OSError as oe: logger.error(f"Error deleting media file {media_full_path} for question {question_id}: {oe}", exc_info=True)

        deleted = delete_question(question_id)
        if deleted: flash("سوال با موفقیت حذف شد.", "success")
        else: flash("خطا در حذف سوال از دیتابیس.", "danger")
    except Exception as e:
        logger.error(f"Error deleting question ID {question_id}: {e}", exc_info=True)
        flash(f"خطای پیش‌بینی نشده در حذف سوال: {str(e)}", "danger")
    return redirect(url_for('manage_questions'))

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
        if deleted: flash("نتیجه آزمون با موفقیت حذف شد.", "success")
        else: flash("خطا در حذف نتیجه آزمون از دیتابیس.", "danger")
    except Exception as e:
        logger.error(f"Error deleting test result ID {test_id}: {e}", exc_info=True)
        flash(f"خطای پیش‌بینی نشده در حذف نتیجه آزمون: {str(e)}", "danger")
    return redirect(url_for('view_test_results'))

@app.route('/leaderboard')
@admin_required
def leaderboard():
    top_users_data = get_top_users(limit=100)
    return render_template('leaderboard.html', top_users=top_users_data)

@app.route('/support_messages')
@admin_required
def view_support_messages():
    messages_data = get_all_support_messages()
    for message in messages_data:
        message['timestamp_shamsi'] = _to_shamsi(message.get('timestamp'))
        if message.get('media_path') and not message['media_path'].startswith(('http://', 'https://')):
            message['media_url'] = url_for('static', filename=message['media_path'])
        else:
            message['media_url'] = message.get('media_path')
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
                update_support_message_response(message_id, admin_response_text)
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

    return render_template('respond_to_support.html', message=message)

@app.route('/delete_support_message/<int:message_id>', methods=['POST'])
@admin_required
def delete_support_message_route(message_id):
    try:
        message_to_delete = get_support_message_by_id(message_id)
        if message_to_delete and message_to_delete.get('media_path'):
            if message_to_delete['media_path'].startswith('media/'):
                 filename = os.path.basename(message_to_delete['media_path'])
                 media_full_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                 if os.path.exists(media_full_path):
                    try: os.remove(media_full_path); logger.info(f"Associated media file {media_full_path} deleted for support message {message_id}.")
                    except OSError as oe: logger.error(f"Error deleting media file {media_full_path} for support message {message_id}: {oe}", exc_info=True)

        deleted = delete_support_message(message_id)
        if deleted: flash("پیام پشتیبانی با موفقیت حذف شد.", "success")
        else: flash("خطا در حذف پیام پشتیبانی از دیتابیس.", "danger")
    except Exception as e:
        logger.error(f"Error deleting support message ID {message_id}: {e}", exc_info=True)
        flash(f"خطای پیش‌بینی نشده در حذف پیام پشتیبانی: {str(e)}", "danger")
    return redirect(url_for('view_support_messages'))

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
    duration_str = request.form.get('duration', '30')
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
    if duration_days > 0: flash(f"اشتراک ویژه برای کاربر {user_id} به مدت {duration_days} روز فعال شد.", "success")
    else: flash(f"اشتراک ویژه کاربر {user_id} لغو شد.", "info")
    return redirect(url_for('manage_users'))

@app.route('/api/php/payment-callback', methods=['POST'])
def php_payment_callback():
    auth_header = request.headers.get('Authorization')
    if not auth_header or 'Bearer ' not in auth_header:
        logger.warning("PHP Callback: Missing or invalid Authorization header.")
        return jsonify({"status": "error", "message": "Unauthorized - Missing or invalid auth header"}), 401

    token = auth_header.split('Bearer ')[1]
    if token != Config.PHP_SECRET_KEY:
        logger.warning(f"PHP Callback: Invalid secret key. Received: {token[:10]}...")
        return jsonify({"status": "error", "message": "Forbidden - Invalid secret key"}), 403

    data = request.json
    if not data:
        logger.error("PHP Callback: No JSON data received.")
        return jsonify({"status": "error", "message": "No data received"}), 400

    order_id_from_php = data.get('order_id')
    ref_id_zarinpal = data.get('ref_id')
    status_from_php = data.get('status')
    amount_from_php = data.get('amount')

    logger.info(f"PHP Callback received: order_id={order_id_from_php}, status={status_from_php}, ref_id={ref_id_zarinpal}, amount={amount_from_php}")

    if not order_id_from_php or status_from_php != 'completed' or not ref_id_zarinpal:
        logger.warning(f"PHP Callback: Incomplete or non-completed data received: {data}")
        return jsonify({"status": "error", "message": "Incomplete or non-completed data"}), 400

    payment_record = get_payment_by_authority(order_id_from_php)
    if not payment_record:
        logger.error(f"PHP Callback: Payment record not found for order_id (authority) {order_id_from_php}")
        return jsonify({"status": "error", "message": "Order not found in DB"}), 404

    if payment_record['status'] == 'completed':
        logger.info(f"PHP Callback: Payment for order_id {order_id_from_php} already marked as completed.")
        return jsonify({"status": "already_completed", "message": "Payment already processed"})

    if int(payment_record['amount']) != int(amount_from_php): # Cast to int for comparison
        logger.error(f"PHP Callback: Amount mismatch for order_id {order_id_from_php}. Expected {payment_record['amount']}, got {amount_from_php}.")
        update_payment_status(order_id_from_php, 'amount_mismatch')
        return jsonify({"status": "error", "message": "Amount mismatch"}), 400

    try:
        user_id = payment_record['user_id']
        duration_days = data.get('duration', 30)
        if not isinstance(duration_days, int) or duration_days <=0:
            duration_days = 30
            logger.warning(f"PHP Callback: Invalid or missing duration for order_id {order_id_from_php}. Defaulting to 30 days.")

        update_payment_status(order_id_from_php, 'completed')
        set_user_premium(user_id, duration_days=duration_days)
        send_payment_confirmation(user_id, duration_days, amount_paid=amount_from_php)

        logger.info(f"PHP Callback: Payment processed successfully for user {user_id}, order_id {order_id_from_php}, Zarinpal ref_id {ref_id_zarinpal}")
        return jsonify({"status": "success", "message": "Payment processed and premium activated"})

    except Exception as e:
        logger.error(f"Error processing PHP callback for order_id {order_id_from_php}: {e}", exc_info=True)
        return jsonify({"status": "error", "message": "Internal server error during callback processing"}), 500

print("--- admin_panel.py: File imported and setup complete ---")
