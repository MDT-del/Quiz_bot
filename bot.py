import telebot
from telebot import types
# import mysql.connector # No direct MySQL connection here, should be handled by database.py
from database import (
    add_user,
    # get_questions, # Usually for admin panel, bot might use more specific getters
    save_test_result,
    get_user_stats,
    get_last_test_time,
    # get_questions_by_skill, # Potentially unused if get_questions_by_skill_and_level is preferred
    get_question_by_id, # Used for quiz logic if needed, though current quiz state holds questions
    get_top_users,
    save_support_message,
    # get_support_message_by_id, # Usually for admin panel
    get_comprehensive_questions,
    save_quiz_state,
    get_quiz_state,
    delete_quiz_state,
    is_user_premium,
    set_user_premium, # Used by payment callback, might be better if payment logic calls it directly or via an API
    # get_all_users, # Usually for admin panel
    get_questions_by_skill_and_level,
    get_user_premium_expiry, # Used for display
    create_payment_record # Used for initiating payment
)
from config import Config
import traceback
import time
import datetime # Ensure this is standard datetime
import jdatetime # For Shamsi date conversion
import os
import html # For escaping user input if ever needed in HTML/Markdown contexts
import random # If any randomization is needed (e.g. for question order, though DB handles RAND() now)
import uuid # For generating unique IDs like payment authority
import json # Added for parsing options if they are string
import logging

# Configure logger for this module
logger = logging.getLogger(__name__)
# BasicConfig should be ideally set in main.py or the entry point of the application
# However, if not set, a default handler will be used by logging.
# For robustness, ensure main.py calls logging.basicConfig()

bot = telebot.TeleBot(Config.TOKEN, parse_mode='Markdown') # Default parse mode

# In-memory store for multi-step operations like support.
# Consider a more persistent store (e.g., Redis, or database table) for production if needed.
support_sessions = {}
user_quiz_sessions = {} # To store active quiz message IDs for editing

# --- بخش ۱: مدیریت منوها ---
def send_main_keyboard(user_id, text="به منوی اصلی خوش آمدید!"):
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    btn_quiz = types.KeyboardButton("📝 آزمون‌ها و چالش‌ها") # Emoji added for consistency
    btn_premium = types.KeyboardButton("💎 حساب کاربری ویژه")
    btn_support = types.KeyboardButton("✉️ پشتیبانی")
    btn_help = types.KeyboardButton("❓ راهنما")
    markup.add(btn_quiz, btn_premium, btn_support, btn_help)
    try:
        bot.send_message(user_id, text, reply_markup=markup)
    except telebot.apihelper.ApiTelegramException as e:
        logger.error(f"Error sending main keyboard to {user_id}: {e}", exc_info=True)

@bot.message_handler(func=lambda message: message.text == "📝 آزمون‌ها و چالش‌ها")
def handle_quiz_menu(message):
    user = message.from_user
    add_user(user.id, user.username, user.first_name, user.last_name) # اطمینان از وجود کاربر
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    btn_quiz_general = types.KeyboardButton("📝 آزمون جامع")
    btn_quiz_skill = types.KeyboardButton("📚 آزمون مهارتی")
    btn_stats = types.KeyboardButton("📊 آمار من")
    btn_leaderboard = types.KeyboardButton("🏆 جدول امتیازات")
    btn_back = types.KeyboardButton("⬅️ بازگشت به منوی اصلی") # Emoji added
    markup.add(btn_quiz_general, btn_quiz_skill, btn_stats, btn_leaderboard, btn_back)
    try:
        bot.send_message(message.chat.id,
                         "لطفاً یکی از گزینه‌های زیر را انتخاب کنید:",
                         reply_markup=markup)
    except telebot.apihelper.ApiTelegramException as e:
        logger.error(f"Error sending quiz menu to {message.chat.id}: {e}", exc_info=True)


@bot.message_handler(func=lambda message: message.text == "⬅️ بازگشت به منوی اصلی")
def back_to_main_menu(message):
    send_main_keyboard(message.chat.id)


# --- بخش ۲: دستورات عمومی ---
@bot.message_handler(commands=['start'])
def handle_start(message):
    user = message.from_user
    try:
        add_user(user.id, user.username, user.first_name, user.last_name)
        logger.info(f"User {user.id} ({user.username}) started the bot or user data updated.")
    except Exception as e:
        logger.error(f"Error adding/updating user {user.id} in handle_start: {e}", exc_info=True)
        # Decide if bot should notify user of this failure or not. For now, proceed.

    welcome_text = f"سلام {html.escape(user.first_name or 'کاربر')} عزیز، خوش آمدید!\n\n"
    if Config.CHANNEL_ID:
        markup = types.InlineKeyboardMarkup()
        try:
            channel_link = f"https://t.me/{Config.CHANNEL_ID.replace('@', '')}" if Config.CHANNEL_ID.startswith('@') else Config.CHANNEL_ID
            markup.add(
                types.InlineKeyboardButton("عضویت در کانال", url=channel_link),
                types.InlineKeyboardButton("✅ بررسی عضویت", callback_data="check_membership")
            )
            welcome_text += "لطفاً برای استفاده از ربات، ابتدا در کانال ما عضو شوید و سپس دکمه بررسی عضویت را بزنید:"
            bot.send_message(message.chat.id, welcome_text, reply_markup=markup)
        except Exception as e: # Catch potential errors with channel link or sending message
            logger.error(f"Error preparing or sending channel membership message for {user.id}: {e}", exc_info=True)
            bot.send_message(message.chat.id, "به ربات ما خوش آمدید! مشکلی در نمایش لینک کانال پیش آمده، اما می‌توانید از سایر امکانات استفاده کنید.")
            send_main_keyboard(message.chat.id) # Fallback to main menu
    else:
        # No channel ID configured, send main menu directly
        logger.info("No channel ID configured. Sending main menu directly.")
        send_main_keyboard(message.chat.id, text=welcome_text + "می‌توانید از امکانات ربات استفاده کنید.")


