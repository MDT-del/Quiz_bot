import telebot
from telebot import types
from database import (
    add_user, save_test_result, get_user_stats, get_last_test_time,
    get_question_by_id, get_top_users, save_support_message,
    get_comprehensive_questions, save_quiz_state, get_quiz_state, delete_quiz_state,
    is_user_premium, set_user_premium, get_questions_by_skill_and_level,
    get_user_premium_expiry
)
from config import Config
import traceback
import time
import datetime
import jdatetime
import os
import html
import random
import uuid
import json
import logging
from telebot.formatting import escape_markdown # For Markdown (V1)

logger = logging.getLogger("bot")
bot = telebot.TeleBot(Config.TOKEN)

support_sessions = {}
user_quiz_sessions = {}


# --- بخش ۱: مدیریت منوها ---
def send_main_keyboard(user_id, text="به منوی اصلی خوش آمدید!"):
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    btn_quiz = types.KeyboardButton("📝 آزمون‌ها و چالش‌ها")
    btn_premium = types.KeyboardButton("💎 حساب کاربری ویژه")
    btn_support = types.KeyboardButton("✉️ پشتیبانی")
    btn_help = types.KeyboardButton("❓ راهنما")
    markup.add(btn_quiz, btn_premium, btn_support, btn_help)
    try:
        bot.send_message(user_id, text, reply_markup=markup, parse_mode=None)
    except telebot.apihelper.ApiTelegramException as e:
        logger.error(f"Error sending main keyboard to {user_id}: {e}", exc_info=True)

@bot.message_handler(func=lambda message: message.text == "📝 آزمون‌ها و چالش‌ها")
def handle_quiz_menu(message):
    user = message.from_user
    add_user(user.id, user.username, user.first_name, user.last_name)
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    btn_quiz_general = types.KeyboardButton("📝 آزمون جامع")
    btn_quiz_skill = types.KeyboardButton("📚 آزمون مهارتی")
    btn_stats = types.KeyboardButton("📊 آمار من")
    btn_leaderboard = types.KeyboardButton("🏆 جدول امتیازات")
    btn_back = types.KeyboardButton("⬅️ بازگشت به منوی اصلی")
    markup.add(btn_quiz_general, btn_quiz_skill, btn_stats, btn_leaderboard, btn_back)
    try:
        bot.send_message(message.chat.id,
                         "لطفاً یکی از گزینه‌های زیر را انتخاب کنید:",
                         reply_markup=markup, parse_mode=None)
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

    # For welcome_text, we use html.escape for safety if displayed elsewhere, but send as plain to Telegram.
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
            bot.send_message(message.chat.id, welcome_text, reply_markup=markup, parse_mode=None)
        except Exception as e:
            logger.error(f"Error preparing or sending channel membership message for {user.id}: {e}", exc_info=True)
            bot.send_message(message.chat.id, "به ربات ما خوش آمدید! مشکلی در نمایش لینک کانال پیش آمده، اما می‌توانید از سایر امکانات استفاده کنید.", parse_mode=None)
            send_main_keyboard(message.chat.id)
    else:
        logger.info("No channel ID configured. Sending main menu directly.")
        send_main_keyboard(message.chat.id, text=welcome_text + "می‌توانید از امکانات ربات استفاده کنید.")

@bot.callback_query_handler(func=lambda call: call.data == "check_membership")
def check_membership_callback(call):
    user = call.from_user
    add_user(user.id, user.username, user.first_name, user.last_name)
    user_id = user.id
    if not Config.CHANNEL_ID:
        bot.answer_callback_query(call.id, "بررسی عضویت نیاز نیست چون کانالی تنظیم نشده.")
        send_main_keyboard(user_id)
        return
    try:
        chat_member = bot.get_chat_member(Config.CHANNEL_ID, user_id)
        if chat_member.status in ['member', 'administrator', 'creator']:
            bot.answer_callback_query(call.id, "عضویت شما تایید شد! ✅")
            try: bot.delete_message(call.message.chat.id, call.message.message_id)
            except: pass
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
    add_user(user.id, user.username, user.first_name, user.last_name)
    user_id = user.id
    premium_text = ""
    markup = types.InlineKeyboardMarkup()

    if is_user_premium(user_id):
        expiry_date_gregorian = get_user_premium_expiry(user_id)
        if expiry_date_gregorian and isinstance(expiry_date_gregorian, datetime.datetime):
            try:
                shamsi_date = jdatetime.datetime.fromgregorian(datetime=expiry_date_gregorian)
                expiry_date_str_shamsi = shamsi_date.strftime("%Y/%m/%d ساعت %H:%M")
                premium_text = (
                    f"✨ *شما کاربر ویژه هستید!*\n\n"
                    f"اعتبار حساب شما تا تاریخ *{escape_markdown(expiry_date_str_shamsi)}* معتبر است."
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
            "- مشاهده *پاسخ صحیح* پس از جواب دادن به هر سوال.\n\n"
            "لطفاً برای فعال‌سازی، یکی از طرح‌های زیر را انتخاب کنید:"
        )
        price_30_days = 50000
        price_90_days = 125000
        markup.add(
            types.InlineKeyboardButton(
                f"💳 اشتراک ۳۰ روزه ({price_30_days:,} تومان)",
                callback_data=f"show_payment_info_30_{price_30_days}")
        )
        markup.add(
            types.InlineKeyboardButton(
                f"💳 اشتراک ۹۰ روزه ({price_90_days:,} تومان)",
                callback_data=f"show_payment_info_90_{price_90_days}")
        )
    try:
        bot.send_message(message.chat.id, premium_text, reply_markup=markup if markup.keyboard else None, parse_mode="Markdown")
    except telebot.apihelper.ApiTelegramException as e:
        logger.error(f"Error sending premium account info to {user_id} (Markdown attempt): {e}", exc_info=True)
        plain_premium_text = premium_text.replace("*", "") # Basic unescaping for plain text
        try:
            bot.send_message(message.chat.id, plain_premium_text, reply_markup=markup if markup.keyboard else None, parse_mode=None)
        except Exception as e2:
            logger.error(f"Error sending premium account info (plain text fallback) to {user_id}: {e2}", exc_info=True)

