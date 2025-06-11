import telebot
from telebot import types
import sqlite3
from database import (add_user, get_questions, save_test_result,
                      get_user_stats, get_last_test_time,
                      get_questions_by_skill_and_level, get_question_by_id,
                      get_top_users, save_support_message,
                      get_support_message_by_id, get_comprehensive_questions,
                      save_quiz_state, get_quiz_state, delete_quiz_state,
                      is_user_premium, set_user_premium, get_all_users,
                      get_questions_by_skill_and_level,
                      get_user_premium_expiry, create_payment_record)
from zarinpal_payment.zarinpal import ZarinPal
from config import Config
import traceback
import time
import datetime
import jdatetime
import os
import html
import random

bot = telebot.TeleBot(Config.TOKEN)
support_sessions = {}


# --- بخش ۱: مدیریت منوها ---
def send_main_keyboard(user_id):
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    btn_quiz = types.KeyboardButton("آزمون‌ها و چالش‌ها")
    btn_premium = types.KeyboardButton("💎 حساب کاربری ویژه")
    btn_support = types.KeyboardButton("✉️ پشتیبانی")
    btn_help = types.KeyboardButton("❓ راهنما")
    markup.add(btn_quiz, btn_premium, btn_support, btn_help)
    bot.send_message(user_id, "به منوی اصلی خوش آمدید!", reply_markup=markup)


@bot.message_handler(func=lambda message: message.text == "آزمون‌ها و چالش‌ها")
def handle_quiz_menu(message):
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    btn_quiz_general = types.KeyboardButton("📝 آزمون جامع")
    btn_quiz_skill = types.KeyboardButton("📚 آزمون مهارتی")
    btn_stats = types.KeyboardButton("📊 آمار من")
    btn_leaderboard = types.KeyboardButton("🏆 جدول امتیازات")
    btn_back = types.KeyboardButton("بازگشت به منوی اصلی")
    markup.add(btn_quiz_general, btn_quiz_skill, btn_stats, btn_leaderboard,
               btn_back)
    bot.send_message(message.chat.id,
                     "لطفاً یکی از گزینه‌های زیر را انتخاب کنید:",
                     reply_markup=markup)


@bot.message_handler(
    func=lambda message: message.text == "بازگشت به منوی اصلی")
def back_to_main_menu(message):
    send_main_keyboard(message.chat.id)


# --- بخش ۲: دستورات عمومی ---
@bot.message_handler(commands=['start'])
def handle_start(message):
    add_user(message.from_user.id, message.from_user.username,
             message.from_user.first_name, message.from_user.last_name)
    markup = types.InlineKeyboardMarkup()
    channel_link = f"https://t.me/{Config.CHANNEL_ID.replace('@', '')}" if Config.CHANNEL_ID.startswith(
        '@') else Config.CHANNEL_ID
    markup.add(
        types.InlineKeyboardButton("عضویت در کانال", url=channel_link),
        types.InlineKeyboardButton("بررسی عضویت",
                                   callback_data="check_membership"))
    bot.send_message(
        message.chat.id,
        f"سلام {message.from_user.first_name} خوش آمدید!\n\nلطفاً برای استفاده از ربات، در کانال ما عضو شوید:",
        reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data == "check_membership")
def check_membership_callback(call):
    user_id = call.from_user.id
    try:
        if not Config.CHANNEL_ID:
            send_main_keyboard(user_id)
            return
        chat_member = bot.get_chat_member(Config.CHANNEL_ID, user_id)
        if chat_member.status in ['member', 'administrator', 'creator']:
            bot.answer_callback_query(call.id, "عضویت شما تایید شد!")
            send_main_keyboard(user_id)
        else:
            bot.answer_callback_query(call.id,
                                      "لطفاً ابتدا در کانال عضو شوید.",
                                      show_alert=True)
    except Exception as e:
        bot.send_message(user_id, "خطا در بررسی عضویت.")


# پرداخت و اشتراک ویژه
@bot.callback_query_handler(
    func=lambda call: call.data.startswith('buy_premium_'))