@bot.callback_query_handler(func=lambda call: call.data == "check_membership")
def check_membership_callback(call):
    user_id = call.from_user.id
    if not Config.CHANNEL_ID:
        bot.answer_callback_query(call.id, "بررسی عضویت نیاز نیست چون کانالی تنظیم نشده.")
        send_main_keyboard(user_id)
        return
    try:
        chat_member = bot.get_chat_member(Config.CHANNEL_ID, user_id)
        if chat_member.status in ['member', 'administrator', 'creator']:
            bot.answer_callback_query(call.id, "عضویت شما تایید شد! ✅")
            bot.delete_message(call.message.chat.id, call.message.message_id) # Remove the inline keyboard
            send_main_keyboard(user_id)
        else:
            bot.answer_callback_query(call.id, "❌ شما هنوز در کانال عضو نشده‌اید. لطفاً ابتدا عضو شوید.", show_alert=True)
    except telebot.apihelper.ApiTelegramException as e:
        logger.error(f"API Error checking membership for {user_id} in {Config.CHANNEL_ID}: {e}", exc_info=True)
        if "user not found" in str(e).lower() or "chat not found" in str(e).lower() or "user_not_participant" in str(e).lower():
             bot.answer_callback_query(call.id, "❌ شما هنوز در کانال عضو نشده‌اید. لطفاً ابتدا عضو شوید.", show_alert=True)
        else:
            bot.answer_callback_query(call.id, "خطا در بررسی عضویت. لطفاً لحظاتی دیگر تلاش کنید.", show_alert=True)
    except Exception as e:
        logger.error(f"Unexpected error checking membership for {user_id}: {e}", exc_info=True)
        bot.answer_callback_query(call.id, "خطای ناشناخته در بررسی عضویت.", show_alert=True)


@bot.message_handler(func=lambda message: message.text == "💎 حساب کاربری ویژه")
def handle_premium_account(message):
    user = message.from_user
    add_user(user.id, user.username, user.first_name, user.last_name) # اطمینان از وجود کاربر
    user_id = user.id # استفاده از user.id به جای message.chat.id برای ثبات
    premium_text = ""
    markup = None

    if is_user_premium(user_id):
        expiry_date_gregorian = get_user_premium_expiry(user_id)
        if expiry_date_gregorian and isinstance(expiry_date_gregorian, datetime.datetime):
            try:
                shamsi_date = jdatetime.datetime.fromgregorian(datetime=expiry_date_gregorian)
                expiry_date_str_shamsi = shamsi_date.strftime("%Y/%m/%d ساعت %H:%M")
                premium_text = (
                    f"✨ *شما کاربر ویژه هستید!*\n\n"
                    f"اعتبار حساب شما تا تاریخ *{expiry_date_str_shamsi}* معتبر است."
                )
            except Exception as e:
                logger.error(f"Error converting premium expiry date for user {user_id}: {e}", exc_info=True)
                premium_text = "✨ *شما کاربر ویژه هستید!*\n\n امکان نمایش تاریخ انقضا وجود ندارد."
        else:
            premium_text = "✨ *شما کاربر ویژه هستید!*\n\n تاریخ انقضای اشتراک شما مشخص نیست."
    else:
        premium_text = (
            "✨ *حساب کاربری ویژه (Premium Account)*\n\n"
            "با ارتقاء به حساب کاربری ویژه، از قابلیت‌های انحصاری زیر بهره‌مند شوید:\n"
            "- شرکت *نامحدود* در تمام آزمون‌ها.\n"
            "- دسترسی کامل به تمام *آزمون‌های مهارتی*.\n"
            "- مشاهده *پاسخ صحیح* پس از جواب دادن به هر سوال.\n"
            # "- امکانات بیشتر به زودی...\n" # Example for future
        )
        if Config.REPLIT_APP_URL and Config.ZARINPAL_MERCHANT_CODE:
            markup = types.InlineKeyboardMarkup()
            # TODO: Consider making price and duration configurable
            price_30_days = 10000  # 10,000 تومان برای ۳۰ روز
            price_90_days = 25000  # 25,000 تومان برای ۹۰ روز
            markup.add(
                types.InlineKeyboardButton(
                    f"💳 اشتراک ۳۰ روزه ({price_30_days:,} تومان)",
                    callback_data=f"buy_premium_30_{price_30_days}")
            )
            markup.add(
                types.InlineKeyboardButton(
                    f"💳 اشتراک ۹۰ روزه ({price_90_days:,} تومان)",
                    callback_data=f"buy_premium_90_{price_90_days}")
            )
        else:
            premium_text += "\n\n⚠️ سیستم پرداخت در حال حاضر غیرفعال است. لطفاً بعداً مراجعه کنید."
    try:
        bot.send_message(message.chat.id, premium_text, reply_markup=markup) # parse_mode is default Markdown
    except telebot.apihelper.ApiTelegramException as e:
        logger.error(f"Error sending premium account info to {user_id}: {e}", exc_info=True)


@bot.callback_query_handler(func=lambda call: call.data.startswith('buy_premium_'))
def handle_buy_premium(call):
    user_id = call.from_user.id
    try:
        parts = call.data.split('_')
        if len(parts) < 4:
            logger.warning(f"Invalid buy_premium callback data: {call.data} for user {user_id}")
            bot.answer_callback_query(call.id, "خطا: درخواست نامعتبر.", show_alert=True)
            return

        duration_days = int(parts[2])
        amount = int(parts[3])  # مبلغ به تومان

        if not Config.REPLIT_APP_URL or not Config.ZARINPAL_MERCHANT_CODE:
            bot.answer_callback_query(call.id, "خطا: سیستم پرداخت هنوز پیکربندی نشده است.", show_alert=True)
            return

        authority = str(uuid.uuid4())
        create_payment_record(user_id, authority, amount) # This should return True on success
        logger.info(f"Payment record created for user {user_id}, authority {authority}, amount {amount}.")

        payment_url = (f"{Config.REPLIT_APP_URL.strip('/')}/payment/pay.php?"
                       f"user_id={user_id}&amount={amount}&order_id={authority}&duration={duration_days}")

        markup_pay = types.InlineKeyboardMarkup()
        markup_pay.add(types.InlineKeyboardButton("⬅️ بازگشت", callback_data="cancel_payment"),
                       types.InlineKeyboardButton("پرداخت آنلاین 💳", url=payment_url))

        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"برای خرید اشتراک *{duration_days} روزه* به مبلغ *{amount:,} تومان*، روی دکمه پرداخت آنلاین کلیک کنید:",
            reply_markup=markup_pay
        )
        bot.answer_callback_query(call.id)

    except ValueError:
        logger.error(f"ValueError in buy_premium callback data: {call.data} for user {user_id}", exc_info=True)
        bot.answer_callback_query(call.id, "خطا در پردازش درخواست.", show_alert=True)
    except Exception as e:
        logger.error(f"Error creating payment link for user {user_id}: {e}", exc_info=True)
        bot.answer_callback_query(call.id, "خطای پیش‌بینی نشده در سیستم پرداخت.", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data == "cancel_payment")