@bot.callback_query_handler(func=lambda call: call.data.startswith('show_payment_info_'))
def handle_show_payment_info(call):
    user = call.from_user
    add_user(user.id, user.username, user.first_name, user.last_name)
    user_id = user.id

    try:
        parts = call.data.split('_')
        duration_days = int(parts[3])
        amount = int(parts[4])
    except (IndexError, ValueError) as e:
        logger.error(f"Invalid callback data for show_payment_info: {call.data} - Error: {e}")
        bot.answer_callback_query(call.id, "خطا در پردازش درخواست شما.", show_alert=True)
        return

    card_number = "621986190922127"

    # Text for Markdown (V1)
    message_text_md = (
        f"✅ برای فعال‌سازی اشتراک *{duration_days} روزه* به مبلغ *{amount:,} تومان*، لطفاً مراحل زیر را دنبال کنید:\n\n"
        f"1. مبلغ را به شماره کارت زیر واریز نمایید:\n"
        f"`{card_number}`\n" # Code block for easy copy
        f"(با کلیک روی شماره کارت، در کلیپ‌بورد شما کپی می‌شود)\n\n"
        f"2. پس از واریز، لطفاً از رسید پرداختی خود یک اسکرین‌شات (عکس) تهیه کنید.\n\n"
        f"3. اسکرین‌شات را از طریق بخش «✉️ پشتیبانی» در منوی اصلی برای ما ارسال کنید.\n\n"
        f"پس از بررسی و تایید رسید توسط تیم پشتیبانی، اشتراک ویژه شما در اسرع وقت فعال خواهد شد.\n\n"
        f"🙏 از صبر و شکیبایی شما سپاسگزاریم."
    )

    try:
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=message_text_md,
            parse_mode="Markdown",
            reply_markup=None
        )
        bot.answer_callback_query(call.id, "اطلاعات پرداخت نمایش داده شد.")
    except telebot.apihelper.ApiTelegramException as e:
        logger.error(f"Error editing message for payment info to user {user_id} (Markdown): {e}", exc_info=True)
        plain_message_text = message_text_md.replace("*", "").replace("`", "")
        try:
            bot.send_message(user_id, plain_message_text, parse_mode=None) # Send as plain
            bot.answer_callback_query(call.id, "اطلاعات پرداخت نمایش داده شد.")
        except Exception as e2:
            logger.error(f"Error sending payment info as new message (plain text) to user {user_id}: {e2}", exc_info=True)
            bot.answer_callback_query(call.id, "خطا در نمایش اطلاعات پرداخت.", show_alert=True)

@bot.message_handler(func=lambda message: message.text == "📊 آمار من")
def handle_my_stats(message):
    user = message.from_user
    add_user(user.id, user.username, user.first_name, user.last_name)
    user_id = user.id
    stats = get_user_stats(user_id)
    response_text = ""
    if stats and stats.get('num_tests', 0) > 0:
        response_text = (
            f"📊 *آمار عملکرد شما:*\n\n"
            f"تعداد آزمون‌ها: `{stats['num_tests']}`\n"
            f"کل امتیازات: `{stats['total_score']}`\n"
            f"بالاترین امتیاز: `{stats['highest_score']}`\n"
            f"میانگین امتیاز: `{stats['average_score']:.2f}`"
        )
    else:
        response_text = "شما هنوز در هیچ آزمونی شرکت نکرده‌اید. با شرکت در آزمون‌ها، آمار خود را اینجا ببینید!"
    try:
        bot.send_message(user_id, response_text, parse_mode="Markdown")
    except telebot.apihelper.ApiTelegramException as e:
        logger.error(f"Error sending stats to {user_id}: {e}", exc_info=True)
        plain_response_text = response_text.replace("*", "").replace("`", "")
        bot.send_message(user_id, plain_response_text, parse_mode=None)


@bot.message_handler(func=lambda message: message.text == "🏆 جدول امتیازات")
def handle_leaderboard(message):
    user = message.from_user
    add_user(user.id, user.username, user.first_name, user.last_name)
    top_users = get_top_users(limit=10)
    if not top_users:
        bot.send_message(message.chat.id, "هنوز امتیازی در جدول ثبت نشده است. اولین نفر باشید!", parse_mode=None)
        return

    leaderboard_text = "🏆 *جدول ۱۰ کاربر برتر:*\n\n"
    for i, user_stat in enumerate(top_users):
        user_name = escape_markdown(user_stat.get('first_name', 'کاربر ناشناس'))
        score = user_stat.get('total_score', 0)
        leaderboard_text += f"*{i+1}.* {user_name} - `{score}` امتیاز\n"
    try:
        bot.send_message(message.chat.id, leaderboard_text, parse_mode="Markdown")
    except telebot.apihelper.ApiTelegramException as e:
        logger.error(f"Error sending leaderboard to {message.chat.id}: {e}", exc_info=True)
        plain_leaderboard_text = leaderboard_text.replace("*", "").replace("`", "")
        bot.send_message(message.chat.id, plain_leaderboard_text, parse_mode=None)


