import mysql.connector
from mysql.connector import errorcode
from config import Config
import os
import datetime
import json

# اطلاعات اتصال به MySQL را از فایل کانفیگ می‌خوانیم
db_config = {
    'host': Config.MYSQL_HOST,
    'user': Config.MYSQL_USER,
    'password': Config.MYSQL_PASSWORD,
    'database': Config.MYSQL_DB
}

def get_db_connection():
    """ یک اتصال جدید به دیتابیس MySQL برقرار می‌کند """
    try:
        conn = mysql.connector.connect(**db_config)
        return conn
    except mysql.connector.Error as err:
        if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
            print("خطا: نام کاربری یا رمز عبور دیتابیس اشتباه است.")
        elif err.errno == errorcode.ER_BAD_DB_ERROR:
            print("خطا: دیتابیس مورد نظر وجود ندارد.")
        else:
            print(f"خطا در اتصال به دیتابیس: {err}")
        return None


def create_tables():
    """ جداول را در دیتابیس MySQL ایجاد می‌کند """
    conn = get_db_connection()
    if not conn:
        return
    
    cursor = conn.cursor()
    
    # دستورات ساخت جدول برای MySQL (تغییرات: AUTO_INCREMENT، DATETIME، ENGINE)
    # تمام ستون‌های TIMESTAMP به DATETIME تغییر کردند
    tables = {}
    tables['users'] = ('''
        CREATE TABLE IF NOT EXISTS `users` (
            `user_id` BIGINT PRIMARY KEY,
            `username` TEXT,
            `first_name` TEXT,
            `last_name` TEXT,
            `join_date` DATETIME DEFAULT CURRENT_TIMESTAMP,
            `premium_expires_at` DATETIME NULL
        ) ENGINE=InnoDB
    ''')
    tables['questions'] = ('''
        CREATE TABLE IF NOT EXISTS `questions` (
            `id` INT PRIMARY KEY AUTO_INCREMENT,
            `question_text` TEXT NOT NULL,
            `options` JSON NOT NULL,
            `correct_answer` INT NOT NULL,
            `level` VARCHAR(255) NOT NULL,
            `skill` VARCHAR(255) NOT NULL,
            `media_path` VARCHAR(255),
            `media_type` VARCHAR(50),
            `question_type` VARCHAR(255)
        ) ENGINE=InnoDB
    ''')
    tables['test_results'] = ('''
        CREATE TABLE IF NOT EXISTS `test_results` (
            `test_id` INT PRIMARY KEY AUTO_INCREMENT,
            `user_id` BIGINT NOT NULL,
            `score` INT NOT NULL,
            `level` VARCHAR(255) NOT NULL,
            `test_type` VARCHAR(255) NOT NULL,
            `test_date` DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`)
        ) ENGINE=InnoDB
    ''')
    tables['support_messages'] = ('''
        CREATE TABLE IF NOT EXISTS `support_messages` (
            `id` INT PRIMARY KEY AUTO_INCREMENT,
            `user_id` BIGINT NOT NULL,
            `message_text` TEXT NOT NULL,
            `timestamp` DATETIME DEFAULT CURRENT_TIMESTAMP,
            `admin_response_text` TEXT,
            `responded_at` DATETIME,
            `status` VARCHAR(50) DEFAULT 'new',
            `media_path` VARCHAR(255),
            FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`)
        ) ENGINE=InnoDB
    ''')
    tables['quiz_states'] = ('''
        CREATE TABLE IF NOT EXISTS `quiz_states` (
            `user_id` BIGINT PRIMARY KEY,
            `current_quiz` TEXT,
            `questions` JSON NOT NULL,
            `current_question_index` INT NOT NULL,
            `score` INT NOT NULL,
            `start_time` TEXT NOT NULL,
            `level` TEXT,
            `test_type` TEXT,
            `deadline` TEXT NOT NULL,
            `answer_details` JSON
        ) ENGINE=InnoDB
    ''')
    tables['payments'] = ('''
        CREATE TABLE IF NOT EXISTS `payments` (
            `id` INT PRIMARY KEY AUTO_INCREMENT,
            `user_id` BIGINT NOT NULL,
            `authority` VARCHAR(255) NOT NULL,
            `amount` INT NOT NULL,
            `status` VARCHAR(50) DEFAULT 'pending',
            `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`)
        ) ENGINE=InnoDB
    ''')
    
    try:
        for table_name in tables:
            table_description = tables[table_name]
            print(f"در حال ساخت جدول {table_name}... ", end='')
            cursor.execute(table_description)
            print("OK")
    except mysql.connector.Error as err:
        print(f"خطا در ساخت جداول: {err}")
    finally:
        cursor.close()
        conn.close()