def handle_cancel_payment(call):
    # Re-send the premium account message
    handle_premium_account(call.message) # call.message here is the original message
    bot.answer_callback_query(call.id, "عملیات پرداخت لغو شد.")
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except: # Ignore if message is already deleted or cannot be deleted
        pass


@bot.message_handler(func=lambda message: message.text == "📊 آمار من")
def handle_my_stats(message):
    user = message.from_user
    add_user(user.id, user.username, user.first_name, user.last_name) # اطمینان از وجود کاربر
    user_id = user.id
    stats = get_user_stats(user_id) # Assuming get_user_stats returns a dict or None
    if stats and stats.get('num_tests', 0) > 0:
        response_text = (f"📊 *آمار عملکرد شما:*\n\n"
                         f"تعداد آزمون‌ها: `{stats['num_tests']}`\n"
                         f"کل امتیازات: `{stats['total_score']}`\n"
                         f"بالاترین امتیاز: `{stats['highest_score']}`\n"
                         f"میانگین امتیاز: `{stats['average_score']:.2f}`") # Format average
    else:
        response_text = "شما هنوز در هیچ آزمونی شرکت نکرده‌اید. با شرکت در آزمون‌ها، آمار خود را اینجا ببینید!"
    try:
        bot.send_message(user_id, response_text) # parse_mode is default Markdown
    except telebot.apihelper.ApiTelegramException as e:
        logger.error(f"Error sending stats to {user_id}: {e}", exc_info=True)


@bot.message_handler(func=lambda message: message.text == "🏆 جدول امتیازات")
def handle_leaderboard(message):
    top_users = get_top_users(limit=10) # Assuming this returns a list of dicts
    if not top_users:
        bot.send_message(message.chat.id, "هنوز امتیازی در جدول ثبت نشده است. اولین نفر باشید!")
        return
    
    leaderboard_text = "🏆 *جدول ۱۰ کاربر برتر:*\n\n"
    for i, user_stat in enumerate(top_users):
        user_name = html.escape(user_stat.get('first_name', 'کاربر ناشناس'))
        score = user_stat.get('total_score', 0) # Changed from 'score' to 'total_score' based on database.py
        leaderboard_text += f"*{i+1}.* {user_name} - `{score}` امتیاز\n"
    try:
        bot.send_message(message.chat.id, leaderboard_text) # parse_mode is default Markdown
    except telebot.apihelper.ApiTelegramException as e:
        logger.error(f"Error sending leaderboard to {message.chat.id}: {e}", exc_info=True)


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
        "برای هر سوال در آزمون جامع *۴۰ ثانیه* و در آزمون مهارتی *۱ دقیقه* زمان برای پاسخگویی دارید.\n\n"
        "------------------------------------\n\n"
        "💎 *حساب کاربری ویژه*\n"
        "با ارتقاء به حساب کاربری ویژه، از مزایای زیر بهره‌مند می‌شوید:\n"
        "- شرکت *نامحدود* در تمام آزمون‌ها.\n"
        "- دسترسی کامل به تمام *آزمون‌های مهارتی*.\n"
        "- مشاهده *پاسخ صحیح* پس از جواب دادن به هر سوال.\n\n"
        "------------------------------------\n\n"
        "✉️ *پشتیبانی*\n"
        "در صورت داشتن هرگونه سوال یا مشکل، از طریق بخش پشتیبانی با ما در تماس باشید.\n\n"
        "📊 *آمار و امتیازات*\n"
        "عملکرد خود را در بخش 'آمار من' پیگیری کنید و جایگاه خود را در 'جدول امتیازات' ببینید."
    )
    try:
        bot.send_message(message.chat.id, help_text) # parse_mode is default Markdown
    except telebot.apihelper.ApiTelegramException as e:
        logger.error(f"Error sending help to {message.chat.id}: {e}", exc_info=True)


# --- بخش ۳: منطق آزمون‌ها ---
def start_quiz_logic(user_id, questions, test_type, level_display_name):
    """Helper function to start a quiz (comprehensive or skill-based)."""
    if not questions:
        bot.send_message(user_id, "متاسفم، سوالی برای این آزمون یافت نشد. لطفاً بعداً دوباره تلاش کنید.")
        return False

    now = datetime.datetime.now()
    # Time limit: 40s for comprehensive, 60s for skill-based per question
    time_per_question = 40 if test_type == 'جامع' else 60
    time_limit_seconds = len(questions) * time_per_question
    deadline = now + datetime.timedelta(seconds=time_limit_seconds)

    quiz_state = {
        'questions': questions,
        'current_question_index': 0,
        'score': 0,
        'start_time': now,
        'deadline': deadline,
        'test_type': test_type,
        'level': level_display_name, # This is what gets saved in test_results
        'answer_details': [] # For comprehensive quiz analysis
    }
    save_quiz_state(user_id, quiz_state)
    
    # Clear any previous quiz message ID for this user
    if user_id in user_quiz_sessions:
        del user_quiz_sessions[user_id]

    bot.send_message(user_id, "⚠️ *توجه:* پاسخ شما پس از انتخاب قابل ویرایش نیست.", parse_mode='Markdown')
    time.sleep(0.5) # Brief pause
    send_question_to_user(user_id, questions[0])
    return True

