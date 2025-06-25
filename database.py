import mysql.connector
from mysql.connector import errorcode
from config import Config
import os
import datetime
import json
import logging
import threading # Added for Lock

# Setup basic logging
# logging.basicConfig should be called in main.py, not here.
# Assuming main.py configures it. If not, basicConfig here would be a fallback.
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# اطلاعات اتصال به MySQL را از فایل کانفیگ می‌خوانیم
db_config = {
    'host': Config.MYSQL_HOST,
    'user': Config.MYSQL_USER,
    'password': Config.MYSQL_PASSWORD,
    'database': Config.MYSQL_DB,
    'pool_name': 'mysql_pool', # افزودن نام برای پول کانکشن
    'pool_size': 5 # تعداد کانکشن‌ها در پول
}

# استفاده از کانکشن پولینگ برای مدیریت بهتر اتصالات
# متغیر برای نگهداری وضعیت ایجاد پول
_pool_initialized = False
_pool_creation_lock = threading.Lock() # Corrected: Use threading.Lock()

def _init_connection_pool():
    """Initialize the connection pool if not already initialized."""
    global _pool_initialized
    # از قفل برای جلوگیری از ایجاد چندباره پول در محیط چند تردی استفاده می‌کنیم
    with _pool_creation_lock:
        if not _pool_initialized:
            try:
                logging.info("در حال تلاش برای ایجاد/اتصال اولیه به پول کانکشن MySQL...")
                # تلاش برای یک اتصال ساده برای اطمینان از اینکه پول ایجاد می‌شود یا وجود دارد
                # در mysql-connector-python >= 8.0.12، پول با اولین اتصال با pool_name ایجاد می‌شود.
                # اگر از نسخه‌های قدیمی‌تر استفاده می‌کنید، ممکن است نیاز به mysql.connector.pooling.MySQLConnectionPool باشد.

                # ابتدا یک کانکشن تست برای ایجاد پول می‌گیریم (اگر وجود نداشته باشد)
                # این کانکشن باید بسته شود.
                temp_conn_config = db_config.copy()
                # اگر pool_name در کانفیگ اولیه باشد، اتصال اول آن را می‌سازد.
                # mysql.connector.connect(**temp_conn_config) # این خط پول را با نام پیش‌فرض می‌سازد اگر نامی در db_config نباشد
                                                            # یا اگر pool_name در db_config باشد، آن را می‌سازد.

                # برای اطمینان از اینکه پول با تنظیمات ما ساخته شده، یک اتصال آزمایشی با pool_name می‌گیریم
                # و اگر پول وجود نداشت، یک اتصال مستقیم با کل db_config می‌سازیم تا پول ساخته شود.
                try:
                    conn_test = mysql.connector.connect(pool_name=db_config['pool_name'])
                    conn_test.close()
                    logging.info(f"پول کانکشن '{db_config['pool_name']}' با موفقیت یافت یا ایجاد شد.")
                except mysql.connector.errors.PoolError: # اگر پول با این نام وجود نداشت
                    logging.info(f"پول کانکشن '{db_config['pool_name']}' یافت نشد، در حال ایجاد با تنظیمات کامل...")
                    conn_init = mysql.connector.connect(**db_config) # این باید پول را بسازد
                    conn_init.close()
                    logging.info(f"پول کانکشن '{db_config['pool_name']}' با تنظیمات کامل ایجاد شد.")

                _pool_initialized = True
            except mysql.connector.Error as err:
                logging.error(f"خطا در ایجاد اولیه پول کانکشن MySQL: {err}", exc_info=True)
                # در صورت عدم موفقیت، _pool_initialized همچنان False باقی می‌ماند
                # و در get_db_connection تلاش برای اتصال مستقیم صورت می‌گیرد.
                return False # نشان دهنده عدم موفقیت در ایجاد پول
            return True # نشان دهنده موفقیت در ایجاد پول
    return True # اگر پول قبلا ساخته شده

