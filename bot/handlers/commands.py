from datetime import datetime
from typing import Optional

import pytz
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from bot.database.db import get_or_create_user, get_user_pending_reminders
from bot.formatting import full_due_str

HELP_TEXT = (
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

MENU_KEYBOARD = InlineKeyboardMarkup(
    [
        [
            InlineKeyboardButton("📖 راهنمای زمان‌ها", callback_data="show_help"),
            InlineKeyboardButton("📋 یادآوری‌های فعال", callback_data="show_list"),
        ]
    ]
)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends welcome message and usage instructions."""
    user = update.effective_user
    chat = update.effective_chat
    if not user or not chat:
        return

    await get_or_create_user(user.id, chat.id)

    welcome_text = (
        f"سلام {user.first_name or 'دوست من'} عزیز! 👋\n"
        "من **Do It** هستم؛ دستیار یادآوری تو. 🎯\n\n"
        "قسمت کارت و زمانش رو برام بنویس، من سرِ وقت یادت می‌ندازم:\n"
        "▫️ `فردا ساعت ۶ برم دکتر`\n"
        "▫️ `ورزش + هر روز ۷ صبح`\n"
        "▫️ `چک کردن فر + ۱۰ دقیقه دیگه`\n\n"
        "دستورات و همه فرمت‌های زمانی رو با دکمه‌های پایین ببین. 👇"
    )

    await update.message.reply_text(welcome_text, parse_mode="Markdown", reply_markup=MENU_KEYBOARD)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends detailed help and cheatsheet."""
    await update.message.reply_text(HELP_TEXT, parse_mode="Markdown")


async def build_active_reminders_view(user_id: int, chat_id: int) -> tuple[str, Optional[InlineKeyboardMarkup]]:
    """Builds the /list text and cancel keyboard for a chat's user."""
    db_user = await get_or_create_user(user_id, chat_id)
    tz = pytz.timezone(db_user.timezone)

    reminders = await get_user_pending_reminders(user_id)
    if not reminders:
        return (
            "📭 شما در حال حاضر هیچ یادآوری فعالی ندارید.\nبرای افزودن یادآوری کافیست پیام خود را بفرستید!\n\n"
            "سعی کنید:\n▫️ `خرید شیر + فردا ۹ صبح`",
            menu_reply_keyboard(),
        )

    recurrence_map = {
        "daily": "روزانه",
        "weekly": "هفتگی",
        "even_days": "روزهای زوج",
        "odd_days": "روزهای فرد",
        "monthly": "ماهانه",
    }

    now_local = datetime.now(pytz.UTC).astimezone(tz)
    text = f"📋 **لیست یادآوری‌های فعال شما ({len(reminders)} مورد):**\n\n"
    keyboard: list[list[InlineKeyboardButton]] = []

    for idx, rem in enumerate(reminders, 1):
        local_dt = rem.remind_at_utc.astimezone(tz)

        rec_str = ""
        if rem.recurrence_type != "none":
            rec_str = f" [🔄 {recurrence_map.get(rem.recurrence_type, 'دوره‌ای')}]"

        text += f"{idx}. 📌 **{rem.task_text}**{rec_str}\n   ⏰ {full_due_str(local_dt, now_local)}\n\n"

        keyboard.append(
            [InlineKeyboardButton(f"❌ لغو #{rem.id}: {rem.task_text[:18]}", callback_data=f"cancel_{rem.id}")]
        )

    keyboard.append([InlineKeyboardButton("🔄 بروزرسانی", callback_data="show_list")])
    return text, InlineKeyboardMarkup(keyboard)


def menu_reply_keyboard() -> InlineKeyboardMarkup:
    """Menu shown together with the reminders list."""
    return MENU_KEYBOARD


async def list_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Lists user's active upcoming reminders."""
    user = update.effective_user
    chat = update.effective_chat
    if not user or not chat:
        return

    await get_or_create_user(user.id, chat.id)
    text, reply_markup = await build_active_reminders_view(user.id, chat.id)
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=reply_markup)