@bot.message_handler(func=lambda message: message.text == "📝 آزمون جامع")
def handle_general_quiz(message):
    user = message.from_user
    add_user(user.id, user.username, user.first_name, user.last_name) # اطمینان از وجود کاربر
    user_id = user.id
    if get_quiz_state(user_id): # Check if a quiz is already in progress
        bot.send_message(user_id, "شما یک آزمون نیمه‌کاره دارید. لطفاً ابتدا آن را تمام کنید یا منتظر بمانید تا زمان آن به پایان برسد.")
        # Optionally, resend the current question of the active quiz
        # current_quiz_state = get_quiz_state(user_id)
        # send_question_to_user(user_id, current_quiz_state['questions'][current_quiz_state['current_question_index']])
        return

    if not is_user_premium(user_id):
        last_test_time = get_last_test_time(user_id, 'جامع') # test_type 'جامع'
        if last_test_time and isinstance(last_test_time, datetime.datetime):
            time_since_last_test = datetime.datetime.now() - last_test_time
            cooldown_seconds = Config.QUIZ_COOLDOWN_HOURS * 3600
            if time_since_last_test.total_seconds() < cooldown_seconds:
                remaining_seconds = cooldown_seconds - time_since_last_test.total_seconds()
                remaining_hours = int(remaining_seconds // 3600)
                remaining_minutes = int((remaining_seconds % 3600) // 60)
                bot.send_message(
                    user_id,
                    f"شما به تازگی در آزمون جامع شرکت کرده‌اید. لطفاً *{remaining_hours}* ساعت و *{remaining_minutes}* دقیقه دیگر دوباره امتحان کنید.\n\n"
                    f"💎 کاربران ویژه محدودیتی برای شرکت در آزمون ندارند."
                )
                return
    try:
        questions = get_comprehensive_questions(Config.MAX_QUESTIONS)
        start_quiz_logic(user_id, questions, 'جامع', 'جامع')
    except Exception as e:
        logger.error(f"Error starting general quiz for user {user_id}: {e}", exc_info=True)
        bot.send_message(user_id, "خطایی در شروع آزمون جامع رخ داد. لطفاً به پشتیبانی اطلاع دهید.")


@bot.message_handler(func=lambda message: message.text == "📚 آزمون مهارتی")
def handle_skill_quiz_selection(message): # Renamed for clarity
    user = message.from_user
    add_user(user.id, user.username, user.first_name, user.last_name) # اطمینان از وجود کاربر
    user_id = user.id
    if not is_user_premium(user_id):
        bot.send_message(user_id, "این بخش مخصوص کاربران ویژه است. با خرید اشتراک به این آزمون‌ها دسترسی پیدا کنید.")
        # Optionally, call handle_premium_account to show purchase options
        # handle_premium_account(message)
        return

    markup = types.InlineKeyboardMarkup(row_width=2) # Max 2 skills per row
    skill_buttons = [types.InlineKeyboardButton(skill, callback_data=f"select_level_{skill}") for skill in Config.QUIZ_SKILLS]
    markup.add(*skill_buttons) # Add all skill buttons

    bot.send_message(
        message.chat.id,
        "شما کاربر ویژه هستید! 👍\nلطفاً ابتدا مهارت مورد نظر برای آزمون را انتخاب کنید:",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('select_level_'))
def handle_level_selection(call):
    user_id = call.message.chat.id
    try:
        skill = call.data.split('_')[2] # e.g. "گرامر"

        markup = types.InlineKeyboardMarkup(row_width=3) # Max 3 levels per row
        level_buttons = [
            types.InlineKeyboardButton(level, callback_data=f"start_skill_quiz_{skill}_{level}")
            for level in Config.QUIZ_LEVELS
        ]
        markup.add(*level_buttons)

        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"عالی! حالا سطح دشواری برای مهارت *{html.escape(skill)}* را انتخاب کنید:",
            reply_markup=markup
        )
        bot.answer_callback_query(call.id)
    except Exception as e:
        logger.error(f"Error in level selection for skill from callback {call.data}: {e}", exc_info=True)
        bot.answer_callback_query(call.id, "خطا در پردازش انتخاب سطح.", show_alert=True)


@bot.callback_query_handler(func=lambda call: call.data.startswith('start_skill_quiz_'))
def handle_skill_quiz_start(call):
    user_id = call.message.chat.id
    if get_quiz_state(user_id):
        bot.answer_callback_query(call.id, "شما یک آزمون دیگر نیمه‌کاره دارید!", show_alert=True)
        return

    try:
        _, _, _, skill, level = call.data.split('_', 4) # e.g. "start_skill_quiz_گرامر_آسان"
        
        questions = get_questions_by_skill_and_level(skill, level, Config.MAX_QUESTIONS)
        if not questions:
            bot.answer_callback_query(call.id, f"متاسفانه سوالی برای مهارت «{html.escape(skill)}» در سطح «{html.escape(level)}» یافت نشد.", show_alert=True)
            return

        level_display_name = f"{skill} - {level}" # For saving in test_results
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"آزمون مهارتی *{html.escape(skill)}* سطح *{html.escape(level)}* در حال آماده‌سازی است..."
        )
        bot.answer_callback_query(call.id) # Acknowledge callback
        start_quiz_logic(user_id, questions, 'مهارتی', level_display_name)

    except Exception as e:
        logger.error(f"Error starting skill quiz from callback {call.data} for user {user_id}: {e}", exc_info=True)
        bot.answer_callback_query(call.id, "خطایی در شروع آزمون مهارتی رخ داد.", show_alert=True)
        try: # Try to edit message to indicate failure if possible
            bot.edit_message_text("خطا در شروع آزمون. لطفاً دوباره تلاش کنید.", chat_id=call.message.chat.id, message_id=call.message.message_id)
        except:
            pass