def get_db_connection():
    """ یک اتصال از پول کانکشن MySQL دریافت می‌کند یا یک اتصال مستقیم برقرار می‌کند """
    global _pool_initialized

    if not _pool_initialized:
        if not _init_connection_pool(): # اگر ایجاد پول ناموفق بود
            logging.warning("پول کانکشن ایجاد نشد یا در دسترس نیست. تلاش برای اتصال مستقیم...")
            # Fallback to direct connection if pool initialization failed
            try:
                direct_config = db_config.copy()
                direct_config.pop('pool_name', None)
                direct_config.pop('pool_size', None)
                conn = mysql.connector.connect(**direct_config)
                logging.info("اتصال مستقیم به دیتابیس (fallback) با موفقیت برقرار شد.")
                return conn
            except mysql.connector.Error as direct_err:
                logging.error(f"خطا در اتصال مستقیم به دیتابیس (fallback): {direct_err}", exc_info=True)
                return None

    # تلاش برای گرفتن اتصال از پول موجود
    try:
        conn = mysql.connector.connect(pool_name=db_config['pool_name'])
        # logging.debug(f"اتصال از پول '{db_config['pool_name']}' با موفقیت دریافت شد.")
        return conn
    except mysql.connector.Error as err:
        logging.error(f"خطا در دریافت اتصال از پول '{db_config['pool_name']}': {err}", exc_info=True)
        # اگر خطای دیگری بود، به عنوان fallback اتصال مستقیم را امتحان می‌کنیم
        # این بخش ممکن است تکراری با منطق بالاتر باشد، اما برای اطمینان در اینجا نیز قرار داده شده
        logging.warning(f"خطای '{err}' هنگام دریافت اتصال از پول. تلاش برای اتصال مستقیم (fallback)...")
        try:
            direct_config = db_config.copy()
            direct_config.pop('pool_name', None)
            direct_config.pop('pool_size', None)
            conn_fallback = mysql.connector.connect(**direct_config)
            logging.info("اتصال مستقیم به دیتابیس (fallback در get_db_connection) با موفقیت برقرار شد.")
            return conn_fallback
        except mysql.connector.Error as direct_err_fallback:
            logging.error(f"خطا در اتصال مستقیم به دیتابیس (fallback نهایی در get_db_connection): {direct_err_fallback}", exc_info=True)
            return None
    except Exception as e: # گرفتن خطاهای دیگر (بسیار غیرمحتمل)
        logging.error(f"خطای بسیار پیش‌بینی نشده در get_db_connection: {e}", exc_info=True)
        return None