@bot.message_handler(func=lambda message: message.text == "❓ راهنما")
def handle_help(message):
    user = message.from_user
    add_user(user.id, user.username, user.first_name, user.last_name)
    help_text = (
        "*راهنمای جامع ربات آزمون زبان*\n\n"
        "به ربات ما خوش آمدید! در اینجا نحوه کار با بخش‌های مختلف توضیح داده شده است:\n\n"
        "-----------------------------------\n\n"
        "📝 *آزمون‌ها*\n"
        "1.  *آزمون جامع:* این آزمون سطح کلی شما را با سوالات متنوع می‌سنجد.\n"
        "2.  *آزمون مهارتی:* این آزمون‌ها (مخصوص کاربران ویژه) روی یک مهارت خاص مانند گرامر یا لغت تمرکز دارند.\n\n"
        "⏳ *زمان‌بندی آزمون:*\n"
        "برای هر سوال در آزمون جامع *۴۰ ثانیه* و در آزمون مهارتی *۱ دقیقه* زمان برای پاسخگویی دارید.\n\n"
        "-----------------------------------\n\n"
        "💎 *حساب کاربری ویژه*\n"
        "با ارتقاء به حساب کاربری ویژه، از مزایای زیر بهره‌مند می‌شوید:\n"
        "- شرکت *نامحدود* در تمام آزمون‌ها.\n"
        "- دسترسی کامل به تمام *آزمون‌های مهارتی*.\n"
        "- مشاهده *پاسخ صحیح* پس از جواب دادن به هر سوال.\n\n"
        "-----------------------------------\n\n"
        "✉️ *پشتیبانی*\n"
        "در صورت داشتن هرگونه سوال یا مشکل، از طریق بخش پشتیبانی با ما در تماس باشید.\n\n"
        "📊 *آمار و امتیازات*\n"
        "عملکرد خود را در بخش 'آمار من' پیگیری کنید و جایگاه خود را در 'جدول امتیازات' ببینید."
    )
    try:
        bot.send_message(message.chat.id, help_text, parse_mode="Markdown")
    except telebot.apihelper.ApiTelegramException as e:
        logger.error(f"Error sending help to {message.chat.id}: {e}", exc_info=True)
        plain_help_text = help_text.replace("*", "")
        bot.send_message(message.chat.id, plain_help_text, parse_mode=None)


def start_quiz_logic(user_id, from_user_obj, questions, test_type, level_display_name):
    add_user(user_id, from_user_obj.username, from_user_obj.first_name, from_user_obj.last_name)
    if not questions:
        bot.send_message(user_id, "متاسفم، سوالی برای این آزمون یافت نشد. لطفاً بعداً دوباره تلاش کنید.", parse_mode=None)
        return False

    now = datetime.datetime.now()
    time_per_question = 40 if test_type == 'جامع' else 60
    time_limit_seconds = len(questions) * time_per_question
    deadline = now + datetime.timedelta(seconds=time_limit_seconds)

    quiz_state = {
        'questions': questions, 'current_question_index': 0, 'score': 0,
        'start_time': now, 'deadline': deadline, 'test_type': test_type,
        'level': level_display_name, 'answer_details': []
    }
    save_quiz_state(user_id, quiz_state)

    if user_id in user_quiz_sessions: del user_quiz_sessions[user_id]

    bot.send_message(user_id, "⚠️ *توجه:* پاسخ شما پس از انتخاب قابل ویرایش نیست.", parse_mode='Markdown')
    time.sleep(0.5)
    send_question_to_user(user_id, questions[0])
    return True