def send_question_to_user(user_id, question_data):
    """Sends a question with inline keyboard options to the user."""
    quiz_state = get_quiz_state(user_id)
    if not quiz_state:
        logger.warning(f"Attempted to send question to user {user_id} but no active quiz state found.")
        # send_main_keyboard(user_id, "خطایی رخ داده، آزمون شما یافت نشد. به منوی اصلی بازگشتید.")
        return

    markup = types.InlineKeyboardMarkup(row_width=1) # One option per row for better readability
    
    # Ensure options are correctly parsed if they are stored as JSON string in question_data
    options_list = question_data.get('options')
    if isinstance(options_list, str):
        try:
            options_list = json.loads(options_list)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse options JSON for question ID {question_data.get('id')} for user {user_id}. Options: {options_list}")
            options_list = [] # Fallback to empty options

    if not isinstance(options_list, list):
        logger.error(f"Options for question ID {question_data.get('id')} is not a list for user {user_id}. Options: {options_list}")
        options_list = []


    for i, option_text in enumerate(options_list):
        markup.add(types.InlineKeyboardButton(str(option_text), callback_data=f"answer_{question_data['id']}_{i}"))

    time_left_str = ""
    if 'deadline' in quiz_state and isinstance(quiz_state['deadline'], datetime.datetime):
        time_left = quiz_state['deadline'] - datetime.datetime.now()
        if time_left.total_seconds() > 0:
            minutes, seconds = divmod(int(time_left.total_seconds()), 60)
            time_left_str = f"⏳ *زمان باقی‌مانده: {minutes} دقیقه و {seconds} ثانیه*\n\n"
        else: # Time is up, but this function was called. End quiz.
            logger.info(f"Time is up for user {user_id} while trying to send question. Ending quiz.")
            end_quiz(user_id, quiz_state) # Pass the current state
            return


    current_q_index = quiz_state.get('current_question_index', 0)
    total_questions_in_quiz = len(quiz_state.get('questions', []))
    question_number_display = f"سوال *{current_q_index + 1}* از *{total_questions_in_quiz}*"

    if quiz_state.get('test_type') == 'جامع':
        header = f"*آزمون جامع* - {question_number_display}"
    else: # Skill quiz
        skill_name = html.escape(question_data.get('skill', 'مهارتی'))
        level_name = html.escape(question_data.get('level', ''))
        header = f"*{skill_name}* (سطح {level_name}) - {question_number_display}"

    question_text_escaped = html.escape(question_data.get('question_text', 'متن سوال یافت نشد.'))
    final_text = f"{time_left_str}{header}\n\n{question_text_escaped}"

    sent_message = None
    try:
        media_path_db = question_data.get('media_path') # e.g., 'media/filename.mp3'
        media_type = question_data.get('media_type')

        if media_path_db and media_type:
            # Construct the full disk path inside the container
            # Config.UPLOAD_FOLDER should be the absolute path to 'static/media' inside the container, e.g., /app/static/media
            # media_path_db is 'media/filename.mp3'. We need just 'filename.mp3' to join with UPLOAD_FOLDER.
            filename_only = os.path.basename(media_path_db)
            full_disk_path = os.path.join(Config.UPLOAD_FOLDER, filename_only)

            logger.info(f"Attempting to send media DIRECTLY for question {question_data.get('id')}: type={media_type}, disk_path={full_disk_path}")

            if os.path.exists(full_disk_path):
                with open(full_disk_path, 'rb') as media_file_obj:
                    if media_type == 'image':
                        sent_message = bot.send_photo(user_id, photo=media_file_obj, caption=final_text, reply_markup=markup)
                    elif media_type == 'audio':
                        sent_message = bot.send_audio(user_id, audio=media_file_obj, caption=final_text, reply_markup=markup)
                    elif media_type == 'video':
                        sent_message = bot.send_video(user_id, video=media_file_obj, caption=final_text, reply_markup=markup)
                    else:
                        logger.warning(f"Unsupported media type '{media_type}' for direct send. Question {question_data.get('id')}. Sending as text.")
                        sent_message = bot.send_message(user_id, final_text, reply_markup=markup)
            else:
                logger.error(f"Media file NOT FOUND at {full_disk_path} for direct send. Question {question_data.get('id')}. Sending as text.")
                sent_message = bot.send_message(user_id, final_text, reply_markup=markup) # Fallback to text
        else:
            # No media path or type, send as text only
            sent_message = bot.send_message(user_id, final_text, reply_markup=markup)

        if sent_message:
            user_quiz_sessions[user_id] = sent_message.message_id
        else:
            # This case should ideally be handled by the fallbacks above, but log if it somehow occurs
            logger.error(f"sent_message was None after trying to send question (ID: {question_data.get('id')}) to user {user_id}, even after fallbacks.")
            # As a last resort, try sending a simple text message if nothing else worked
            bot.send_message(user_id, "خطایی در نمایش سوال رخ داد. لطفاً دوباره تلاش کنید یا به پشتیبانی اطلاع دهید.")


    except telebot.apihelper.ApiTelegramException as e:
        # Log API errors specifically, including if it was a direct send attempt
        media_info_for_log = f"(direct send attempt, path: {full_disk_path if 'full_disk_path' in locals() else 'N/A'})" if media_path_db and media_type else "(text only send attempt)"
        logger.error(f"API Error sending question ID {question_data.get('id')} to {user_id} {media_info_for_log}: {e}", exc_info=True)
        if "bot was blocked by the user" in str(e).lower():
            logger.warning(f"Bot was blocked by user {user_id}. Cleaning up quiz state.")
            delete_quiz_state(user_id)
        # If sending media failed, try sending as text only as a fallback if not already done
        elif media_path_db and media_type: # Only if media send was attempted and failed
            logger.info(f"Fallback: Sending question ID {question_data.get('id')} as text only to user {user_id} after media send API error.")
            try:
                sent_message = bot.send_message(user_id, final_text, reply_markup=markup)
                if sent_message: user_quiz_sessions[user_id] = sent_message.message_id
            except Exception as fallback_e:
                logger.error(f"Error sending fallback text for question ID {question_data.get('id')} to {user_id}: {fallback_e}", exc_info=True)

    except FileNotFoundError: # Specifically for direct send
        logger.error(f"Media file NOT FOUND at {full_disk_path if 'full_disk_path' in locals() else 'Unknown path'} for direct send. Question {question_data.get('id')}. Fallback to text.")
        try:
            sent_message = bot.send_message(user_id, final_text, reply_markup=markup)
            if sent_message: user_quiz_sessions[user_id] = sent_message.message_id
        except Exception as fallback_e:
            logger.error(f"Error sending fallback text for question ID {question_data.get('id')} after FileNotFoundError: {fallback_e}", exc_info=True)

    except Exception as e: # Catch-all for other unexpected errors
        media_info_for_log = f"(direct send attempt, path: {full_disk_path if 'full_disk_path' in locals() else 'N/A'})" if media_path_db and media_type else "(text only send attempt)"
        logger.error(f"Unexpected error sending question ID {question_data.get('id')} to {user_id} {media_info_for_log}: {e}", exc_info=True)
        # Fallback to text on other errors if media was involved
        if media_path_db and media_type:
            logger.info(f"Fallback: Sending question ID {question_data.get('id')} as text only to user {user_id} after unexpected error.")
            try:
                sent_message = bot.send_message(user_id, final_text, reply_markup=markup)
                if sent_message: user_quiz_sessions[user_id] = sent_message.message_id
            except Exception as fallback_e:
                logger.error(f"Error sending fallback text for question ID {question_data.get('id')} after unexpected error: {fallback_e}", exc_info=True)