def add_user(user_id, username, first_name, last_name):
    # دستور INSERT IGNORE برای MySQL معادل INSERT OR IGNORE در SQLite است
    sql = "INSERT IGNORE INTO users (user_id, username, first_name, last_name) VALUES (%s, %s, %s, %s)"
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, (user_id, username, first_name, last_name))
            conn.commit()


def get_user(user_id):
    sql = "SELECT * FROM users WHERE user_id = %s"
    with get_db_connection() as conn:
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute(sql, (user_id, ))
            return cursor.fetchone()

def add_question(question_text, options, correct_answer, level, skill, media_path=None, media_type=None, question_type='multiple_choice'):
    sql = "INSERT INTO questions (question_text, options, correct_answer, level, skill, media_path, media_type, question_type) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"
    options_json = json.dumps(options)
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, (question_text, options_json, correct_answer, level, skill, media_path, media_type, question_type))
            conn.commit()


def get_questions():
    sql = "SELECT * FROM questions ORDER BY id DESC"
    with get_db_connection() as conn:
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute(sql)
            return cursor.fetchall()

def get_comprehensive_questions(count=Config.MAX_QUESTIONS):
    sql = "SELECT * FROM questions WHERE question_type = 'جامع' ORDER BY id ASC LIMIT %s"
    with get_db_connection() as conn:
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute(sql, (count,))
            return cursor.fetchall()
            
def get_questions_by_skill_and_level(skill, level, count=Config.MAX_QUESTIONS):
    sql = "SELECT * FROM questions WHERE skill = %s AND level = %s AND question_type = 'مهارتی' ORDER BY RAND() LIMIT %s"
    with get_db_connection() as conn:
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute(sql, (skill, level, count))
            return cursor.fetchall()


def get_question_by_id(question_id):
    sql = "SELECT * FROM questions WHERE id = %s"
    with get_db_connection() as conn:
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute(sql, (question_id,))
            return cursor.fetchone()


def update_question(question_id, question_text, options, correct_answer, level, skill, question_type, media_path=None, media_type=None):
    sql = "UPDATE questions SET question_text = %s, options = %s, correct_answer = %s, level = %s, skill = %s, question_type = %s, media_path = %s, media_type = %s WHERE id = %s"
    options_json = json.dumps(options)
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, (question_text, options_json, correct_answer, level, skill, question_type, media_path, media_type, question_id))
            conn.commit()


def delete_question(question_id):
    sql = "DELETE FROM questions WHERE id = %s"
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, (question_id,))
            conn.commit()


def save_test_result(user_id, score, level, test_type='جامع'):
    sql = "INSERT INTO test_results (user_id, score, level, test_type) VALUES (%s, %s, %s, %s)"
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, (user_id, score, level, test_type))
            conn.commit()


def get_all_test_results():
    sql = '''
        SELECT tr.test_id, tr.user_id, u.username, u.first_name, u.last_name,
               tr.score, tr.level, tr.test_type, tr.test_date
        FROM test_results tr
        JOIN users u ON tr.user_id = u.user_id
        ORDER BY tr.test_date DESC
    '''
    with get_db_connection() as conn:
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute(sql)
            results = cursor.fetchall()
            for r in results: # جایگزین کردن مقادیر None
                r['username'] = r.get('username') or 'N/A'
                r['first_name'] = r.get('first_name') or 'N/A'
                r['last_name'] = r.get('last_name') or ''
            return results