def create_tables():
    """ جداول را در دیتابیس MySQL ایجاد می‌کند """
    # دستورات ساخت جدول برای MySQL (تغییرات: AUTO_INCREMENT، DATETIME، ENGINE)
    # تمام ستون‌های TIMESTAMP به DATETIME تغییر کردند
    # نوع ستون‌های username، first_name، last_name در جدول users و current_quiz در quiz_states
    # و level و skill در questions و test_results و quiz_states از TEXT به VARCHAR(255) تغییر کرد
    # تا محدودیت منطقی برای طول آن‌ها وجود داشته باشد و کمی بهینه‌تر باشد.
    # همچنین media_path و question_type و test_type نیز به VARCHAR(255) یا VARCHAR(50) تغییر کردند.
    tables = {}
    tables['users'] = ('''
        CREATE TABLE IF NOT EXISTS `users` (
            `user_id` BIGINT UNSIGNED PRIMARY KEY,
            `username` VARCHAR(255),
            `first_name` VARCHAR(255),
            `last_name` VARCHAR(255),
            `join_date` DATETIME DEFAULT CURRENT_TIMESTAMP,
            `premium_expires_at` DATETIME NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    ''')
    tables['questions'] = ('''
        CREATE TABLE IF NOT EXISTS `questions` (
            `id` INT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
            `question_text` TEXT NOT NULL,
            `options` JSON NOT NULL,
            `correct_answer` INT UNSIGNED NOT NULL,
            `level` VARCHAR(50) NOT NULL,
            `skill` VARCHAR(50) NOT NULL,
            `media_path` VARCHAR(255),
            `media_type` VARCHAR(50),
            `question_type` VARCHAR(50)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    ''')
    tables['test_results'] = ('''
        CREATE TABLE IF NOT EXISTS `test_results` (
            `test_id` INT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
            `user_id` BIGINT UNSIGNED NOT NULL,
            `score` INT NOT NULL,
            `level` VARCHAR(50) NOT NULL,
            `test_type` VARCHAR(50) NOT NULL,
            `test_date` DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`) ON DELETE CASCADE ON UPDATE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    ''')
    tables['support_messages'] = ('''
        CREATE TABLE IF NOT EXISTS `support_messages` (
            `id` INT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
            `user_id` BIGINT UNSIGNED NOT NULL,
            `message_text` TEXT NOT NULL,
            `timestamp` DATETIME DEFAULT CURRENT_TIMESTAMP,
            `admin_response_text` TEXT,
            `responded_at` DATETIME,
            `status` VARCHAR(50) DEFAULT 'new',
            `media_path` VARCHAR(255),
            FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`) ON DELETE CASCADE ON UPDATE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    ''')
    tables['quiz_states'] = ('''
        CREATE TABLE IF NOT EXISTS `quiz_states` (
            `user_id` BIGINT UNSIGNED PRIMARY KEY,
            `current_quiz` VARCHAR(255),
            `questions` JSON NOT NULL,
            `current_question_index` INT NOT NULL,
            `score` INT NOT NULL,
            `start_time` VARCHAR(255) NOT NULL, # Storing as string, converted in app
            `level` VARCHAR(50),
            `test_type` VARCHAR(50),
            `deadline` VARCHAR(255) NOT NULL, # Storing as string, converted in app
            `answer_details` JSON
        ) ENGINE=InnoDB
    ''')
    tables['payments'] = ('''
        CREATE TABLE IF NOT EXISTS `payments` (
            `id` INT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
            `user_id` BIGINT UNSIGNED NOT NULL,
            `authority` VARCHAR(255) NOT NULL,
            `amount` INT NOT NULL,
            `status` VARCHAR(50) DEFAULT 'pending',
            `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`) ON DELETE CASCADE ON UPDATE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    ''')
    
    conn = get_db_connection()
    if not conn:
        logging.error("عدم امکان اتصال به دیتابیس برای ساخت جداول.")
        return

    try:
        with conn.cursor() as cursor:
            for table_name, table_description in tables.items():
                logging.info(f"در حال ساخت جدول {table_name}... ")
                cursor.execute(table_description)
                logging.info(f"جدول {table_name} با موفقیت ساخته یا از قبل موجود بود.")
    except mysql.connector.Error as err:
        logging.error(f"خطا در ساخت جداول: {err}")
    finally:
        if conn and conn.is_connected(): # بستن اتصال اگر هنوز باز است (در صورت عدم استفاده از پولینگ یا خطای خارج از with)
            conn.close()


def _parse_json_fields(row, fields_to_parse):
    """Helper function to parse JSON fields in a row if they exist and are strings."""
    if row:
        for field in fields_to_parse:
            if field in row and isinstance(row[field], str):
                try:
                    row[field] = json.loads(row[field])
                except json.JSONDecodeError:
                    logging.warning(f"خطا در پارس کردن JSON برای فیلد {field} در ردیف: {row}")
                    # Keep original string or set to None/empty list as appropriate
                    # For now, keeping the original string if parsing fails
    return row