@bot.callback_query_handler(func=lambda call: call.data.startswith('answer_'))
def handle_answer(call):
    user_id = call.message.chat.id
    quiz_state = get_quiz_state(user_id)

    if not quiz_state:
        bot.answer_callback_query(call.id, "متاسفانه آزمون شما یافت نشد یا منقضی شده است.", show_alert=True)
        # Try to clean up the UI if the message still exists
        try:
            bot.edit_message_text("این آزمون دیگر فعال نیست.", chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=None)
        except:
            pass # Ignore if message cannot be edited
        return

    if 'deadline' in quiz_state and isinstance(quiz_state['deadline'], datetime.datetime) and datetime.datetime.now() > quiz_state['deadline']:
        bot.answer_callback_query(call.id) # Acknowledge, then send message
        bot.send_message(user_id, "⏰ زمان آزمون شما به پایان رسیده است!")
        end_quiz(user_id, quiz_state)
        return

    current_question_index = quiz_state['current_question_index']
    if current_question_index >= len(quiz_state['questions']):
        logger.warning(f"User {user_id} answered but quiz index out of bounds. Ending quiz.")
        end_quiz(user_id, quiz_state)
        return

    current_question = quiz_state['questions'][current_question_index]

    try:
        _, question_id_str, chosen_option_index_str = call.data.split('_')
        question_id_answered = int(question_id_str)
        chosen_option_index = int(chosen_option_index_str)
    except ValueError:
        logger.error(f"Invalid answer callback data: {call.data} for user {user_id}", exc_info=True)
        bot.answer_callback_query(call.id, "خطا در پردازش پاسخ.", show_alert=True)
        return

    # Check if this question was already processed (e.g. due to double click or race condition)
    # This requires that current_question['id'] is what we expect.
    if question_id_answered != current_question.get('id'):
        bot.answer_callback_query(call.id, "این سوال قبلاً پاسخ داده شده یا سوال دیگری فعال است.", show_alert=True)
        return

    is_correct = (chosen_option_index == current_question.get('correct_answer'))

    if is_correct:
        quiz_state['score'] += 1

    # Store answer details for comprehensive quiz analysis
    if quiz_state.get('test_type') == 'جامع':
        if 'answer_details' not in quiz_state or not isinstance(quiz_state['answer_details'], list):
            quiz_state['answer_details'] = []
        quiz_state['answer_details'].append({
            'question_id': current_question.get('id'),
            'skill': current_question.get('skill'),
            'level': current_question.get('level'),
            'correct': is_correct,
            'chosen_option': chosen_option_index
        })

    # --- Feedback and UI Update ---
    feedback_message = ""
    is_premium_user = is_user_premium(user_id)
    options_list_for_feedback = current_question.get('options')
    if isinstance(options_list_for_feedback, str): # Ensure options are list
        try:
            options_list_for_feedback = json.loads(options_list_for_feedback)
        except: options_list_for_feedback = []


    edited_markup = types.InlineKeyboardMarkup(row_width=1)
    for i, option_text_raw in enumerate(options_list_for_feedback):
        option_text = html.escape(str(option_text_raw))
        prefix = ""
        if i == chosen_option_index: # User's choice
            prefix = "✔️ " # Tick for chosen
            if is_correct:
                 prefix = "✅ " # Green tick if correct
            else:
                 prefix = "❌ " # Red cross if incorrect
        elif is_premium_user and i == current_question.get('correct_answer'): # If premium, show correct answer
            prefix = "🎯 " # Target for correct answer if not chosen by user

        edited_markup.add(types.InlineKeyboardButton(f"{prefix}{option_text}", callback_data=f"answered_{current_question['id']}_{i}"))

    if is_premium_user:
        feedback_message = "✅ پاسخ صحیح" if is_correct else f"❌ پاسخ شما اشتباه بود. پاسخ صحیح: {html.escape(str(options_list_for_feedback[current_question.get('correct_answer')]))}"
    else:
        feedback_message = "پاسخ شما ثبت شد."
        if is_correct:
            feedback_message += " (درست)"
        else:
            feedback_message += " (نادرست)"


    # Reconstruct question text for editing
    current_q_idx_display = quiz_state.get('current_question_index', 0)
    total_q_in_quiz_display = len(quiz_state.get('questions', []))
    q_num_display_edit = f"سوال *{current_q_idx_display + 1}* از *{total_q_in_quiz_display}*"

    header_edit = ""
    if quiz_state.get('test_type') == 'جامع':
        header_edit = f"*آزمون جامع* - {q_num_display_edit}"
    else:
        skill_edit = html.escape(current_question.get('skill', 'مهارتی'))
        level_edit = html.escape(current_question.get('level', ''))
        header_edit = f"*{skill_edit}* (سطح {level_edit}) - {q_num_display_edit}"

    question_text_edit = html.escape(current_question.get('question_text', ''))
    edited_message_text = f"{header_edit}\n\n{question_text_edit}\n\n*{feedback_message}*"

    active_quiz_message_id = user_quiz_sessions.get(user_id)
    if active_quiz_message_id == call.message.message_id: # Ensure we are editing the correct message
        try:
            if call.message.content_type == 'text':
                bot.edit_message_text(text=edited_message_text,
                                      chat_id=call.message.chat.id,
                                      message_id=call.message.message_id,
                                      reply_markup=edited_markup)
            # elif call.message.content_type == 'photo': # Add for media if necessary
            #     bot.edit_message_caption(caption=edited_message_text, ...)
        except telebot.apihelper.ApiTelegramException as e:
            if "message is not modified" not in str(e).lower():
                logger.error(f"API Error editing answer feedback for user {user_id}, q_id {current_question.get('id')}: {e}", exc_info=True)
    else:
        logger.warning(f"Mismatch in message_id for editing answer for user {user_id}. Expected {active_quiz_message_id}, got {call.message.message_id}")
        # Send a new message as fallback if editing fails or message_id mismatch
        bot.send_message(user_id, f"نتیجه سوال شما:\n{feedback_message}", reply_markup=edited_markup)


    bot.answer_callback_query(call.id) # Acknowledge the callback immediately

    quiz_state['current_question_index'] += 1
    save_quiz_state(user_id, quiz_state) # Save state after incrementing index

    if quiz_state['current_question_index'] < len(quiz_state['questions']):
        time.sleep(1 if is_premium_user else 0.5) # Slightly longer pause for premium to read feedback
        send_question_to_user(user_id, quiz_state['questions'][quiz_state['current_question_index']])
    else:
        logger.info(f"All questions answered for user {user_id}. Ending quiz.")
        end_quiz(user_id, quiz_state)


def get_level_from_percentage(percentage):
    # Ensure percentage is within 0-100
    percentage = max(0, min(100, percentage))
    # Define level boundaries (upper bound)
    if percentage <= 20: return "A1.1 (مقدماتی ۱)"
    elif percentage <= 35: return "A1.2 (مقدماتی ۲)"
    elif percentage <= 52: return "A2.1 (پایه ۱)"
    elif percentage <= 62: return "A2.2 (پایه ۲)"
    elif percentage <= 75: return "B1 (متوسط)"
    elif percentage <= 90: return "B2 (فوق متوسط)"
    else: return "C1/C2 (پیشرفته)"


