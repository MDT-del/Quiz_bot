import sqlite3
from config import Config
import os
import datetime
import json


def create_tables():
    """
    تمام جداول مورد نیاز برنامه را در دیتابیس ایجاد می‌کند.
    """
    os.makedirs('data', exist_ok=True)
    os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
    with sqlite3.connect(Config.DATABASE_PATH) as conn:
        cursor = conn.cursor()

        # جدول کاربران
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            premium_expires_at TIMESTAMP
        )''')

        # جدول سوالات
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question_text TEXT NOT NULL,
            options TEXT NOT NULL,
            correct_answer INTEGER NOT NULL,
            level TEXT NOT NULL,
            skill TEXT NOT NULL,
            media_path TEXT,
            media_type TEXT,
            question_type TEXT
        )''')

        # جدول نتایج آزمون
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS test_results (
            test_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            score INTEGER NOT NULL,
            level TEXT NOT NULL,
            test_type TEXT NOT NULL,
            test_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )''')

        # جدول پیام‌های پشتیبانی
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS support_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            message_text TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            admin_response_text TEXT,
            responded_at TIMESTAMP,
            status TEXT DEFAULT 'new',
            media_path TEXT,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )''')

        # جدول وضعیت آزمون کاربران
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS quiz_states (
            user_id INTEGER PRIMARY KEY,
            current_quiz TEXT,
            questions TEXT NOT NULL,
            current_question_index INTEGER NOT NULL,
            score INTEGER NOT NULL,
            start_time TEXT NOT NULL,
            level TEXT,
            test_type TEXT,
            deadline TEXT NOT NULL,
            answer_details TEXT
        )''')

        # جدول پرداخت‌ها
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            authority TEXT NOT NULL,
            amount INTEGER NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )''')

        print("--- database.py: create_tables() finished successfully ---"
              )  # این خط را اضافه کنید
        conn.commit()


def add_user(user_id, username, first_name, last_name):
    with sqlite3.connect(Config.DATABASE_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO users (user_id, username, first_name, last_name) VALUES (?, ?, ?, ?)",
            (user_id, username, first_name, last_name))
        conn.commit()


def get_user(user_id):
    with sqlite3.connect(Config.DATABASE_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id, ))
        user = cursor.fetchone()
        return dict(user) if user else None


def add_question(question_text,
                 options,
                 correct_answer,
                 level,
                 skill,
                 media_path=None,
                 media_type=None,
                 question_type='multiple_choice'):
    with sqlite3.connect(Config.DATABASE_PATH) as conn:
        cursor = conn.cursor()
        # Convert options list to JSON string for storage
        options_json = json.dumps(options)
        cursor.execute(
            "INSERT INTO questions (question_text, options, correct_answer, level, skill, media_path, media_type, question_type) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (question_text, options_json, correct_answer, level, skill,
             media_path, media_type, question_type))
        conn.commit()