def _execute_query(sql, params=None, fetch_one=False, fetch_all=False, is_ddl=False, dictionary_cursor=True):
    """
    یک تابع کمکی برای اجرای کوئری‌ها، مدیریت اتصال و مکان‌نما.
    is_ddl: True اگر کوئری از نوع DDL باشد (مانند CREATE, ALTER, DROP) و نیاز به commit ندارد مگر اینکه بخشی از تراکنش بزرگتر باشد.
    dictionary_cursor: True اگر می‌خواهید نتایج به صورت دیکشنری باشند.
    """
    conn = None
    try:
        conn = get_db_connection()
        if not conn:
            logging.error("عدم امکان اتصال به دیتابیس.")
            return None # یا raise Exception("Failed to connect to database")

        # برای cursor با dictionary=True، بافر شدن به صورت پیش‌فرض فعال است (buffered=True)
        # اگر نیاز به unbuffered cursor دارید (مثلاً برای نتایج بسیار بزرگ)، باید buffered=False تنظیم شود.
        cursor_type = conn.cursor(dictionary=dictionary_cursor) if dictionary_cursor else conn.cursor()

        with cursor_type as cursor:
            cursor.execute(sql, params)
            if is_ddl or (not fetch_one and not fetch_all): # INSERT, UPDATE, DELETE
                conn.commit()
                return cursor.lastrowid if cursor.lastrowid else True # برای INSERT می‌تواند ID ردیف جدید را برگرداند

            if fetch_one:
                return cursor.fetchone()
            if fetch_all:
                return cursor.fetchall()
            return True # برای کوئری‌هایی که نتیجه‌ای برنمی‌گردانند اما DDL هم نیستند (اگر چنین حالتی وجود داشته باشد)

    except mysql.connector.Error as err:
        logging.error(f"خطای دیتابیس در اجرای کوئری '{sql[:100]}...': {err}")
        # می‌توان در اینجا conn.rollback() را نیز فراخوانی کرد اگر تراکنشی در جریان بوده.
        # اما با auto-commit پیش‌فرض، هر execute یک تراکنش است مگر اینکه صریحاً start_transaction() فراخوانی شود.
        return None # یا False یا raise err
    except Exception as e:
        logging.error(f"خطای پیش‌بینی نشده در اجرای کوئری '{sql[:100]}...': {e}")
        return None
    finally:
        if conn and conn.is_connected():
            conn.close()


def add_user(user_id, username, first_name, last_name):
    sql = "INSERT IGNORE INTO users (user_id, username, first_name, last_name) VALUES (%s, %s, %s, %s)"
    return _execute_query(sql, (user_id, username, first_name, last_name))

def get_user(user_id):
    sql = "SELECT * FROM users WHERE user_id = %s"
    return _execute_query(sql, (user_id,), fetch_one=True)

def add_question(question_text, options, correct_answer, level, skill, media_path=None, media_type=None, question_type='multiple_choice'):
    sql = "INSERT INTO questions (question_text, options, correct_answer, level, skill, media_path, media_type, question_type) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"
    options_json = json.dumps(options)
    return _execute_query(sql, (question_text, options_json, correct_answer, level, skill, media_path, media_type, question_type))

def get_questions():
    sql = "SELECT * FROM questions ORDER BY id DESC"
    rows = _execute_query(sql, fetch_all=True)
    if rows:
        return [_parse_json_fields(row, ['options']) for row in rows]
    return []

def get_comprehensive_questions(count=Config.MAX_QUESTIONS):
    sql = "SELECT * FROM questions WHERE question_type = 'جامع' ORDER BY id ASC LIMIT %s"
    rows = _execute_query(sql, (count,), fetch_all=True)
    if rows:
        return [_parse_json_fields(row, ['options']) for row in rows]
    return []
            
def get_questions_by_skill_and_level(skill, level, count=Config.MAX_QUESTIONS):
    sql = "SELECT * FROM questions WHERE skill = %s AND level = %s AND question_type = 'مهارتی' ORDER BY RAND() LIMIT %s"
    rows = _execute_query(sql, (skill, level, count), fetch_all=True)
    if rows:
        return [_parse_json_fields(row, ['options']) for row in rows]
    return []