def end_quiz(user_id, quiz_state):
    if not quiz_state: # Should not happen if called correctly
        logger.error(f"end_quiz called for user {user_id} with no quiz_state.")
        delete_quiz_state(user_id) # Clean up just in case
        send_main_keyboard(user_id, "خطایی در پایان آزمون رخ داد.")
        return

    total_questions = len(quiz_state.get('questions', []))
    score = quiz_state.get('score', 0)

    # Ensure start_time is a datetime object
    start_time = quiz_state.get('start_time')
    if isinstance(start_time, str): # If loaded from DB as string initially
        try:
            start_time = datetime.datetime.fromisoformat(start_time)
        except ValueError:
            start_time = datetime.datetime.now() # Fallback
            logger.warning(f"Could not parse start_time string for user {user_id}, using current time as fallback.")
    elif not isinstance(start_time, datetime.datetime):
        start_time = datetime.datetime.now() # Fallback for other invalid types
        logger.warning(f"Invalid start_time type for user {user_id}, using current time as fallback.")

    duration = datetime.datetime.now() - start_time
    minutes, seconds = divmod(int(duration.total_seconds()), 60)

    try:
        save_test_result(user_id, score, quiz_state.get('level', 'N/A'), quiz_state.get('test_type', 'N/A'))
    except Exception as e:
        logger.error(f"Failed to save test result for user {user_id}: {e}", exc_info=True)
        # Decide if user should be notified

    percentage = round((score / total_questions) * 100) if total_questions > 0 else 0
    user_level_determined = get_level_from_percentage(percentage)

    summary_text = (f"🎉 *آزمون شما به پایان رسید!*\n\n"
                    f"تعداد سوالات: `{total_questions}`\n"
                    f"پاسخ‌های صحیح: `{score}`\n"
                    f"درصد موفقیت: *{percentage}%*\n"
                    f"سطح تقریبی شما: *{user_level_determined}*\n"
                    f"مدت زمان آزمون: *{minutes} دقیقه و {seconds} ثانیه*")

    if quiz_state.get('test_type') == 'جامع' and 'answer_details' in quiz_state and quiz_state['answer_details']:
        analysis_text = "\n\n📊 *تحلیل عملکرد شما بر اساس مهارت (در آزمون جامع):*\n"
        skill_stats = {skill: {"correct": 0, "total": 0} for skill in Config.QUIZ_SKILLS}

        for detail in quiz_state['answer_details']:
            skill = detail.get('skill', '').strip()
            if skill and skill in skill_stats: # Ensure skill is valid and was part of config
                skill_stats[skill]['total'] += 1
                if detail.get('correct'):
                    skill_stats[skill]['correct'] += 1

        performance_lines = []
        for skill_name, data in skill_stats.items():
            if data['total'] > 0:
                skill_percentage = round((data['correct'] / data['total']) * 100)
                performance_lines.append(f"- *{html.escape(skill_name)}*: {skill_percentage}٪ ({data['correct']} از {data['total']})")

        if performance_lines:
            summary_text += analysis_text + "\n".join(performance_lines)
            # Suggestion based on lowest performance if applicable (more complex logic)
            # For now, just showing the stats.

    try:
        bot.send_message(user_id, summary_text)
    except telebot.apihelper.ApiTelegramException as e:
        logger.error(f"Error sending quiz summary to {user_id}: {e}", exc_info=True)

    # Suggestion based on overall level (example)
    if percentage <= 35: # A1 level
        bot.send_message(user_id, "برای تقویت پایه زبان خود، پیشنهاد می‌کنیم در دوره‌های آموزشی سطح مقدماتی (A1/A2) ما شرکت کنید یا منابع مرتبط را مطالعه نمایید.")
    elif percentage <= 75: # B1 level
        bot.send_message(user_id, "عملکرد خوبی داشتید! برای رسیدن به سطوح بالاتر، تمرین مستمر روی مهارت‌های مختلف را فراموش نکنید.")

    delete_quiz_state(user_id)
    if user_id in user_quiz_sessions: # Clean up message_id store
        del user_quiz_sessions[user_id]

    send_main_keyboard(user_id, "آزمون به پایان رسید. برای شروع مجدد یا سایر گزینه‌ها، از منوی اصلی استفاده کنید.")


# --- بخش ۴: پشتیبانی و سایر موارد ---
@bot.message_handler(func=lambda message: message.text == "✉️ پشتیبانی")
def handle_support_request(message): # Renamed for clarity
    user = message.from_user
    add_user(user.id, user.username, user.first_name, user.last_name) # اطمینان از وجود کاربر
    user_id = user.id
    support_sessions[user_id] = {'in_support': True, 'stage': 'awaiting_message'}

    markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True, one_time_keyboard=True)
    btn_cancel = types.KeyboardButton("↪️ انصراف از ارسال پیام")
    markup.add(btn_cancel)

    bot.send_message(
        user_id,
        "شما وارد بخش پشتیبانی شده‌اید.\n"
        "لطفاً پیام متنی یا عکس خود را برای تیم پشتیبانی ارسال کنید.\n\n"
        "برای لغو، دکمه 'انصراف' را بزنید.",
        reply_markup=markup
    )

@bot.message_handler(func=lambda message: message.text == "↪️ انصراف از ارسال پیام")
def handle_cancel_support(message):
    user_id = message.chat.id
    if user_id in support_sessions:
        del support_sessions[user_id]
        logger.info(f"Support session cancelled by user {user_id}.")
    bot.send_message(user_id, "ارسال پیام به پشتیبانی لغو شد.")
    send_main_keyboard(user_id) # Go back to main menu with its keyboard


def forward_support_message_to_admins(user_id, first_name, username, message_id_to_forward=None, text_content=None, media_path_for_admin_info=None):
    """Helper to forward/notify admins about a new support message."""
    user_display = f"{html.escape(first_name or '')} (@{html.escape(username or 'N/A')}, ID: {user_id})"
    admin_notification_text = f"یک پیام پشتیبانی جدید از کاربر {user_display} دریافت شد."
    if media_path_for_admin_info: # If it's a media, inform admin to check panel
        admin_notification_text += f"\nنوع: تصویر/رسانه. برای مشاهده به پنل ادمین مراجعه کنید: {Config.REPLIT_APP_URL.strip('/')}/support_messages"

    for admin_id in Config.ADMIN_IDS:
        try:
            # ارسال پیام به ادمین بدون فرمت خاص برای جلوگیری از خطای entities
            bot.send_message(admin_id, admin_notification_text, parse_mode=None)
            if message_id_to_forward and not media_path_for_admin_info: # Forward only text directly
                bot.forward_message(admin_id, user_id, message_id_to_forward)
        except telebot.apihelper.ApiTelegramException as e:
            logger.error(f"Failed to send/forward support notification to admin {admin_id} for user {user_id}: {e}", exc_info=True)