def delete_test_result(test_id):
    sql = "DELETE FROM test_results WHERE test_id = %s"
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, (test_id,))
            conn.commit()

def get_user_stats(user_id):
    # این تابع نیاز به چند کوئری جداگانه دارد
    stats = {}
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM test_results WHERE user_id = %s", (user_id,))
            stats['num_tests'] = cursor.fetchone()[0]
            cursor.execute("SELECT SUM(score) FROM test_results WHERE user_id = %s", (user_id,))
            stats['total_score'] = cursor.fetchone()[0] or 0
            cursor.execute("SELECT MAX(score) FROM test_results WHERE user_id = %s", (user_id,))
            stats['highest_score'] = cursor.fetchone()[0] or 0
            stats['average_score'] = (stats['total_score'] / stats['num_tests']) if stats['num_tests'] > 0 else 0
            stats['average_score'] = round(stats['average_score'], 2)
    return stats


def get_last_test_time(user_id, test_type='جامع'):
    sql = "SELECT MAX(test_date) FROM test_results WHERE user_id = %s AND test_type = %s"
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, (user_id, test_type))
            result = cursor.fetchone()[0]
            # در MySQL Connector، آبجکت datetime مستقیماً برگردانده می‌شود
            return result 

def get_top_users(limit=10):
    sql = '''
        SELECT u.user_id, u.username, u.first_name, u.last_name, SUM(tr.score) as total_score
        FROM users u
        JOIN test_results tr ON u.user_id = tr.user_id
        GROUP BY u.user_id
        ORDER BY total_score DESC
        LIMIT %s
    '''
    with get_db_connection() as conn:
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute(sql, (limit,))
            return cursor.fetchall()

def save_support_message(user_id, message_text, media_path=None):
    sql = "INSERT INTO support_messages (user_id, message_text, media_path) VALUES (%s, %s, %s)"
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, (user_id, message_text, media_path))
            conn.commit()

def get_all_support_messages():
    sql = '''
        SELECT sm.id, sm.user_id, u.username, u.first_name, u.last_name,
               sm.message_text, sm.timestamp, sm.admin_response_text,
               sm.responded_at, sm.status, sm.media_path
        FROM support_messages sm
        LEFT JOIN users u ON sm.user_id = u.user_id
        ORDER BY sm.timestamp DESC
    '''
    with get_db_connection() as conn:
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute(sql)
            return cursor.fetchall()

def get_support_message_by_id(message_id):
    sql = '''
        SELECT sm.id, sm.user_id, u.username, u.first_name, u.last_name,
               sm.message_text, sm.timestamp, sm.admin_response_text,
               sm.responded_at, sm.status, sm.media_path
        FROM support_messages sm
        LEFT JOIN users u ON sm.user_id = u.user_id
        WHERE sm.id = %s
    '''
    with get_db_connection() as conn:
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute(sql, (message_id,))
            return cursor.fetchone()

def update_support_message_response(message_id, admin_response_text):
    sql = "UPDATE support_messages SET admin_response_text = %s, responded_at = %s, status = 'responded' WHERE id = %s"
    responded_at = datetime.datetime.now()
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, (admin_response_text, responded_at, message_id))
            conn.commit()

def update_support_message_status(message_id, status):
    sql = "UPDATE support_messages SET status = %s WHERE id = %s"
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, (status, message_id))
            conn.commit()