@bot.message_handler(func=lambda message: message.text == "📝 آزمون جامع")
def handle_general_quiz(message):
    user = message.from_user
    add_user(user.id, user.username, user.first_name, user.last_name)
    user_id = user.id
    if get_quiz_state(user_id):
        bot.send_message(user_id, "شما یک آزمون نیمه‌کاره دارید. لطفاً ابتدا آن را تمام کنید یا منتظر بمانید تا زمان آن به پایان برسد.", parse_mode=None)
        return

    if not is_user_premium(user_id):
        last_test_time = get_last_test_time(user_id, 'جامع')
        if last_test_time and isinstance(last_test_time, datetime.datetime):
            time_since_last_test = datetime.datetime.now() - last_test_time
            cooldown_seconds = Config.QUIZ_COOLDOWN_HOURS * 3600
            if time_since_last_test.total_seconds() < cooldown_seconds:
                remaining_seconds = cooldown_seconds - time_since_last_test.total_seconds()
                remaining_hours = int(remaining_seconds // 3600)
                remaining_minutes = int((remaining_seconds % 3600) // 60)
                text_md = (
                    f"شما به تازگی در آزمون جامع شرکت کرده‌اید. لطفاً *{remaining_hours}* ساعت و *{remaining_minutes}* دقیقه دیگر دوباره امتحان کنید.\n\n"
                    f"💎 کاربران ویژه محدودیتی برای شرکت در آزمون ندارند."
                )
                bot.send_message(user_id, text_md, parse_mode="Markdown")
                return
    try:
        questions = get_comprehensive_questions(Config.MAX_QUESTIONS)
        start_quiz_logic(user_id, user, questions, 'جامع', 'جامع')
    except Exception as e:
        logger.error(f"Error starting general quiz for user {user_id}: {e}", exc_info=True)
        bot.send_message(user_id, "خطایی در شروع آزمون جامع رخ داد. لطفاً به پشتیبانی اطلاع دهید.", parse_mode=None)

@bot.message_handler(func=lambda message: message.text == "📚 آزمون مهارتی")
def handle_skill_quiz_selection(message):
    user = message.from_user
    add_user(user.id, user.username, user.first_name, user.last_name)
    user_id = user.id
    if not is_user_premium(user_id):
        bot.send_message(user_id, "این بخش مخصوص کاربران ویژه است. با خرید اشتراک به این آزمون‌ها دسترسی پیدا کنید.", parse_mode=None)
        return

    markup = types.InlineKeyboardMarkup(row_width=2)
    skill_buttons = [types.InlineKeyboardButton(skill, callback_data=f"select_level_{skill}") for skill in Config.QUIZ_SKILLS]
    markup.add(*skill_buttons)

    bot.send_message(
        message.chat.id,
        "شما کاربر ویژه هستید! 👍\nلطفاً ابتدا مهارت مورد نظر برای آزمون را انتخاب کنید:",
        reply_markup=markup, parse_mode=None
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('select_level_'))
def handle_level_selection(call):
    user = call.from_user
    add_user(user.id, user.username, user.first_name, user.last_name)
    user_id = user.id
    try:
        skill = call.data.split('_')[2]
        markup = types.InlineKeyboardMarkup(row_width=3)
        level_buttons = [
            types.InlineKeyboardButton(level, callback_data=f"start_skill_quiz_{skill}_{level}")
            for level in Config.QUIZ_LEVELS
        ]
        markup.add(*level_buttons)

        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"عالی! حالا سطح دشواری برای مهارت *{escape_markdown(skill)}* را انتخاب کنید:",
            reply_markup=markup,
            parse_mode="Markdown"
        )
        bot.answer_callback_query(call.id)
    except Exception as e:
        logger.error(f"Error in level selection for skill from callback {call.data}: {e}", exc_info=True)
        bot.answer_callback_query(call.id, "خطا در پردازش انتخاب سطح.", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data.startswith('start_skill_quiz_'))
def handle_skill_quiz_start(call):
    user = call.from_user
    add_user(user.id, user.username, user.first_name, user.last_name)
    user_id = user.id
    if get_quiz_state(user_id):
        bot.answer_callback_query(call.id, "شما یک آزمون دیگر نیمه‌کاره دارید!", show_alert=True)
        return

    try:
        _, _, _, skill, level = call.data.split('_', 4)
        questions = get_questions_by_skill_and_level(skill, level, Config.MAX_QUESTIONS)
        if not questions:
            bot.answer_callback_query(call.id, f"متاسفانه سوالی برای مهارت «{html.escape(skill)}» در سطح «{html.escape(level)}» یافت نشد.", show_alert=True)
            return

        level_display_name = f"{skill} - {level}"
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"آزمون مهارتی *{escape_markdown(skill)}* سطح *{escape_markdown(level)}* در حال آماده‌سازی است...",
            parse_mode="Markdown"
        )
        bot.answer_callback_query(call.id)
        start_quiz_logic(user_id, user, questions, 'مهارتی', level_display_name)

    except Exception as e:
        logger.error(f"Error starting skill quiz from callback {call.data} for user {user_id}: {e}", exc_info=True)
        bot.answer_callback_query(call.id, "خطایی در شروع آزمون مهارتی رخ داد.", show_alert=True)
        try:
            bot.edit_message_text("خطا در شروع آزمون. لطفاً دوباره تلاش کنید.", chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode=None)
        except: pass