@bot.message_handler(content_types=['text'], func=lambda message: support_sessions.get(message.chat.id, {}).get('stage') == 'awaiting_message')
def handle_support_message_text(message):
    user_id = message.chat.id
    user = message.from_user

    # Avoid processing "انصراف از ارسال پیام" if it somehow bypasses the specific handler
    if message.text == "↪️ انصراف از ارسال پیام":
        handle_cancel_support(message)
        return

    try:
        save_support_message(user_id, message.text) # Save text message to DB
        logger.info(f"Support text message from {user_id} saved.")

        forward_support_message_to_admins(user_id, user.first_name, user.username, message_id_to_forward=message.message_id)

        bot.send_message(user_id, "پیام شما با موفقیت برای تیم پشتیبانی ارسال شد. منتظر پاسخ ما باشید.")
    except Exception as e:
        logger.error(f"Error handling support text from {user_id}: {e}", exc_info=True)
        bot.send_message(user_id, "متاسفانه در ارسال پیام شما به پشتیبانی خطایی رخ داد. لطفاً دوباره تلاش کنید.")
    finally: # Always clean up session and send main menu
        if user_id in support_sessions:
            del support_sessions[user_id]
        send_main_keyboard(user_id)


@bot.message_handler(content_types=['photo'], func=lambda message: support_sessions.get(message.chat.id, {}).get('stage') == 'awaiting_message')
def handle_support_photo(message):
    user_id = message.chat.id
    user = message.from_user
    try:
        photo_file_id = message.photo[-1].file_id # Get the largest photo
        file_info = bot.get_file(photo_file_id)
        downloaded_file = bot.download_file(file_info.file_path)

        # Ensure UPLOAD_FOLDER exists (though it should be handled by Flask app startup too)
        if not os.path.exists(Config.UPLOAD_FOLDER):
            os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)

        unique_filename = f"support_photo_{user_id}_{int(time.time())}.jpg"
        save_path_on_disk = os.path.join(Config.UPLOAD_FOLDER, unique_filename)

        with open(save_path_on_disk, 'wb') as new_file:
            new_file.write(downloaded_file)

        media_path_for_db = os.path.join('media', unique_filename) # Relative path for DB
        caption_text = message.caption if message.caption else "تصویر ارسالی (بدون متن)"

        save_support_message(user_id, caption_text, media_path_for_db)
        logger.info(f"Support photo from {user_id} saved to {save_path_on_disk}, DB path: {media_path_for_db}.")

        forward_support_message_to_admins(user_id, user.first_name, user.username, media_path_for_admin_info=media_path_for_db)

        bot.send_message(user_id, "تصویر شما همراه با متن (در صورت وجود) با موفقیت برای پشتیبانی ارسال شد.")
    except Exception as e:
        logger.error(f"Error handling support photo from {user_id}: {e}", exc_info=True)
        bot.send_message(user_id, "متاسفانه در ارسال تصویر شما به پشتیبانی خطایی رخ داد. لطفاً دوباره تلاش کنید.")
    finally: # Always clean up session and send main menu
        if user_id in support_sessions:
            del support_sessions[user_id]
        send_main_keyboard(user_id)

# Fallback for other content types in support session to avoid them being handled by other handlers
@bot.message_handler(content_types=['audio', 'video', 'document', 'sticker', 'voice', 'location', 'contact'],
                     func=lambda message: support_sessions.get(message.chat.id, {}).get('stage') == 'awaiting_message')
def handle_unsupported_support_content(message):
    user_id = message.chat.id
    bot.send_message(user_id, "در حال حاضر فقط امکان ارسال پیام متنی یا عکس به پشتیبانی وجود دارد. لطفاً پیام خود را به صورت متنی یا عکس ارسال کنید، یا عملیات را لغو نمایید.")
    # We don't remove from support_sessions here, user might still want to send valid content or cancel.

@bot.message_handler(commands=['admin'])
def admin_panel_command(message):
    user_id = message.chat.id
    if user_id in Config.ADMIN_IDS:
        panel_url = Config.REPLIT_APP_URL.strip('/') + "/dashboard" if Config.REPLIT_APP_URL else "پنل ادمین (URL not configured)"
        bot.send_message(user_id, f"به پنل ادمین خوش آمدید!\nلینک پنل: {panel_url}")
    else:
        # Silently ignore or send a generic "unknown command" if desired
        logger.info(f"Non-admin user {user_id} tried to use /admin command.")


# --- Utility functions that might be called from admin_panel or other parts ---
# These functions are defined here so `admin_panel.py` can import them as `from bot import ...`

def send_admin_response_to_user(user_telegram_id, admin_response_text):
    """Sends a message from admin (via panel) to the user."""
    try:
        bot.send_message(user_telegram_id,
                         f"✉️ *پاسخ از طرف پشتیبانی:*\n\n{html.escape(admin_response_text)}",
                         parse_mode='Markdown') # MarkdownV2 might be better for more complex formatting
        logger.info(f"Admin response sent to user {user_telegram_id}.")
        return True
    except telebot.apihelper.ApiTelegramException as e:
        logger.error(f"Failed to send admin response to user {user_telegram_id}: {e}", exc_info=True)
        return False
    except Exception as e: # Catch any other unexpected error
        logger.error(f"Unexpected error sending admin response to user {user_telegram_id}: {e}", exc_info=True)
        return False


def send_payment_confirmation(user_id, duration_days, amount_paid=None, currency="تومان"):
    """Sends a payment confirmation message to the user."""
    try:
        text = f"✅ پرداخت شما با موفقیت تایید شد!\n"
        if amount_paid:
             text += f"مبلغ `{amount_paid:,} {currency}` دریافت شد.\n"
        text += f"اشتراک ویژه شما به مدت *{duration_days}* روز فعال گردید."

        bot.send_message(user_id, text, parse_mode='Markdown')
        send_main_keyboard(user_id, "اشتراک شما فعال شد! از امکانات ویژه لذت ببرید.")
        logger.info(f"Payment confirmation sent to user {user_id} for {duration_days} days.")
        return True
    except telebot.apihelper.ApiTelegramException as e:
        logger.error(f"Failed to send payment confirmation to {user_id}: {e}", exc_info=True)
        return False
    except Exception as e:
        logger.error(f"Unexpected error sending payment confirmation to {user_id}: {e}", exc_info=True)
        return False

# A catch-all handler for unhandled text messages (optional, can be noisy)
# @bot.message_handler(func=lambda message: True)
# def unhandled_message(message):
#     bot.send_message(message.chat.id, "متوجه منظور شما نشدم. لطفاً از دکمه‌های منو استفاده کنید یا از دستور /help برای راهنمایی کمک بگیرید.")

logger.info("Bot instance created and handlers configured.")

# Note: bot.infinity_polling() is typically called from main.py in a separate thread.
# Do not call it here if main.py is handling the bot's execution.