def handle_buy_premium(call):
    user_id = call.from_user.id
    parts = call.data.split('_')
    duration_days = int(parts[2])
    amount = int(parts[3])  # مبلغ به تومان

    # --- تغییر ۱: آدرس بازگشت در همینجا تعریف و به کلاس پاس داده می‌شود ---
    callback_url = f"{Config.REPLIT_APP_URL}/verify_payment"

    try:
        zarinpal = ZarinPal(
            merchant_id=Config.ZARINPAL_MERCHANT_CODE,
            callback_url=callback_url,
            sandbox=False  # برای تست True قرار دهید
        )

        description = f"خرید اشتراک {duration_days} روزه برای ربات"

        # ارسال درخواست پرداخت
        response = zarinpal.payment_request(amount=amount,
                                            description=description)

        # --- تغییر ۲: نحوه دریافت authority عوض شده است ---
        authority = response.get("data", {}).get("authority")

        if authority:
            # --- تغییر ۳: لینک پرداخت حالا باید جداگانه ساخته شود ---
            payment_url = zarinpal.generate_payment_url(authority)

            # ذخیره رکورد پرداخت در دیتابیس
            create_payment_record(user_id, authority, amount)

            # ارسال لینک پرداخت به کاربر
            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton("پرداخت آنلاین", url=payment_url))
            bot.send_message(
                user_id,
                "برای تکمیل خرید، روی دکمه زیر کلیک کرده و پرداخت را انجام دهید:",
                reply_markup=markup)
            bot.answer_callback_query(call.id)
        else:
            # اگر authority دریافت نشود، یعنی خطایی رخ داده
            error_message = response.get("errors", {}).get(
                "message", "خطای نامشخص از درگاه پرداخت")
            bot.answer_callback_query(call.id,
                                      f"خطا: {error_message}",
                                      show_alert=True)
            print(f"Zarinpal error: {response.get('errors')}")

    except Exception as e:
        bot.answer_callback_query(call.id,
                                  "خطای پیش‌بینی نشده در سیستم پرداخت.",
                                  show_alert=True)
        print(f"Error creating payment link: {e}")


@bot.message_handler(func=lambda message: message.text == "📊 آمار من")
def handle_my_stats(message):
    user_id = message.chat.id
    stats = get_user_stats(user_id)
    if stats and stats['num_tests'] > 0:
        response_text = (f"📊 *آمار عملکرد شما:*\n\n"
                         f"تعداد آزمون‌ها: `{stats['num_tests']}`\n"
                         f"کل امتیازات: `{stats['total_score']}`\n"
                         f"بالاترین امتیاز: `{stats['highest_score']}`\n"
                         f"میانگین امتیاز: `{stats['average_score']}`")
    else:
        response_text = "شما هنوز در هیچ آزمونی شرکت نکرده‌اید."
    bot.send_message(user_id, response_text, parse_mode='Markdown')


@bot.message_handler(func=lambda message: message.text == "🏆 جدول امتیازات")
def handle_leaderboard(message):
    top_users = get_top_users(limit=10)
    if not top_users:
        bot.send_message(message.chat.id, "هنوز امتیازی در جدول ثبت نشده است.")
        return
    leaderboard_text = "🏆 *جدول ۱۰ کاربر برتر:*\n\n"
    for i, user in enumerate(top_users):
        leaderboard_text += f"*{i+1}.* {user['first_name']} - `{user['score']}` امتیاز\n"
    bot.send_message(message.chat.id, leaderboard_text, parse_mode='Markdown')