def send_question_to_user(user_id, question_data):
    quiz_state = get_quiz_state(user_id)
    if not quiz_state:
        logger.warning(f"Attempted to send question to user {user_id} but no active quiz state found.")
        return

    markup = types.InlineKeyboardMarkup(row_width=1)
    options_list = question_data.get('options')
    if isinstance(options_list, str):
        try: options_list = json.loads(options_list)
        except json.JSONDecodeError: logger.error(f"Failed to parse options JSON for qID {question_data.get('id')} for user {user_id}. Opt: {options_list}"); options_list = []
    if not isinstance(options_list, list): logger.error(f"Options for qID {question_data.get('id')} not a list for user {user_id}. Opt: {options_list}"); options_list = []

    for i, option_text_raw in enumerate(options_list):
        markup.add(types.InlineKeyboardButton(escape_markdown(str(option_text_raw)), callback_data=f"answer_{question_data['id']}_{i}"))

    time_left_str = ""
    if 'deadline' in quiz_state and isinstance(quiz_state['deadline'], datetime.datetime):
        time_left = quiz_state['deadline'] - datetime.datetime.now()
        if time_left.total_seconds() > 0:
            minutes, seconds = divmod(int(time_left.total_seconds()), 60)
            time_left_str = f"⏳ *زمان باقی‌مانده: {minutes} دقیقه و {seconds} ثانیه*\n\n"
        else:
            logger.info(f"Time is up for user {user_id} while trying to send question. Ending quiz.")
            end_quiz(user_id, quiz_state)
            return

    current_q_index = quiz_state.get('current_question_index', 0)
    total_questions_in_quiz = len(quiz_state.get('questions', []))
    question_number_display = f"سوال *{current_q_index + 1}* از *{total_questions_in_quiz}*"

    header = ""
    if quiz_state.get('test_type') == 'جامع':
        header = f"*آزمون جامع* - {question_number_display}"
    else:
        skill_name = escape_markdown(question_data.get('skill', 'مهارتی'))
        level_name = escape_markdown(question_data.get('level', ''))
        header = f"*{skill_name}* (سطح {level_name}) - {question_number_display}"

    question_text_escaped = escape_markdown(question_data.get('question_text', 'متن سوال یافت نشد.'))
    final_text = f"{time_left_str}{header}\n\n{question_text_escaped}"

    sent_message = None
    try:
        media_path_db = question_data.get('media_path')
        media_type = question_data.get('media_type')

        if media_path_db and media_type:
            filename_only = os.path.basename(media_path_db)
            full_disk_path = os.path.join(Config.UPLOAD_FOLDER, filename_only)

            logger.info(f"Attempting to send media DIRECTLY for question {question_data.get('id')}: type={media_type}, disk_path={full_disk_path}")

            if os.path.exists(full_disk_path):
                with open(full_disk_path, 'rb') as media_file_obj:
                    if media_type == 'image':
                        sent_message = bot.send_photo(user_id, photo=media_file_obj, caption=final_text, reply_markup=markup, parse_mode="Markdown")
                    elif media_type == 'audio':
                        sent_message = bot.send_audio(user_id, audio=media_file_obj, caption=final_text, reply_markup=markup, parse_mode="Markdown")
                    elif media_type == 'video':
                        sent_message = bot.send_video(user_id, video=media_file_obj, caption=final_text, reply_markup=markup, parse_mode="Markdown")
                    else:
                        logger.warning(f"Unsupported media type '{media_type}' for direct send. Question {question_data.get('id')}. Sending as text.")
                        sent_message = bot.send_message(user_id, final_text, reply_markup=markup, parse_mode="Markdown")
            else:
                logger.error(f"Media file NOT FOUND at {full_disk_path} for direct send. Question {question_data.get('id')}. Sending as text.")
                sent_message = bot.send_message(user_id, final_text, reply_markup=markup, parse_mode="Markdown")
        else:
            sent_message = bot.send_message(user_id, final_text, reply_markup=markup, parse_mode="Markdown")

        if sent_message:
            user_quiz_sessions[user_id] = sent_message.message_id
        else:
            logger.error(f"sent_message was None after trying to send question (ID: {question_data.get('id')}) to user {user_id}, even after fallbacks.")
            bot.send_message(user_id, "خطایی در نمایش سوال رخ داد. لطفاً دوباره تلاش کنید یا به پشتیبانی اطلاع دهید.", parse_mode=None)

    except telebot.apihelper.ApiTelegramException as e:
        media_info_for_log = f"(direct send attempt, path: {full_disk_path if 'full_disk_path' in locals() else 'N/A'})" if media_path_db and media_type else "(text only send attempt)"
        logger.error(f"API Error sending question ID {question_data.get('id')} to {user_id} {media_info_for_log}: {e}", exc_info=True)
        if "bot was blocked by the user" in str(e).lower():
            logger.warning(f"Bot was blocked by user {user_id}. Cleaning up quiz state.")
            delete_quiz_state(user_id)
        # Fallback for Markdown errors
        plain_final_text = final_text.replace("*", "").replace("`", "").replace("_", "")
        try:
            logger.info(f"Fallback (Markdown error): Sending question ID {question_data.get('id')} as plain text to user {user_id}.")
            sent_message = bot.send_message(user_id, plain_final_text, reply_markup=markup, parse_mode=None)
            if sent_message: user_quiz_sessions[user_id] = sent_message.message_id
        except Exception as fallback_e:
            logger.error(f"Error sending fallback text for question ID {question_data.get('id')} to {user_id}: {fallback_e}", exc_info=True)

    except FileNotFoundError:
        logger.error(f"Media file NOT FOUND at {full_disk_path if 'full_disk_path' in locals() else 'Unknown path'} for direct send. Question {question_data.get('id')}. Fallback to text.")
        plain_final_text = final_text.replace("*", "").replace("`", "").replace("_", "")
        try:
            sent_message = bot.send_message(user_id, plain_final_text, reply_markup=markup, parse_mode=None)
            if sent_message: user_quiz_sessions[user_id] = sent_message.message_id
        except Exception as fallback_e:
            logger.error(f"Error sending fallback text for question ID {question_data.get('id')} after FileNotFoundError: {fallback_e}", exc_info=True)
    except Exception as e:
        media_info_for_log = f"(direct send attempt, path: {full_disk_path if 'full_disk_path' in locals() else 'N/A'})" if media_path_db and media_type else "(text only send attempt)"
        logger.error(f"Unexpected error sending question ID {question_data.get('id')} to {user_id} {media_info_for_log}: {e}", exc_info=True)
        plain_final_text = final_text.replace("*", "").replace("`", "").replace("_", "")
        try:
            logger.info(f"Fallback (unexpected error): Sending question ID {question_data.get('id')} as plain text to user {user_id}.")
            sent_message = bot.send_message(user_id, plain_final_text, reply_markup=markup, parse_mode=None)
            if sent_message: user_quiz_sessions[user_id] = sent_message.message_id
        except Exception as fallback_e:
            logger.error(f"Error sending fallback text for question ID {question_data.get('id')} after unexpected error: {fallback_e}", exc_info=True)