def get_question_by_id(question_id):
    sql = "SELECT * FROM questions WHERE id = %s"
    row = _execute_query(sql, (question_id,), fetch_one=True)
    return _parse_json_fields(row, ['options'])

def update_question(question_id, question_text, options, correct_answer, level, skill, question_type, media_path=None, media_type=None):
    sql = "UPDATE questions SET question_text = %s, options = %s, correct_answer = %s, level = %s, skill = %s, question_type = %s, media_path = %s, media_type = %s WHERE id = %s"
    options_json = json.dumps(options)
    return _execute_query(sql, (question_text, options_json, correct_answer, level, skill, question_type, media_path, media_type, question_id))

def delete_question(question_id):
    sql = "DELETE FROM questions WHERE id = %s"
    return _execute_query(sql, (question_id,))

def save_test_result(user_id, score, level, test_type='جامع'):
    sql = "INSERT INTO test_results (user_id, score, level, test_type) VALUES (%s, %s, %s, %s)"
    return _execute_query(sql, (user_id, score, level, test_type))

def get_all_test_results():
    sql = '''
        SELECT tr.test_id, tr.user_id, u.username, u.first_name, u.last_name,
               tr.score, tr.level, tr.test_type, tr.test_date
        FROM test_results tr
        JOIN users u ON tr.user_id = u.user_id
        ORDER BY tr.test_date DESC
    '''
    results = _execute_query(sql, fetch_all=True)
    if results:
        for r in results: # جایگزین کردن مقادیر None
            r['username'] = r.get('username') or 'N/A'
            r['first_name'] = r.get('first_name') or 'N/A'
            r['last_name'] = r.get('last_name') or ''
        return results
    return []

def delete_test_result(test_id):
    sql = "DELETE FROM test_results WHERE test_id = %s"
    return _execute_query(sql, (test_id,))

def get_user_stats(user_id):
    stats = {'num_tests': 0, 'total_score': 0, 'highest_score': 0, 'average_score': 0}

    sql_count = "SELECT COUNT(*) as count FROM test_results WHERE user_id = %s"
    count_result = _execute_query(sql_count, (user_id,), fetch_one=True, dictionary_cursor=True) # اطمینان از دیکشنری بودن
    if count_result and count_result['count'] is not None:
        stats['num_tests'] = count_result['count']

    if stats['num_tests'] > 0:
        sql_sum_max = "SELECT SUM(score) as total, MAX(score) as highest FROM test_results WHERE user_id = %s"
        sum_max_result = _execute_query(sql_sum_max, (user_id,), fetch_one=True, dictionary_cursor=True)
        if sum_max_result:
            stats['total_score'] = sum_max_result.get('total') or 0
            stats['highest_score'] = sum_max_result.get('highest') or 0

        if stats['num_tests'] > 0 : # بررسی مجدد برای جلوگیری از تقسیم بر صفر اگر کوئری دوم نتیجه ندهد
            stats['average_score'] = round(stats['total_score'] / stats['num_tests'], 2)
        else: # این حالت نباید رخ دهد اگر num_tests > 0 باشد، اما برای اطمینان
            stats['average_score'] = 0

    return stats

def get_last_test_time(user_id, test_type='جامع'):
    sql = "SELECT MAX(test_date) as max_date FROM test_results WHERE user_id = %s AND test_type = %s"
    result = _execute_query(sql, (user_id, test_type), fetch_one=True, dictionary_cursor=True)
    # در MySQL Connector، آبجکت datetime مستقیماً برگردانده می‌شود
    return result['max_date'] if result and result['max_date'] else None

def get_top_users(limit=10):
    sql = '''
        SELECT u.user_id, u.username, u.first_name, u.last_name, SUM(tr.score) as total_score
        FROM users u
        JOIN test_results tr ON u.user_id = tr.user_id
        GROUP BY u.user_id
        ORDER BY total_score DESC
        LIMIT %s
    '''
    return _execute_query(sql, (limit,), fetch_all=True)