@bot.message_handler(func=lambda message: message.text == "❓ راهنما")
def handle_help(message):
    help_text = (
        "*راهنمای جامع ربات آزمون زبان*\n\n"
        "به ربات ما خوش آمدید! در اینجا نحوه کار با بخش‌های مختلف توضیح داده شده است:\n\n"
        "------------------------------------\n\n"
        "📝 *آزمون‌ها*\n"
        "1.  *آزمون جامع:* این آزمون سطح کلی شما را با سوالات متنوع می‌سنجد.\n"
        "2.  *آزمون مهارتی:* این آزمون‌ها (مخصوص کاربران ویژه) روی یک مهارت خاص مانند گرامر یا لغت تمرکز دارند.\n\n"
        "⏳ *زمان‌بندی آزمون:*\n"
        "برای هر سوال در آزمون، شما *۱ دقیقه* (در آزمون جامع ۴۰ ثانیه) زمان برای پاسخگویی دارید.\n\n"
        "------------------------------------\n\n"
        "💎 *حساب کاربری ویژه*\n"
        "با ارتقاء به حساب کاربری ویژه، از مزایای زیر بهره‌مند می‌شوید:\n"
        "- شرکت *نامحدود* در تمام آزمون‌ها.\n"
        "- دسترسی کامل به تمام *آزمون‌های مهارتی*.\n"
        "- مشاهده *پاسخ صحیح* پس از جواب دادن به هر سوال.\n")
    bot.send_message(message.chat.id, help_text, parse_mode='Markdown')


# --- بخش ۳: منطق آزمون‌ها ---


