import jdatetime
import pytz
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from bot.database.db import get_or_create_user, get_user_pending_reminders


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends welcome message and usage instructions."""
    user = update.effective_user
    chat = update.effective_chat
    if not user or not chat:
        return

    await get_or_create_user(user.id, chat.id)

    welcome_text = (
        f"سلام {user.first_name or 'دوست من'} عزیز! 👋\n"
        "به ربات **Do It (انجامش بده)** خوش آمدید 🎯\n\n"
        "من دستیار یادآوری هوشمند شما هستم. کافیست کار مورد نظرتان را همراه با زمان برایم بفرستید تا در موعد مقرر دقیقاً به شما یادآوری کنم.\n\n"
        "📝 **فرمت دلخواه (با یا بدون +):**\n"
        "▫️ `خرید نان + ساعت ۷ عصر`\n"
        "▫️ `فردا ساعت ۶ برم دکتر`\n"
        "▫️ `ساعت ۱۰ شب به مامان زنگ بزن`\n"
        "▫️ `ورزش + هر روز ۷ صبح`\n"
        "▫️ `استخر + پنج شنبه ۷ بعد از ظهر`\n"
        "▫️ `جلسه کاری + ۲۵ مهر ماه`\n"
        "▫️ `25 October ساعت ۴ بعد از ظهر ارسال ایمیل`\n"
        "▫️ `چک کردن فر + ۱۰ دقیقه دیگه`\n"
        "▫️ `کلاس زبان + روزهای زوج ساعت ۵ عصر`\n\n"
        "📋 **دستورات کمکی:**\n"
        "/list - مشاهده یادآوری‌های فعال\n"
        "/help - راهنمای کامل عبارات زمانی"
    )

    await update.message.reply_text(welcome_text, parse_mode="Markdown")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends detailed help and cheatsheet."""
    help_text = (
        "💡 **راهنمای جامع ربات Do It (انجامش بده)**\n\n"
        "شما می‌توانید زمان را به شکل‌های کاملاً طبیعی، جلالی (شمسی)، میلادی یا نسبی بنویسید:\n\n"
        "🔹 **ساعت‌های شبانه‌روز:**\n"
        "• `ساعت ۷ عصر` / `۷ بعد از ظهر` (19:00)\n"
        "• `۸ صبح` (08:00)\n"
        "• `۱۲ ظهر` (12:00) / `۱۲ شب` (00:00)\n"
        "• `ساعت ۷ و نیم شب` (19:30)\n\n"
        "🔹 **روزها و روزهای هفته:**\n"
        "• `فردا ساعت ۶`\n"
        "• `پس فردا ساعت ۱۰ صبح`\n"
        "• `پنج شنبه ۷ بعد از ظهر`\n"
        "• `این شنبه ساعت ۹`\n\n"
        "🔹 **تقویم شمسی (جلالی):**\n"
        "• `۲۵ مهر ماه`\n"
        "• `۲۵ مهر ساعت ۴ بعد از ظهر`\n"
        "• `اول آبان ساعت ۱۰`\n"
        "• `۱۴۰۵/۰۷/۲۵ ساعت ۱۵:۳۰`\n\n"
        "🔹 **تقویم میلادی:**\n"
        "• `25 October ساعت ۱۶`\n"
        "• `15 November send report`\n"
        "• `۲۵ اکتبر ساعت ۴ بعد از ظهر`\n"
        "• `2026-10-25 10:00`\n\n"
        "🔹 **تکرارشونده و دوره‌ای:**\n"
        "• `هر روز ۷ صبح`\n"
        "• `هر هفته پنج شنبه ۸ شب`\n"
        "• `روزهای زوج ساعت ۵ عصر` (شنبه، دوشنبه، چهارشنبه)\n"
        "• `روزهای فرد ساعت ۵ عصر` (یکشنبه، سه‌شنبه، پنج‌شنبه)\n"
        "• `هر ماه ۲۵ ام ساعت ۹ صبح`\n\n"
        "🔹 **زمان‌های نسبی:**\n"
        "• `۱۰ دقیقه دیگه`\n"
        "• `نیم ساعت دیگه`\n"
        "• `یک ربع دیگه`\n"
        "• `۲ ساعت بعد`\n"
        "• `۳ روز دیگه`\n\n"
        "📌 همواره می‌توانید با ارسال پیام ساده مانند `خرید شیر + فردا ۹ صبح` یا `فردا ۹ صبح خرید شیر` یادآوری بسازید."
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")


async def list_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Lists user's active upcoming reminders."""
    user = update.effective_user
    chat = update.effective_chat
    if not user or not chat:
        return

    db_user = await get_or_create_user(user.id, chat.id)
    tz = pytz.timezone(db_user.timezone)

    reminders = await get_user_pending_reminders(user.id)
    if not reminders:
        await update.message.reply_text(
            "📭 شما در حال حاضر هیچ یادآوری فعالی ندارید.\nبرای افزودن یادآوری کافیست پیام خود را بفرستید!",
            parse_mode="Markdown",
        )
        return

    recurrence_map = {
        "daily": "روزانه",
        "weekly": "هفتگی",
        "even_days": "روزهای زوج",
        "odd_days": "روزهای فرد",
        "monthly": "ماهانه",
    }

    text = f"📋 **لیست یادآوری‌های فعال شما ({len(reminders)} مورد):**\n\n"

    for idx, rem in enumerate(reminders, 1):
        local_dt = rem.remind_at_utc.astimezone(tz)
        jdt = jdatetime.datetime.fromgregorian(datetime=local_dt)
        time_str = f"{jdt.strftime('%Y/%m/%d %H:%M')} ({local_dt.strftime('%Y-%m-%d %H:%M')})"

        rec_str = ""
        if rem.recurrence_type != "none":
            rec_str = f" [🔄 {recurrence_map.get(rem.recurrence_type, 'دوره‌ای')}]"

        text += f"{idx}. 📌 **{rem.task_text}**{rec_str}\n   ⏰ موعد: `{time_str}`\n\n"

    keyboard = [
        [InlineKeyboardButton(f"❌ لغو #{rem.id}: {rem.task_text[:18]}", callback_data=f"cancel_{rem.id}")]
        for rem in reminders[:10]  # Show inline cancel buttons for up to 10 items
    ]

    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=reply_markup)