def save_quiz_state(user_id, state_data):
    sql = "INSERT INTO quiz_states (user_id, current_quiz, questions, current_question_index, score, start_time, level, test_type, deadline, answer_details) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) ON DUPLICATE KEY UPDATE current_quiz=VALUES(current_quiz), questions=VALUES(questions), current_question_index=VALUES(current_question_index), score=VALUES(score), start_time=VALUES(start_time), level=VALUES(level), test_type=VALUES(test_type), deadline=VALUES(deadline), answer_details=VALUES(answer_details)"
    questions_json = json.dumps(state_data.get('questions', []))
    answer_details_json = json.dumps(state_data.get('answer_details', []))
    start_time_str = state_data['start_time'].strftime("%Y-%m-%d %H:%M:%S")
    deadline_str = state_data['deadline'].strftime("%Y-%m-%d %H:%M:%S")
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, (user_id, state_data.get('current_quiz'), questions_json, state_data.get('current_question_index'), state_data.get('score'), start_time_str, state_data.get('level'), state_data.get('test_type'), deadline_str, answer_details_json))
            conn.commit()

def get_quiz_state(user_id):
    sql = "SELECT * FROM quiz_states WHERE user_id = %s"
    with get_db_connection() as conn:
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute(sql, (user_id,))
            row = cursor.fetchone()
            if row:
                row['start_time'] = datetime.datetime.strptime(row['start_time'], "%Y-%m-%d %H:%M:%S")
                row['deadline'] = datetime.datetime.strptime(row['deadline'], "%Y-%m-%d %H:%M:%S")
                return row
            return None


def delete_quiz_state(user_id):
    sql = "DELETE FROM quiz_states WHERE user_id = %s"
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, (user_id,))
            conn.commit()

def delete_support_message(message_id):
    sql = "DELETE FROM support_messages WHERE id = %s"
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, (message_id,))
            conn.commit()

def set_user_premium(user_id, duration_days=30):
    if duration_days and duration_days > 0:
        expiry_date = datetime.datetime.now() + datetime.timedelta(days=duration_days)
        sql = "UPDATE users SET premium_expires_at = %s WHERE user_id = %s"
        params = (expiry_date, user_id)
    else:
        sql = "UPDATE users SET premium_expires_at = NULL WHERE user_id = %s"
        params = (user_id,)
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, params)
            conn.commit()

def is_user_premium(user_id):
    sql = "SELECT premium_expires_at FROM users WHERE user_id = %s"
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, (user_id,))
            result = cursor.fetchone()
            if result and result[0]:
                expiry_date = result[0]
                return datetime.datetime.now() < expiry_date
            return False

def get_user_premium_expiry(user_id):
    sql = "SELECT premium_expires_at FROM users WHERE user_id = %s"
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, (user_id,))
            result = cursor.fetchone()
            return result[0] if result else None

def get_all_users():
    sql = "SELECT user_id, username, first_name, last_name, join_date, premium_expires_at FROM users ORDER BY join_date DESC"
    with get_db_connection() as conn:
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute(sql)
            return cursor.fetchall()
            
def get_total_user_count():
    sql = "SELECT COUNT(*) FROM users"
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql)
            return cursor.fetchone()[0]

def get_total_question_count():
    sql = "SELECT COUNT(*) FROM questions"
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql)
            return cursor.fetchone()[0]

def get_recent_quiz_count(hours=24):
    sql = "SELECT COUNT(*) FROM test_results WHERE test_date >= %s"
    time_threshold = datetime.datetime.now() - datetime.timedelta(hours=hours)
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, (time_threshold,))
            return cursor.fetchone()[0]

def create_payment_record(user_id, authority, amount):
    sql = "INSERT INTO payments (user_id, authority, amount) VALUES (%s, %s, %s)"
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, (user_id, authority, amount))
            conn.commit()

def get_payment_by_authority(authority):
    sql = "SELECT * FROM payments WHERE authority = %s"
    with get_db_connection() as conn:
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute(sql, (authority,))
            return cursor.fetchone()
            
def update_payment_status(authority, status):
    sql = "UPDATE payments SET status = %s WHERE authority = %s"
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, (status, authority))
            conn.commit()