@bot.message_handler(func=lambda message: message.text == "📝 آزمون جامع")
def handle_general_quiz(message):
    user_id = message.chat.id
    if get_quiz_state(user_id):
        bot.send_message(user_id, "شما یک آزمون نیمه‌کاره دارید.")
        return
    if not is_user_premium(user_id):
        last_test_time = get_last_test_time(user_id, 'جامع')
        if last_test_time:
            time_since_last_test = datetime.datetime.now() - last_test_time
            cooldown_seconds = Config.QUIZ_COOLDOWN_HOURS * 3600
            if time_since_last_test.total_seconds() < cooldown_seconds:
                remaining_seconds = cooldown_seconds - time_since_last_test.total_seconds(
                )
                remaining_hours = int(remaining_seconds // 3600)
                remaining_minutes = int((remaining_seconds % 3600) // 60)
                bot.send_message(
                    user_id,
                    f"شما به تازگی در آزمون جامع شرکت کرده‌اید. لطفاً *{remaining_hours}* ساعت و *{remaining_minutes}* دقیقه دیگر دوباره امتحان کنید.\n\n💎 کاربران ویژه محدودیتی برای شرکت در آزمون ندارند.",
                    parse_mode='Markdown')
                return
    try:
        questions = get_comprehensive_questions(Config.MAX_QUESTIONS)
        if not questions:
            bot.send_message(user_id,
                             "متاسفم، سوالی برای آزمون جامع یافت نشد.")
            return
        now = datetime.datetime.now()
        time_limit_seconds = len(
            questions) * 40  # زمان جدید: ۴۰ ثانیه برای هر سوال
        deadline = now + datetime.timedelta(seconds=time_limit_seconds)
        quiz_state = {
            'questions': questions,
            'current_question_index': 0,
            'score': 0,
            'start_time': now,
            'deadline': deadline,
            'test_type': 'جامع',
            'level': 'جامع',
            'answer_details': []
        }
        save_quiz_state(user_id, quiz_state)
        bot.send_message(user_id,
                         "⚠️ *توجه:* پاسخ شما قابل ویرایش نیست.",
                         parse_mode='Markdown')
        time.sleep(1)
        send_question(user_id, questions[0])
    except Exception as e:
        print(f"Error starting general quiz: {e}")


@bot.message_handler(func=lambda message: message.text == "📚 آزمون مهارتی")
def handle_skill_quiz(message):
    user_id = message.chat.id
    if not is_user_premium(user_id):
        bot.send_message(user_id, "این بخش مخصوص کاربران ویژه است.")
        return

    markup = types.InlineKeyboardMarkup(row_width=2)
    for skill in Config.QUIZ_SKILLS:
        markup.add(
            types.InlineKeyboardButton(skill,
                                       callback_data=f"select_level_{skill}"))

    bot.send_message(
        message.chat.id,
        "شما کاربر ویژه هستید! لطفاً ابتدا مهارت مورد نظر را انتخاب کنید:",
        reply_markup=markup)


@bot.callback_query_handler(
    func=lambda call: call.data.startswith('select_level_'))
def handle_level_selection(call):
    user_id = call.message.chat.id
    skill = call.data.split('_')[2]

    markup = types.InlineKeyboardMarkup(row_width=3)
    level_buttons = []
    for level in Config.QUIZ_LEVELS:
        level_buttons.append(
            types.InlineKeyboardButton(
                level, callback_data=f"start_quiz_{skill}_{level}"))

    markup.add(*level_buttons)
    bot.edit_message_text(
        f"عالی! حالا سطح مورد نظر برای مهارت *{skill}* را انتخاب کنید:",
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=markup,
        parse_mode='Markdown')


@bot.callback_query_handler(
    func=lambda call: call.data.startswith('start_quiz_'))
def handle_skill_quiz_start(call):
    user_id = call.message.chat.id
    if get_quiz_state(user_id):
        bot.answer_callback_query(call.id,
                                  "شما یک آزمون دیگر نیمه‌کاره دارید!",
                                  show_alert=True)
        return

    _, _, skill, level = call.data.split('_', 3)

    try:
        questions = get_questions_by_skill_and_level(skill, level,
                                                     Config.MAX_QUESTIONS)

        if not questions:
            bot.answer_callback_query(
                call.id,
                f"سوالی برای مهارت «{skill}» در سطح «{level}» یافت نشد.",
                show_alert=True)
            return

        now = datetime.datetime.now()
        quiz_state = {
            'questions': questions,
            'current_question_index': 0,
            'score': 0,
            'start_time': now,
            'deadline': now + datetime.timedelta(seconds=len(questions) * 60),
            'test_type': 'مهارتی',
            'level': f"{skill} - {level}"
        }
        save_quiz_state(user_id, quiz_state)
        bot.answer_callback_query(call.id)
        bot.edit_message_text(f"آزمون *{skill}* سطح *{level}* شروع شد!",
                              chat_id=call.message.chat.id,
                              message_id=call.message.message_id,
                              parse_mode='Markdown')
        time.sleep(1)
        send_question(user_id, questions[0])
    except Exception as e:
        print(f"Error starting skill quiz: {e}")


def send_question(user_id, question):
    markup = types.InlineKeyboardMarkup(row_width=1)
    for i, option in enumerate(question['options']):
        markup.add(
            types.InlineKeyboardButton(
                option, callback_data=f"answer_{question['id']}_{i}"))
    quiz_state = get_quiz_state(user_id)
    time_left_str = ""
    if quiz_state and 'deadline' in quiz_state:
        time_left = quiz_state['deadline'] - datetime.datetime.now()
        if time_left.total_seconds() > 0:
            minutes, seconds = divmod(int(time_left.total_seconds()), 60)
            time_left_str = f"⏳ *زمان باقی‌مانده: {minutes} دقیقه و {seconds} ثانیه*\n\n"

    current_question_number = quiz_state.get('current_question_index', 0) + 1
    if quiz_state and quiz_state.get('test_type') == 'جامع':
        header = "*آزمون جامع*"
    else:
        header = f"*{question['skill']} - سطح {question['level']}*"
    numbered_question_text = f"*{current_question_number}.* {question['question_text']}"
    final_text = f"{time_left_str}{header}\n\n{numbered_question_text}"
    try:
        if question.get('media_path'):
            # منطق ارسال رسانه
            pass
        else:
            bot.send_message(user_id,
                             final_text,
                             parse_mode='Markdown',
                             reply_markup=markup)
    except Exception as e:
        print(f"Error sending question: {e}")


@bot.callback_query_handler(func=lambda call: call.data.startswith('answer_'))
def handle_answer(call):
    user_id = call.message.chat.id
    quiz_state = get_quiz_state(user_id)
    if not quiz_state: return

    if 'deadline' in quiz_state and datetime.datetime.now(
    ) > quiz_state['deadline']:
        bot.send_message(user_id, "⏰ زمان آزمون شما به پایان رسیده است!")
        end_quiz(user_id, quiz_state)
        return

    current_question_index = quiz_state['current_question_index']
    current_question = quiz_state['questions'][current_question_index]
    _, question_id_str, chosen_option_index_str = call.data.split('_')
    if int(question_id_str) != current_question['id']:
        bot.answer_callback_query(call.id,
                                  "این سوال قبلا پاسخ داده شده است.",
                                  show_alert=True)
        return

    chosen_option_index = int(chosen_option_index_str)
    is_correct = (chosen_option_index == current_question['correct_answer'])

    if is_correct: quiz_state['score'] += 1

    if quiz_state.get('test_type') == 'جامع':
        if 'answer_details' not in quiz_state:
            quiz_state['answer_details'] = []
        quiz_state['answer_details'].append({
            'skill':
            current_question.get('skill'),
            'correct':
            is_correct
        })

    try:
        is_premium = is_user_premium(user_id)
        feedback = ""
        edited_markup = types.InlineKeyboardMarkup(row_width=1)
        if is_premium:
            feedback = ""
            for i, option in enumerate(current_question['options']):
                emoji = "✅" if i == current_question['correct_answer'] else (
                    "❌" if i == chosen_option_index else "")
                edited_markup.add(
                    types.InlineKeyboardButton(
                        f"{emoji} {option}",
                        callback_data=f"answered_{current_question['id']}_{i}")
                )
        else:
            feedback = "پاسخ شما ثبت شد."
            for i, option in enumerate(current_question['options']):
                button_text = f"✔️ {option}" if i == chosen_option_index else option
                edited_markup.add(
                    types.InlineKeyboardButton(
                        button_text,
                        callback_data=f"answered_{current_question['id']}_{i}")
                )

        quiz_state_for_title = get_quiz_state(user_id)
        if quiz_state_for_title and quiz_state_for_title.get(
                'test_type') == 'جامع':
            header = "*آزمون جامع*"
        else:
            header = f"*{current_question['skill']} - سطح {current_question['level']}*"

        numbered_question_text = f"*{current_question_index + 1}.* {current_question['question_text']}"
        final_display_text = f"{header}\n\n{numbered_question_text}"
        if feedback:
            final_display_text += f"\n\n{feedback}"

        if call.message.content_type == 'text':
            bot.edit_message_text(text=final_display_text,
                                  chat_id=call.message.chat.id,
                                  message_id=call.message.message_id,
                                  parse_mode='Markdown',
                                  reply_markup=edited_markup)
        else:
            bot.edit_message_caption(caption=final_display_text,
                                     chat_id=call.message.chat.id,
                                     message_id=call.message.message_id,
                                     parse_mode='Markdown',
                                     reply_markup=edited_markup)

    except telebot.apihelper.ApiTelegramException as e:
        if "message is not modified" not in str(e):
            print(f"Error editing message: {e}")

    bot.answer_callback_query(call.id)
    quiz_state['current_question_index'] += 1
    save_quiz_state(user_id, quiz_state)

    if quiz_state['current_question_index'] < len(quiz_state['questions']):
        time.sleep(1)
        send_question(
            user_id,
            quiz_state['questions'][quiz_state['current_question_index']])
    else:
        end_quiz(user_id, quiz_state)


def get_level_from_percentage(percentage):
    if percentage <= 20: return "A1.1"
    elif percentage <= 35: return "A1.2"
    elif percentage <= 52: return "A2.1"
    elif percentage <= 62: return "A2.2"
    elif percentage <= 75: return "B1"
    elif percentage <= 90: return "B2"
    else: return "C+ (C1/C2)"


def end_quiz(user_id, quiz_state):
    total_questions = len(quiz_state['questions'])
    score = quiz_state['score']
    duration = datetime.datetime.now() - quiz_state['start_time']
    minutes, seconds = divmod(int(duration.total_seconds()), 60)
    save_test_result(user_id, score, quiz_state.get('level'),
                     quiz_state.get('test_type'))
    percentage = round(
        (score / total_questions) * 100) if total_questions > 0 else 0
    user_level = get_level_from_percentage(percentage)
    summary_text = (f"🎉 *آزمون شما به پایان رسید!*\n\n"
                    f" درصد موفقیت: *{percentage}%*\n"
                    f" سطح تقریبی شما: *{user_level}*")

    if quiz_state.get(
            'test_type'
    ) == 'جامع' and 'answer_details' in quiz_state and quiz_state[
            'answer_details']:
        analysis_text = "\n\n📊 *تحلیل عملکرد شما بر اساس مهارت:*\n"
        skill_stats = {
            skill: {
                "correct": 0,
                "total": 0
            }
            for skill in Config.QUIZ_SKILLS
        }
        for detail in quiz_state['answer_details']:
            skill = detail.get('skill', '').strip()
            if skill and skill in skill_stats:
                skill_stats[skill]['total'] += 1
                if detail['correct']: skill_stats[skill]['correct'] += 1

        performance = {}
        has_tested_skills = False
        for skill_name, data in skill_stats.items():
            if data['total'] > 0:
                has_tested_skills = True
                skill_percentage = round(
                    (data['correct'] / data['total']) * 100)
                analysis_text += f"- *{skill_name}*: {skill_percentage}٪ موفقیت ({data['correct']} از {data['total']})\n"
                performance[skill_name] = skill_percentage

        if has_tested_skills and len(performance) > 1:
            max_perf = max(performance.values())
            min_perf = min(performance.values())
            if max_perf != min_perf:
                strengths = [
                    skill for skill, perc in performance.items()
                    if perc == max_perf
                ]
                weaknesses = [
                    skill for skill, perc in performance.items()
                    if perc == min_perf
                ]
                analysis_text += f"\n✨ *نقطه قوت شما:* {', '.join(strengths)}"
                analysis_text += f"\n🧗 *نیاز به تمرین بیشتر:* {', '.join(weaknesses)}"

        if has_tested_skills:
            summary_text += analysis_text

    bot.send_message(user_id, summary_text, parse_mode='Markdown')
    if percentage <= 20:
        bot.send_message(
            user_id,
            "برای تقویت پایه زبان خود، پیشنهاد می‌کنیم در دوره‌های آموزشی سطح A1 ما شرکت کنید."
        )
    delete_quiz_state(user_id)


# --- بخش ۴: پشتیبانی و سایر موارد ---


@bot.message_handler(func=lambda message: message.text == "✉️ پشتیبانی")
def handle_support(message):
    user_id = message.chat.id
    support_sessions[user_id] = {'in_support': True}
    markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    btn_cancel = types.KeyboardButton("انصراف از ارسال پیام")
    markup.add(btn_cancel)
    bot.send_message(
        user_id,
        "لطفاً پیام متنی یا عکس خود را برای پشتیبانی ارسال کنید یا از دکمه زیر برای انصراف استفاده کنید:",
        reply_markup=markup)


@bot.message_handler(
    func=lambda message: message.text == "انصراف از ارسال پیام")
def handle_cancel_support(message):
    user_id = message.chat.id
    if user_id in support_sessions:
        del support_sessions[user_id]
    bot.send_message(user_id, "ارسال پیام لغو شد.")
    send_main_keyboard(user_id)


@bot.message_handler(content_types=['text'],
                     func=lambda message: support_sessions.get(
                         message.chat.id, {}).get('in_support'))
def handle_support_message_text(message):
    user_id = message.chat.id
    try:
        save_support_message(user_id, message.text)
        admin_notification = f"یک پیام پشتیبانی جدید از کاربر {message.from_user.first_name} (@{message.from_user.username}) دریافت شد."
        for admin_id in Config.ADMIN_IDS:
            bot.send_message(admin_id, admin_notification)
            bot.forward_message(admin_id, user_id, message.message_id)
        bot.send_message(user_id, "پیام شما با موفقیت برای پشتیبانی ارسال شد.")
        if user_id in support_sessions: del support_sessions[user_id]
        send_main_keyboard(user_id)
    except Exception as e:
        bot.send_message(user_id, "خطا در ارسال پیام.")
        print(f"Error handling support text: {e}")


@bot.message_handler(content_types=['photo'],
                     func=lambda message: support_sessions.get(
                         message.chat.id, {}).get('in_support'))
def handle_support_photo(message):
    user_id = message.chat.id
    try:
        photo_file_id = message.photo[-1].file_id
        file_info = bot.get_file(photo_file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        unique_filename = f"support_{user_id}_{int(time.time())}.jpg"
        save_path = os.path.join(Config.UPLOAD_FOLDER, unique_filename)
        with open(save_path, 'wb') as new_file:
            new_file.write(downloaded_file)
        media_path_for_db = os.path.join('media', unique_filename)
        caption = message.caption if message.caption else "تصویر ارسالی (بدون متن)"
        save_support_message(user_id, caption, media_path_for_db)
        admin_notification = f"یک پیام تصویری جدید از کاربر {message.from_user.first_name} (@{message.from_user.username}) دریافت شد. برای مشاهده به پنل ادمین مراجعه کنید."
        for admin_id in Config.ADMIN_IDS:
            bot.send_message(admin_id, admin_notification)
        bot.send_message(user_id,
                         "تصویر شما با موفقیت برای پشتیبانی ارسال شد.")
        if user_id in support_sessions: del support_sessions[user_id]
        send_main_keyboard(user_id)
    except Exception as e:
        bot.send_message(user_id, "خطا در ارسال تصویر.")
        print(f"Error handling support photo: {e}")


@bot.message_handler(func=lambda message: message.text == "💎 حساب کاربری ویژه")
def handle_premium_account(message):
    user_id = message.chat.id

    if is_user_premium(user_id):
        # ... (کد نمایش وضعیت کاربر ویژه که قبلاً نوشتیم، بدون تغییر باقی می‌ماند)
        expiry_date_gregorian = get_user_premium_expiry(user_id)
        if expiry_date_gregorian:
            shamsi_date = jdatetime.datetime.fromgregorian(
                datetime=expiry_date_gregorian)
            expiry_date_str_shamsi = shamsi_date.strftime("%Y/%m/%d")
            premium_text = (
                f"✨ *شما کاربر ویژه هستید!*\n\n"
                f"اعتبار حساب شما تا تاریخ *{expiry_date_str_shamsi}* معتبر است."
            )
        else:
            premium_text = "شما کاربر ویژه هستید."
    else:
        premium_text = (
            "✨ *حساب کاربری ویژه (Premium Account)*\n\n"
            "با ارتقاء به حساب کاربری ویژه، از قابلیت‌های انحصاری زیر بهره‌مند شوید."
        )

        markup = types.InlineKeyboardMarkup()
        # قیمت را می‌توانید از فایل کانفیگ بخوانید
        price = 1000  # 50,000 تومان
        markup.add(
            types.InlineKeyboardButton(
                f"💳 خرید اشتراک ۳۰ روزه ({price:,} تومان)",
                callback_data=f"buy_premium_30_{price}"))
        bot.send_message(message.chat.id,
                         premium_text,
                         parse_mode='Markdown',
                         reply_markup=markup)
        return  # برای اینکه پیام دیفالت ارسال نشود

    bot.send_message(message.chat.id, premium_text, parse_mode='Markdown')


@bot.message_handler(commands=['admin'])
def admin_panel_command(message):
    user_id = message.chat.id
    if user_id in Config.ADMIN_IDS:
        bot.send_message(
            user_id,
            f"به پنل ادمین خوش آمدید!\nلینک پنل: {Config.REPLIT_APP_URL}/dashboard"
        )


def send_admin_response_to_user(user_telegram_id, admin_response_text):
    try:
        bot.send_message(user_telegram_id,
                         f"*پاسخ پشتیبانی:*\n\n{admin_response_text}",
                         parse_mode='Markdown')
        return True
    except Exception as e:
        print(f"Error sending admin response to user {user_telegram_id}: {e}")
        return False


def send_payment_confirmation(user_id, duration_days):
    try:
        text = f"✅ پرداخت شما با موفقیت تایید شد!\nاشتراک ویژه شما به مدت *{duration_days}* روز فعال گردید."
        bot.send_message(user_id, text, parse_mode='Markdown')
        send_main_keyboard(user_id)  # منوی اصلی را هم نمایش می‌دهیم
        return True
    except Exception as e:
        print(f"Could not send payment confirmation to {user_id}: {e}")
        return False