@bot.callback_query_handler(func=lambda call: call.data.startswith('answer_'))
def handle_answer(call):
    user = call.from_user
    add_user(user.id, user.username, user.first_name, user.last_name)
    user_id = user.id
    quiz_state = get_quiz_state(user_id)

    if not quiz_state:
        bot.answer_callback_query(call.id, "متاسفانه آزمون شما یافت نشد یا منقضی شده است.", show_alert=True)
        try:
            # Remove keyboard from the original message
            bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=None)
        except telebot.apihelper.ApiTelegramException as e:
            logger.warning(f"Could not remove reply markup from expired quiz message for user {user_id}: {e}")
        return

    if 'deadline' in quiz_state and isinstance(quiz_state['deadline'], datetime.datetime) and datetime.datetime.now() > quiz_state['deadline']:
        bot.answer_callback_query(call.id)
        bot.send_message(user_id, "⏰ زمان آزمون شما به پایان رسیده است!", parse_mode=None)
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

    if question_id_answered != current_question.get('id'):
        bot.answer_callback_query(call.id, "این سوال قبلاً پاسخ داده شده یا سوال دیگری فعال است.", show_alert=True)
        return

    is_correct = (chosen_option_index == current_question.get('correct_answer'))
    if is_correct: quiz_state['score'] += 1

    if quiz_state.get('test_type') == 'جامع':
        if 'answer_details' not in quiz_state or not isinstance(quiz_state['answer_details'], list):
            quiz_state['answer_details'] = []
        quiz_state['answer_details'].append({
            'question_id': current_question.get('id'), 'skill': current_question.get('skill'),
            'level': current_question.get('level'), 'correct': is_correct,
            'chosen_option': chosen_option_index
        })

    is_premium_user = is_user_premium(user_id)
    options_list_for_feedback = current_question.get('options', [])
    if isinstance(options_list_for_feedback, str):
        try: options_list_for_feedback = json.loads(options_list_for_feedback)
        except: options_list_for_feedback = []
    if not isinstance(options_list_for_feedback, list): options_list_for_feedback = []

    # --- New logic: Remove keyboard from original message, send feedback as new message ---
    try:
        bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=None)
    except telebot.apihelper.ApiTelegramException as e:
        # This might happen if the message was media and edit_message_text was (incorrectly) used before
        logger.warning(f"Could not remove reply markup from message {call.message.message_id} for user {user_id}. Error: {e}")
        # If it's media, try to edit caption's reply markup
        if call.message.caption:
             try:
                bot.edit_message_caption(chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=None)
             except telebot.apihelper.ApiTelegramException as e_caption:
                logger.warning(f"Could not remove reply markup from media caption for user {user_id}. Error: {e_caption}")


    feedback_text = ""
    feedback_parse_mode = None

    if is_premium_user:
        feedback_text = "✅ *پاسخ صحیح*" if is_correct else "❌ *پاسخ شما اشتباه بود*"
        correct_answer_idx = current_question.get('correct_answer')
        if correct_answer_idx is not None and 0 <= correct_answer_idx < len(options_list_for_feedback):
            correct_answer_text_raw = str(options_list_for_feedback[correct_answer_idx])
            feedback_text += f"\nپاسخ صحیح: *{escape_markdown(correct_answer_text_raw)}*"

        # Show chosen option with indicator
        chosen_option_text_raw = str(options_list_for_feedback[chosen_option_index])
        chosen_indicator = "✅" if is_correct else "❌"
        feedback_text += f"\nپاسخ شما: {chosen_indicator} *{escape_markdown(chosen_option_text_raw)}*"
        feedback_parse_mode = "Markdown"
    else: # کاربر عادی
        feedback_text = "پاسخ شما ثبت شد."
        feedback_parse_mode = None

    try:
        bot.send_message(user_id, feedback_text, parse_mode=feedback_parse_mode)
    except telebot.apihelper.ApiTelegramException as e_fb:
        logger.error(f"Error sending feedback message to user {user_id}: {e_fb}", exc_info=True)
        if feedback_parse_mode == "Markdown": # Try plain text fallback
            plain_feedback_text = feedback_text.replace("*", "").replace("`", "")
            try:
                bot.send_message(user_id, plain_feedback_text, parse_mode=None)
            except Exception as e_fb_plain:
                 logger.error(f"Error sending plain text feedback to user {user_id}: {e_fb_plain}", exc_info=True)
    # --- End of new logic for feedback ---

    bot.answer_callback_query(call.id)
    quiz_state['current_question_index'] += 1
    save_quiz_state(user_id, quiz_state)

    if quiz_state['current_question_index'] < len(quiz_state['questions']):
        time.sleep(1 if is_premium_user else 0.5)
        send_question_to_user(user_id, quiz_state['questions'][quiz_state['current_question_index']])
    else:
        logger.info(f"All questions answered for user {user_id}. Ending quiz.")
        end_quiz(user_id, quiz_state)

def get_level_from_percentage(percentage):
    percentage = max(0, min(100, percentage))
    if percentage <= 20: return "A1.1"
    elif percentage <= 35: return "A1.2"
    elif percentage <= 52: return "A2.1"
    elif percentage <= 62: return "A2.2"
    elif percentage <= 75: return "B1"
    elif percentage <= 90: return "B2"
    else: return "C1/C2"

def end_quiz(user_id, quiz_state):
    if not quiz_state:
        logger.error(f"end_quiz called for user {user_id} with no quiz_state.")
        delete_quiz_state(user_id)
        send_main_keyboard(user_id, "خطایی در پایان آزمون رخ داد.")
        return

    total_questions = len(quiz_state.get('questions', []))
    score = quiz_state.get('score', 0)
    start_time = quiz_state.get('start_time')
    if isinstance(start_time, str):
        try: start_time = datetime.datetime.fromisoformat(start_time)
        except ValueError: start_time = datetime.datetime.now(); logger.warning(f"Could not parse start_time string for user {user_id}, using current time.")
    elif not isinstance(start_time, datetime.datetime): start_time = datetime.datetime.now(); logger.warning(f"Invalid start_time type for user {user_id}, using current time.")

    duration = datetime.datetime.now() - start_time
    minutes, seconds = divmod(int(duration.total_seconds()), 60)

    try:
        save_test_result(user_id, score, quiz_state.get('level', 'N/A'), quiz_state.get('test_type', 'N/A'))
    except Exception as e:
        logger.error(f"Failed to save test result for user {user_id}: {e}", exc_info=True)

    percentage = round((score / total_questions) * 100) if total_questions > 0 else 0
    user_level_determined = get_level_from_percentage(percentage)

    summary_text_md = (f"🎉 *آزمون شما به پایان رسید!*\n\n"
                             f"تعداد سوالات: `{total_questions}`\n"
                             f"پاسخ‌های صحیح: `{score}`\n"
                             f"درصد موفقیت: *{percentage}%*\n"
                             f"سطح تقریبی شما: *{escape_markdown(user_level_determined)}*\n"
                             f"مدت زمان آزمون: *{minutes} دقیقه و {seconds} ثانیه*")

    if quiz_state.get('test_type') == 'جامع' and 'answer_details' in quiz_state and quiz_state['answer_details']:
        analysis_text_md = "\n\n📊 *تحلیل عملکرد شما بر اساس مهارت (در آزمون جامع):*\n"
        skill_stats = {skill: {"correct": 0, "total": 0} for skill in Config.QUIZ_SKILLS}

        for detail in quiz_state['answer_details']:
            skill = detail.get('skill', '').strip()
            if skill and skill in skill_stats:
                skill_stats[skill]['total'] += 1
                if detail.get('correct'): skill_stats[skill]['correct'] += 1

        performance_lines = []
        for skill_name, data in skill_stats.items():
            if data['total'] > 0:
                skill_percentage = round((data['correct'] / data['total']) * 100)
                performance_lines.append(f"- *{escape_markdown(skill_name)}*: {skill_percentage}% ({data['correct']} از {data['total']})")

        if performance_lines:
            summary_text_md += analysis_text_md + "\n".join(performance_lines)

    try:
        bot.send_message(user_id, summary_text_md, parse_mode="Markdown")
    except telebot.apihelper.ApiTelegramException as e:
        logger.error(f"Error sending quiz summary to {user_id} (Markdown): {e}", exc_info=True)
        plain_summary_text = summary_text_md.replace("*", "").replace("`", "")
        bot.send_message(user_id, plain_summary_text, parse_mode=None)


    suggestion_text_md = ""
    if percentage <= 35:
        suggestion_text_md = "برای تقویت پایه زبان خود، پیشنهاد می‌کنیم در دوره‌های آموزشی سطح مقدماتی (A1/A2) ما شرکت کنید یا منابع مرتبط را مطالعه نمایید."
    elif percentage <= 75:
        suggestion_text_md = "عملکرد خوبی داشتید! برای رسیدن به سطوح بالاتر، تمرین مستمر روی مهارت‌های مختلف را فراموش نکنید."
    if suggestion_text_md:
        try:
            # This is a static message, ensure it's Markdown V1 compatible or send as plain.
            # For now, assuming it's simple enough for V1.
            bot.send_message(user_id, suggestion_text_md, parse_mode="Markdown")
        except telebot.apihelper.ApiTelegramException as e:
             logger.error(f"Error sending suggestion to {user_id} (Markdown): {e}", exc_info=True)
             bot.send_message(user_id, suggestion_text_md.replace("*",""), parse_mode=None)


    delete_quiz_state(user_id)
    if user_id in user_quiz_sessions:
        del user_quiz_sessions[user_id]

    send_main_keyboard(user_id, "آزمون به پایان رسید. برای شروع مجدد یا سایر گزینه‌ها، از منوی اصلی استفاده کنید.")