def save_support_message(user_id, message_text, media_path=None):
    sql = "INSERT INTO support_messages (user_id, message_text, media_path) VALUES (%s, %s, %s)"
    return _execute_query(sql, (user_id, message_text, media_path))

def get_all_support_messages():
    sql = '''
        SELECT sm.id, sm.user_id, u.username, u.first_name, u.last_name,
               sm.message_text, sm.timestamp, sm.admin_response_text,
               sm.responded_at, sm.status, sm.media_path
        FROM support_messages sm
        LEFT JOIN users u ON sm.user_id = u.user_id
        ORDER BY sm.timestamp DESC
    '''
    return _execute_query(sql, fetch_all=True)

def get_support_message_by_id(message_id):
    sql = '''
        SELECT sm.id, sm.user_id, u.username, u.first_name, u.last_name,
               sm.message_text, sm.timestamp, sm.admin_response_text,
               sm.responded_at, sm.status, sm.media_path
        FROM support_messages sm
        LEFT JOIN users u ON sm.user_id = u.user_id
        WHERE sm.id = %s
    '''
    return _execute_query(sql, (message_id,), fetch_one=True)

def update_support_message_response(message_id, admin_response_text):
    sql = "UPDATE support_messages SET admin_response_text = %s, responded_at = %s, status = 'responded' WHERE id = %s"
    responded_at = datetime.datetime.now()
    return _execute_query(sql, (admin_response_text, responded_at, message_id))

def update_support_message_status(message_id, status):
    sql = "UPDATE support_messages SET status = %s WHERE id = %s"
    return _execute_query(sql, (status, message_id))

def save_quiz_state(user_id, state_data):
    sql = """
        INSERT INTO quiz_states
            (user_id, current_quiz, questions, current_question_index, score,
             start_time, level, test_type, deadline, answer_details)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            current_quiz=VALUES(current_quiz), questions=VALUES(questions),
            current_question_index=VALUES(current_question_index), score=VALUES(score),
            start_time=VALUES(start_time), level=VALUES(level),
            test_type=VALUES(test_type), deadline=VALUES(deadline),
            answer_details=VALUES(answer_details)
    """
    questions_json = json.dumps(state_data.get('questions', []))
    answer_details_json = json.dumps(state_data.get('answer_details', []))

    # اطمینان از اینکه start_time و deadline آبجکت datetime هستند قبل از فرمت کردن
    start_time_obj = state_data.get('start_time')
    deadline_obj = state_data.get('deadline')

    start_time_str = start_time_obj.strftime("%Y-%m-%d %H:%M:%S") if isinstance(start_time_obj, datetime.datetime) else str(start_time_obj)
    deadline_str = deadline_obj.strftime("%Y-%m-%d %H:%M:%S") if isinstance(deadline_obj, datetime.datetime) else str(deadline_obj)

    return _execute_query(sql, (
        user_id, state_data.get('current_quiz'), questions_json,
        state_data.get('current_question_index'), state_data.get('score'),
        start_time_str, state_data.get('level'), state_data.get('test_type'),
        deadline_str, answer_details_json
    ))

def get_quiz_state(user_id):
    sql = "SELECT * FROM quiz_states WHERE user_id = %s"
    row = _execute_query(sql, (user_id,), fetch_one=True)
    if row:
        try:
            row['questions'] = json.loads(row['questions']) if isinstance(row.get('questions'), str) else row.get('questions', [])
            row['answer_details'] = json.loads(row['answer_details']) if isinstance(row.get('answer_details'), str) else row.get('answer_details', [])

            if isinstance(row.get('start_time'), str):
                 row['start_time'] = datetime.datetime.strptime(row['start_time'], "%Y-%m-%d %H:%M:%S")
            if isinstance(row.get('deadline'), str):
                row['deadline'] = datetime.datetime.strptime(row['deadline'], "%Y-%m-%d %H:%M:%S")
        except (json.JSONDecodeError, TypeError, ValueError) as e:
            logging.error(f"خطا در پارس کردن اطلاعات quiz_state برای کاربر {user_id}: {e}")
            # ممکن است بخواهید در اینجا None برگردانید یا ردیف را با داده‌های ناقص برگردانید
            return None # یا row با مقادیر پیش‌فرض برای فیلدهای مشکل‌دار
        return row
    return None