def get_questions():
    with sqlite3.connect(Config.DATABASE_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM questions ORDER BY id DESC")
        questions = []
        for row in cursor.fetchall():
            question = dict(row)
            question['options'] = json.loads(
                question['options'])  # Convert JSON string back to list
            questions.append(question)
        return questions


def get_comprehensive_questions(count=Config.MAX_QUESTIONS):
    """سوالات آزمون جامع را به ترتیب ID از دیتابیس برمی‌گرداند."""
    with sqlite3.connect(Config.DATABASE_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # <-- CHANGE: عبارت ORDER BY RANDOM() به ORDER BY id ASC تغییر کرد
        cursor.execute(
            "SELECT * FROM questions WHERE question_type = 'جامع' ORDER BY id ASC LIMIT ?",
            (count, ))

        questions = []
        for row in cursor.fetchall():
            question = dict(row)
            question['options'] = json.loads(question['options'])
            questions.append(question)
        return questions


def get_questions_by_skill(skill, count=Config.MAX_QUESTIONS):
    """سوالات تصادفی را بر اساس یک مهارت خاص و فقط از نوع 'مهارتی' برمی‌گرداند."""
    with sqlite3.connect(Config.DATABASE_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # <-- CHANGE: افزودن شرط AND question_type = 'مهارتی' برای جداسازی کامل
        cursor.execute(
            "SELECT * FROM questions WHERE skill = ? AND question_type = 'مهارتی' ORDER BY RANDOM() LIMIT ?",
            (skill, count))

        questions = []
        for row in cursor.fetchall():
            question = dict(row)
            question['options'] = json.loads(question['options'])
            questions.append(question)
        return questions


def get_question_by_id(question_id):
    with sqlite3.connect(Config.DATABASE_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM questions WHERE id = ?", (question_id, ))
        question = cursor.fetchone()
        if question:
            q_dict = dict(question)
            q_dict['options'] = json.loads(q_dict['options'])
            return q_dict
        return None


def update_question(
        question_id,
        question_text,
        options,
        correct_answer,
        level,
        skill,
        question_type,  # این پارامتر اضافه شد
        media_path=None,
        media_type=None):
    with sqlite3.connect(Config.DATABASE_PATH) as conn:
        cursor = conn.cursor()
        options_json = json.dumps(options)
        cursor.execute(
            "UPDATE questions SET question_text = ?, options = ?, correct_answer = ?, level = ?, skill = ?, question_type = ?, media_path = ?, media_type = ? WHERE id = ?",  # فیلد question_type به کوئری اضافه شد
            (question_text, options_json, correct_answer, level, skill,
             question_type, media_path, media_type,
             question_id))  # متغیر question_type به مقادیر اضافه شد
        conn.commit()


def delete_question(question_id):
    with sqlite3.connect(Config.DATABASE_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM questions WHERE id = ?", (question_id, ))
        conn.commit()


def save_test_result(user_id, score, level, test_type='جامع'):
    with sqlite3.connect(Config.DATABASE_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO test_results (user_id, score, level, test_type) VALUES (?, ?, ?, ?)",
            (user_id, score, level, test_type))
        conn.commit()


def get_all_test_results():
    with sqlite3.connect(Config.DATABASE_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('''
            SELECT tr.test_id, tr.user_id, u.username, u.first_name, u.last_name,
                   tr.score, tr.level, tr.test_type, tr.test_date
            FROM test_results tr
            JOIN users u ON tr.user_id = u.user_id
            ORDER BY tr.test_date DESC
            ''')
        results = []
        for row in cursor.fetchall():
            result = dict(row)
            result['username'] = result['username'] if result[
                'username'] else 'N/A'
            result['first_name'] = result['first_name'] if result[
                'first_name'] else 'N/A'
            result['last_name'] = result['last_name'] if result[
                'last_name'] else ''
            results.append(result)
        return results


def delete_test_result(test_id):
    with sqlite3.connect(Config.DATABASE_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM test_results WHERE test_id = ?",
                       (test_id, ))
        conn.commit()


def get_user_stats(user_id):
    with sqlite3.connect(Config.DATABASE_PATH) as conn:
        cursor = conn.cursor()
        # Total tests
        cursor.execute("SELECT COUNT(*) FROM test_results WHERE user_id = ?",
                       (user_id, ))
        num_tests = cursor.fetchone()[0]

        # Total score
        cursor.execute("SELECT SUM(score) FROM test_results WHERE user_id = ?",
                       (user_id, ))
        total_score = cursor.fetchone()[0] or 0

        # Highest score
        cursor.execute("SELECT MAX(score) FROM test_results WHERE user_id = ?",
                       (user_id, ))
        highest_score = cursor.fetchone()[0] or 0

        # Average score
        average_score = (total_score / num_tests) if num_tests > 0 else 0

        return {
            'num_tests': num_tests,
            'total_score': total_score,
            'highest_score': highest_score,
            'average_score': round(average_score, 2)
        }


def get_last_test_time(user_id, test_type='جامع'):
    """آخرین زمان شرکت در یک نوع آزمون خاص را برمی‌گرداند."""
    with sqlite3.connect(Config.DATABASE_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT MAX(test_date) FROM test_results WHERE user_id = ? AND test_type = ?",
            (user_id, test_type))
        result = cursor.fetchone()[0]

        # <-- CHANGE: بررسی و تبدیل رشته به آبجکت datetime
        if result:
            # دیتابیس زمان را به صورت رشته برمی‌گرداند، ما آن را به آبجکت تاریخ تبدیل می‌کنیم
            return datetime.datetime.strptime(result, "%Y-%m-%d %H:%M:%S")

        # اگر کاربر تا به حال در آزمون شرکت نکرده باشد، None برمی‌گردانیم
        return None


def get_top_users(limit=10):
    with sqlite3.connect(Config.DATABASE_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            '''
            SELECT u.user_id, u.username, u.first_name, u.last_name, SUM(tr.score) as total_score
            FROM users u
            JOIN test_results tr ON u.user_id = tr.user_id
            GROUP BY u.user_id
            ORDER BY total_score DESC
            LIMIT ?
            ''', (limit, ))
        top_users = []
        for row in cursor.fetchall():
            user = dict(row)
            user['username'] = user['username'] if user['username'] else 'N/A'
            user['first_name'] = user['first_name'] if user[
                'first_name'] else 'N/A'
            user['last_name'] = user['last_name'] if user['last_name'] else ''
            user['score'] = user[
                'total_score']  # For consistency with old leaderboard format
            top_users.append(user)
        return top_users


def save_support_message(user_id, message_text, media_path=None):
    """پیام پشتیبانی (متنی یا همراه با آدرس رسانه) را ذخیره می‌کند."""
    with sqlite3.connect(Config.DATABASE_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO support_messages (user_id, message_text, media_path) VALUES (?, ?, ?)",
            (user_id, message_text, media_path))
        conn.commit()


def get_all_support_messages():
    """لیست تمام پیام‌های پشتیبانی را برای نمایش در پنل ادمین برمی‌گرداند."""
    with sqlite3.connect(Config.DATABASE_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # <-- CHANGE: استفاده از LEFT JOIN برای نمایش تمام پیام‌ها
        cursor.execute('''
            SELECT sm.id, sm.user_id, u.username, u.first_name, u.last_name,
                   sm.message_text, sm.timestamp, sm.admin_response_text,
                   sm.responded_at, sm.status, sm.media_path
            FROM support_messages sm
            LEFT JOIN users u ON sm.user_id = u.user_id
            ORDER BY sm.timestamp DESC
            ''')

        messages = []
        for row in cursor.fetchall():
            message = dict(row)
            # اگر کاربری در جدول users نبود، مقادیر پیش‌فرض نمایش داده می‌شود
            message['username'] = message['username'] if message[
                'username'] else 'نامشخص'
            message['first_name'] = message['first_name'] if message[
                'first_name'] else f"کاربر {message['user_id']}"
            message['last_name'] = message['last_name'] if message[
                'last_name'] else ''
            messages.append(message)
        return messages


def get_support_message_by_id(message_id):
    """یک پیام پشتیبانی خاص را با شناسه‌اش برمی‌گرداند."""
    with sqlite3.connect(Config.DATABASE_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # <-- CHANGE: استفاده از LEFT JOIN در این تابع هم برای هماهنگی
        cursor.execute(
            '''
            SELECT sm.id, sm.user_id, u.username, u.first_name, u.last_name,
                   sm.message_text, sm.timestamp, sm.admin_response_text,
                   sm.responded_at, sm.status, sm.media_path
            FROM support_messages sm
            LEFT JOIN users u ON sm.user_id = u.user_id
            WHERE sm.id = ?
        ''', (message_id, ))

        row = cursor.fetchone()
        if row:
            message = dict(row)
            message['username'] = message['username'] if message[
                'username'] else 'نامشخص'
            message['first_name'] = message['first_name'] if message[
                'first_name'] else f"کاربر {message['user_id']}"
            message['last_name'] = message['last_name'] if message[
                'last_name'] else ''
            return message
        return None


def update_support_message_response(message_id, admin_response_text):
    """
    Updates a support message with the admin's response and sets responded_at timestamp.
    """
    with sqlite3.connect(Config.DATABASE_PATH) as conn:
        cursor = conn.cursor()
        responded_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute(
            "UPDATE support_messages SET admin_response_text = ?, responded_at = ?, status = 'responded' WHERE id = ?",
            (admin_response_text, responded_at, message_id))
        conn.commit()


def update_support_message_status(message_id, status):
    """
    Updates the status of a support message.
    """
    with sqlite3.connect(Config.DATABASE_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE support_messages SET status = ? WHERE id = ?",
                       (status, message_id))
        conn.commit()


def save_quiz_state(user_id, state_data):
    with sqlite3.connect(Config.DATABASE_PATH) as conn:
        cursor = conn.cursor()

        # تبدیل لیست‌های پایتون به رشته JSON برای ذخیره‌سازی
        questions_json = json.dumps(state_data.get('questions', []))
        answer_details_json = json.dumps(state_data.get(
            'answer_details', []))  # <-- تبدیل لیست جزئیات به JSON
        start_time_str = state_data['start_time'].strftime("%Y-%m-%d %H:%M:%S")
        deadline_str = state_data['deadline'].strftime("%Y-%m-%d %H:%M:%S")

        cursor.execute(
            """
            INSERT OR REPLACE INTO quiz_states 
            (user_id, current_quiz, questions, current_question_index, score, start_time, level, test_type, deadline, answer_details)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, state_data.get('current_quiz'), questions_json,
             state_data.get('current_question_index'), state_data.get('score'),
             start_time_str, state_data.get('level'),
             state_data.get('test_type'), deadline_str, answer_details_json
             )  # <-- ذخیره جزئیات در دیتابیس
        )
        conn.commit()


def get_quiz_state(user_id):
    with sqlite3.connect(Config.DATABASE_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM quiz_states WHERE user_id = ?",
                       (user_id, ))
        row = cursor.fetchone()

        if row:
            state_data = dict(row)
            # تبدیل رشته‌های JSON به لیست‌های پایتون
            state_data['questions'] = json.loads(state_data['questions'])
            state_data['start_time'] = datetime.datetime.strptime(
                state_data['start_time'], "%Y-%m-%d %H:%M:%S")
            state_data['deadline'] = datetime.datetime.strptime(
                state_data['deadline'], "%Y-%m-%d %H:%M:%S")
            if state_data.get('answer_details'):
                state_data['answer_details'] = json.loads(
                    state_data['answer_details'])  # <-- بازیابی لیست جزئیات
            else:
                state_data['answer_details'] = []
            return state_data
        return None


def delete_quiz_state(user_id):
    """وضعیت آزمون کاربر را پس از اتمام آزمون از دیتابیس حذف می‌کند."""
    with sqlite3.connect(Config.DATABASE_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM quiz_states WHERE user_id = ?",
                       (user_id, ))
        conn.commit()


def delete_support_message(message_id):
    with sqlite3.connect(Config.DATABASE_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM support_messages WHERE id = ?",
                       (message_id, ))
        conn.commit()


def set_user_premium(user_id, duration_days=30):
    """اشتراک ویژه کاربر را برای مدت مشخصی فعال یا باطل می‌کند."""
    with sqlite3.connect(Config.DATABASE_PATH) as conn:
        cursor = conn.cursor()

        # اگر duration_days عددی مثبت باشد، تاریخ انقضا را تنظیم کن
        if duration_days and duration_days > 0:
            expiry_date = datetime.datetime.now() + datetime.timedelta(
                days=duration_days)
            # بررسی می‌کنیم ستون جدید وجود دارد یا خیر
            try:
                cursor.execute(
                    "UPDATE users SET premium_expires_at = ? WHERE user_id = ?",
                    (expiry_date, user_id))
            except sqlite3.OperationalError:
                # اگر ستون وجود نداشت، آن را اضافه کرده و سپس آپدیت می‌کنیم
                cursor.execute(
                    "ALTER TABLE users ADD COLUMN premium_expires_at TIMESTAMP;"
                )
                cursor.execute(
                    "UPDATE users SET premium_expires_at = ? WHERE user_id = ?",
                    (expiry_date, user_id))
        # اگر duration_days برابر 0 یا None باشد، اشتراک را لغو کن
        else:
            try:
                cursor.execute(
                    "UPDATE users SET premium_expires_at = NULL WHERE user_id = ?",
                    (user_id, ))
            except sqlite3.OperationalError:
                cursor.execute(
                    "ALTER TABLE users ADD COLUMN premium_expires_at TIMESTAMP;"
                )
                cursor.execute(
                    "UPDATE users SET premium_expires_at = NULL WHERE user_id = ?",
                    (user_id, ))

        conn.commit()


def is_user_premium(user_id):
    """بررسی می‌کند که آیا اشتراک ویژه کاربر معتبر است یا خیر."""
    with sqlite3.connect(Config.DATABASE_PATH) as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT premium_expires_at FROM users WHERE user_id = ?",
                (user_id, ))
            result = cursor.fetchone()

            if result and result[0]:
                # تاریخ ذخیره شده در دیتابیس را به آبجکت datetime تبدیل می‌کنیم
                expiry_date = datetime.datetime.strptime(
                    result[0].split('.')[0], "%Y-%m-%d %H:%M:%S")
                # اگر تاریخ انقضا در آینده باشد، کاربر ویژه است
                return datetime.datetime.now() < expiry_date

            return False
        except (sqlite3.OperationalError, IndexError):
            # اگر ستون premium_expires_at وجود نداشته باشد یا خطایی رخ دهد، کاربر ویژه نیست
            return False


def get_user_premium_expiry(user_id):
    """تاریخ انقضای اشتراک ویژه کاربر را برمی‌گرداند."""
    with sqlite3.connect(Config.DATABASE_PATH) as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT premium_expires_at FROM users WHERE user_id = ?",
                (user_id, ))
            result = cursor.fetchone()
            if result and result[0]:
                return datetime.datetime.strptime(result[0].split('.')[0],
                                                  "%Y-%m-%d %H:%M:%S")
        except (sqlite3.OperationalError, IndexError):
            return None
        return None


def get_all_users():
    """لیست تمام کاربران را برای نمایش در پنل ادمین برمی‌گرداند."""
    with sqlite3.connect(Config.DATABASE_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        # اطمینان از وجود ستون is_premium
        try:
            cursor.execute(
                "SELECT user_id, username, first_name, last_name, join_date, premium_expires_at FROM users ORDER BY join_date DESC"
            )
        except sqlite3.OperationalError:
            # اگر ستون وجود نداشت، آن را اضافه کن و دوباره کوئری را اجرا کن
            cursor.execute(
                "ALTER TABLE users ADD COLUMN premium_expires_at TIMESTAMP;")
            conn.commit()
            cursor.execute(
                "SELECT user_id, username, first_name, last_name, join_date, premium_expires_at FROM users ORDER BY join_date DESC"
            )

        users = cursor.fetchall()
        return [dict(row) for row in users]


def get_total_user_count():
    """تعداد کل کاربران ثبت‌نام کرده را برمی‌گرداند."""
    with sqlite3.connect(Config.DATABASE_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        return cursor.fetchone()[0]


def get_total_question_count():
    """تعداد کل سوالات موجود در دیتابیس را برمی‌گرداند."""
    with sqlite3.connect(Config.DATABASE_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM questions")
        return cursor.fetchone()[0]


def get_recent_quiz_count(hours=24):
    """تعداد آزمون‌های انجام شده در چند ساعت اخیر را برمی‌گرداند."""
    with sqlite3.connect(Config.DATABASE_PATH) as conn:
        cursor = conn.cursor()
        # زمان حال را به فرمت رشته‌ای که در دیتابیس ذخیره شده، تبدیل می‌کنیم
        time_threshold = datetime.datetime.now() - datetime.timedelta(
            hours=hours)
        cursor.execute(
            "SELECT COUNT(*) FROM test_results WHERE test_date >= ?",
            (time_threshold.strftime("%Y-%m-%d %H:%M:%S"), ))
        return cursor.fetchone()[0]


def get_questions_by_skill_and_level(skill, level, count=Config.MAX_QUESTIONS):
    """سوالات را بر اساس مهارت و سطح مشخص فیلتر می‌کند."""
    with sqlite3.connect(Config.DATABASE_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM questions WHERE skill = ? AND level = ? AND question_type = 'مهارتی' ORDER BY RANDOM() LIMIT ?",
            (skill, level, count))

        questions = []
        for row in cursor.fetchall():
            question = dict(row)
            question['options'] = json.loads(question['options'])
            questions.append(question)
        return questions


def create_payment_record(user_id, authority, amount):
    """یک رکورد پرداخت جدید در وضعیت انتظار ایجاد می‌کند."""
    with sqlite3.connect(Config.DATABASE_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO payments (user_id, authority, amount) VALUES (?, ?, ?)",
            (user_id, authority, amount))
        conn.commit()


#پرداخت های کاربر را برمی‌گرداند
def get_payment_by_authority(authority):
    """اطلاعات پرداخت را بر اساس کد authority برمی‌گرداند."""
    with sqlite3.connect(Config.DATABASE_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM payments WHERE authority = ?",
                       (authority, ))
        payment = cursor.fetchone()
        return dict(payment) if payment else None


def update_payment_status(authority, status):
    """وضعیت یک پرداخت را به‌روزرسانی می‌کند."""
    with sqlite3.connect(Config.DATABASE_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE payments SET status = ? WHERE authority = ?",
                       (status, authority))
        conn.commit()