# --- بخش ۴: پشتیبانی و سایر موارد ---
@bot.message_handler(func=lambda message: message.text == "✉️ پشتیبانی")
def handle_support_request(message):
    user = message.from_user
    add_user(user.id, user.username, user.first_name, user.last_name)
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
        reply_markup=markup, parse_mode=None
    )

@bot.message_handler(func=lambda message: message.text == "↪️ انصراف از ارسال پیام")
def handle_cancel_support(message):
    user_id = message.chat.id
    if user_id in support_sessions:
        del support_sessions[user_id]
        logger.info(f"Support session cancelled by user {user_id}.")
    bot.send_message(user_id, "ارسال پیام به پشتیبانی لغو شد.", parse_mode=None)
    send_main_keyboard(user_id)

def forward_support_message_to_admins(user_id, first_name, username, message_id_to_forward=None, text_content=None, media_path_for_admin_info=None):
    user_display_plain = f"{first_name or ''} (@{username or 'N/A'}, ID: {user_id})"
    admin_notification_text = f"یک پیام پشتیبانی جدید از کاربر {user_display_plain} دریافت شد."

    if media_path_for_admin_info:
        panel_url = f"{Config.REPLIT_APP_URL.strip('/')}/support_messages"
        admin_notification_text += f"\nنوع: تصویر/رسانه. برای مشاهده به پنل ادمین ({panel_url}) مراجعه کنید."

    for admin_id in Config.ADMIN_IDS:
        try:
            logger.info(f"Admin Supp Msg (Plain Text): {admin_notification_text}")
            bot.send_message(admin_id, admin_notification_text, parse_mode=None)
            if message_id_to_forward and not media_path_for_admin_info:
                bot.forward_message(admin_id, user_id, message_id_to_forward)
        except telebot.apihelper.ApiTelegramException as e:
            logger.error(f"Failed to send plain text support notification to admin {admin_id} for user {user_id}: {e}", exc_info=True)
        except Exception as e_gen:
             logger.error(f"General error in forward_support_message_to_admins for admin {admin_id}: {e_gen}", exc_info=True)

@bot.message_handler(content_types=['text'], func=lambda message: support_sessions.get(message.chat.id, {}).get('stage') == 'awaiting_message')
def handle_support_message_text(message):
    user = message.from_user
    add_user(user.id, user.username, user.first_name, user.last_name)
    user_id = user.id

    if message.text == "↪️ انصراف از ارسال پیام":
        handle_cancel_support(message)
        return

    try:
        save_support_message(user_id, message.text)
        logger.info(f"Support text message from {user_id} saved.")
        forward_support_message_to_admins(user_id, user.first_name, user.username, message_id_to_forward=message.message_id)
        bot.send_message(user_id, "پیام شما با موفقیت برای تیم پشتیبانی ارسال شد. منتظر پاسخ ما باشید.", parse_mode=None)
    except Exception as e:
        logger.error(f"Error handling support text from {user_id}: {e}", exc_info=True)
        bot.send_message(user_id, "متاسفانه در ارسال پیام شما به پشتیبانی خطایی رخ داد. لطفاً دوباره تلاش کنید.", parse_mode=None)
    finally:
        if user_id in support_sessions:
            del support_sessions[user_id]
        send_main_keyboard(user_id)