def delete_quiz_state(user_id):
    sql = "DELETE FROM quiz_states WHERE user_id = %s"
    return _execute_query(sql, (user_id,))

def delete_support_message(message_id):
    sql = "DELETE FROM support_messages WHERE id = %s"
    return _execute_query(sql, (message_id,))

def set_user_premium(user_id, duration_days=30):
    expiry_date_val = None
    if duration_days and duration_days > 0:
        expiry_date_val = datetime.datetime.now() + datetime.timedelta(days=duration_days)

    sql = "UPDATE users SET premium_expires_at = %s WHERE user_id = %s"
    return _execute_query(sql, (expiry_date_val, user_id))

def is_user_premium(user_id):
    sql = "SELECT premium_expires_at FROM users WHERE user_id = %s"
    result = _execute_query(sql, (user_id,), fetch_one=True)
    if result and result['premium_expires_at']:
        # premium_expires_at باید از نوع datetime.datetime باشد
        expiry_date = result['premium_expires_at']
        if isinstance(expiry_date, datetime.datetime):
            return datetime.datetime.now() < expiry_date
        else: # اگر به دلایلی نوع داده متفاوت بود (مثلاً رشته تاریخ)
            try:
                # تلاش برای تبدیل اگر رشته باشد، هرچند نباید اینطور باشد اگر دیتابیس درست تنظیم شده
                expiry_date_obj = datetime.datetime.fromisoformat(str(expiry_date))
                return datetime.datetime.now() < expiry_date_obj
            except ValueError:
                logging.error(f"فرمت premium_expires_at برای کاربر {user_id} نامعتبر است: {expiry_date}")
                return False
    return False

def get_user_premium_expiry(user_id):
    sql = "SELECT premium_expires_at FROM users WHERE user_id = %s"
    result = _execute_query(sql, (user_id,), fetch_one=True)
    return result['premium_expires_at'] if result else None

def get_all_users():
    sql = "SELECT user_id, username, first_name, last_name, join_date, premium_expires_at FROM users ORDER BY join_date DESC"
    return _execute_query(sql, fetch_all=True)
            
def get_total_user_count():
    sql = "SELECT COUNT(*) as count FROM users"
    result = _execute_query(sql, fetch_one=True, dictionary_cursor=True)
    return result['count'] if result and result['count'] is not None else 0

def get_total_question_count():
    sql = "SELECT COUNT(*) as count FROM questions"
    result = _execute_query(sql, fetch_one=True, dictionary_cursor=True)
    return result['count'] if result and result['count'] is not None else 0

def get_recent_quiz_count(hours=24):
    sql = "SELECT COUNT(*) as count FROM test_results WHERE test_date >= %s"
    time_threshold = datetime.datetime.now() - datetime.timedelta(hours=hours)
    result = _execute_query(sql, (time_threshold,), fetch_one=True, dictionary_cursor=True)
    return result['count'] if result and result['count'] is not None else 0

def create_payment_record(user_id, authority, amount):
    sql = "INSERT INTO payments (user_id, authority, amount) VALUES (%s, %s, %s)"
    return _execute_query(sql, (user_id, authority, amount))

def get_payment_by_authority(authority):
    sql = "SELECT * FROM payments WHERE authority = %s"
    return _execute_query(sql, (authority,), fetch_one=True)
            
def update_payment_status(authority, status):
    sql = "UPDATE payments SET status = %s WHERE authority = %s"
    return _execute_query(sql, (status, authority))