@bot.message_handler(content_types=['photo'], func=lambda message: support_sessions.get(message.chat.id, {}).get('stage') == 'awaiting_message')
def handle_support_photo(message):
    user = message.from_user
    add_user(user.id, user.username, user.first_name, user.last_name)
    user_id = user.id
    try:
        photo_file_id = message.photo[-1].file_id
        file_info = bot.get_file(photo_file_id)
        downloaded_file = bot.download_file(file_info.file_path)

        if not os.path.exists(Config.UPLOAD_FOLDER):
            os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)

        unique_filename = f"support_photo_{user_id}_{int(time.time())}.jpg"
        save_path_on_disk = os.path.join(Config.UPLOAD_FOLDER, unique_filename)

        with open(save_path_on_disk, 'wb') as new_file:
            new_file.write(downloaded_file)

        media_path_for_db = os.path.join('media', unique_filename)
        caption_text = message.caption if message.caption else "تصویر ارسالی (بدون متن)"

        save_support_message(user_id, caption_text, media_path_for_db)
        logger.info(f"Support photo from {user_id} saved to {save_path_on_disk}, DB path: {media_path_for_db}.")
        forward_support_message_to_admins(user_id, user.first_name, user.username, media_path_for_admin_info=media_path_for_db)
        bot.send_message(user_id, "تصویر شما همراه با متن (در صورت وجود) با موفقیت برای پشتیبانی ارسال شد.", parse_mode=None)
    except Exception as e:
        logger.error(f"Error handling support photo from {user_id}: {e}", exc_info=True)
        bot.send_message(user_id, "متاسفانه در ارسال تصویر شما به پشتیبانی خطایی رخ داد. لطفاً دوباره تلاش کنید.", parse_mode=None)
    finally:
        if user_id in support_sessions:
            del support_sessions[user_id]
        send_main_keyboard(user_id)

@bot.message_handler(content_types=['audio', 'video', 'document', 'sticker', 'voice', 'location', 'contact'],
                     func=lambda message: support_sessions.get(message.chat.id, {}).get('stage') == 'awaiting_message')
def handle_unsupported_support_content(message):
    user_id = message.chat.id
    bot.send_message(user_id, "در حال حاضر فقط امکان ارسال پیام متنی یا عکس به پشتیبانی وجود دارد. لطفاً پیام خود را به صورت متنی یا عکس ارسال کنید، یا عملیات را لغو نمایید.", parse_mode=None)

@bot.message_handler(commands=['admin'])
def admin_panel_command(message):
    user = message.from_user
    add_user(user.id, user.username, user.first_name, user.last_name)
    user_id = user.id
    if user_id in Config.ADMIN_IDS:
        panel_url = Config.REPLIT_APP_URL.strip('/') + "/dashboard" if Config.REPLIT_APP_URL else "پنل ادمین (URL not configured)"
        bot.send_message(user_id, f"به پنل ادمین خوش آمدید!\nلینک پنل: {panel_url}", parse_mode=None)
    else:
        logger.info(f"Non-admin user {user_id} tried to use /admin command.")

def send_admin_response_to_user(user_telegram_id, admin_response_text):
    try:
        # Admin might use Markdown, so we try to send as Markdown (V1)
        # We assume admin is aware or we escape it.
        # For now, we will escape it to prevent errors from admin input.
        escaped_response = escape_markdown(admin_response_text)
        bot.send_message(user_telegram_id,
                         f"✉️ *پاسخ از طرف پشتیبانی:*\n\n{escaped_response}",
                         parse_mode='Markdown')
        logger.info(f"Admin response sent to user {user_telegram_id}.")
        return True
    except telebot.apihelper.ApiTelegramException as e:
        logger.error(f"Failed to send Markdown admin response to user {user_telegram_id}: {e}", exc_info=True)
        try:
            bot.send_message(user_telegram_id, f"پاسخ از طرف پشتیبانی:\n\n{admin_response_text}", parse_mode=None)
            logger.info(f"Fallback: Admin response sent as plain text to user {user_telegram_id}.")
            return True
        except Exception as fallback_e:
            logger.error(f"Failed to send fallback plain text admin response to user {user_telegram_id}: {fallback_e}", exc_info=True)
            return False
    except Exception as e:
        logger.error(f"Unexpected error sending admin response to user {user_telegram_id}: {e}", exc_info=True)
        return False

def send_payment_confirmation(user_id, duration_days, amount_paid=None, currency="تومان"):
    try:
        text_md = f"✅ اشتراک ویژه شما با موفقیت فعال شد!\n"
        if amount_paid:
             text_md += f"مبلغ دریافتی: `{amount_paid:,}` {escape_markdown(currency)}.\n"
        text_md += f"مدت اعتبار: *{duration_days}* روز."

        bot.send_message(user_id, text_md, parse_mode='Markdown')
        send_main_keyboard(user_id, "اشتراک شما فعال شد! از امکانات ویژه لذت ببرید.")
        logger.info(f"Manual payment confirmation sent to user {user_id} for {duration_days} days.")
        return True
    except telebot.apihelper.ApiTelegramException as e:
        logger.error(f"Failed to send payment confirmation (Markdown) to {user_id}: {e}", exc_info=True)
        plain_text = f"✅ اشتراک ویژه شما با موفقیت فعال شد!\n"
        if amount_paid: plain_text += f"مبلغ دریافتی: {amount_paid:,} {currency}.\n"
        plain_text += f"مدت اعتبار: {duration_days} روز."
        try:
            bot.send_message(user_id, plain_text, parse_mode=None)
            send_main_keyboard(user_id, "اشتراک شما فعال شد! از امکانات ویژه لذت ببرید.")
            logger.info(f"Fallback: Payment confirmation sent as plain text to user {user_id}.")
            return True
        except Exception as fallback_e:
            logger.error(f"Failed to send fallback plain text payment confirmation to {user_id}: {fallback_e}", exc_info=True)
            return False
    except Exception as e:
        logger.error(f"Unexpected error sending payment confirmation to {user_id}: {e}", exc_info=True)
        return False

logger.info("Bot instance (bot.py) created and handlers configured.")
