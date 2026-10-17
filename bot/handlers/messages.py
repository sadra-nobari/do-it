import pytz
from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from bot.database.db import create_reminder, get_or_create_user
from bot.formatting import full_due_str
from bot.parser.time_parser import parse_reminder
from bot.scheduler.job_manager import schedule_reminder_job


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Processes incoming text messages and creates reminders."""
    message = update.message
    user = update.effective_user
    chat = update.effective_chat
    if not message or not message.text or not user or not chat:
        return

    text = message.text.strip()
    if not text:
        return

    # Fetch user preferences
    db_user = await get_or_create_user(user.id, chat.id)
    tz_name = db_user.timezone or "Asia/Tehran"
    tz = pytz.timezone(tz_name)

    # Parse user message
    result = parse_reminder(text, tz_name=tz_name)

    # Save to SQLite database
    reminder = await create_reminder(
        user_id=user.id,
        chat_id=chat.id,
        task_text=result.task,
        remind_at_utc=result.remind_at_utc,
        recurrence_type=result.recurrence_type,
        recurrence_rule=result.recurrence_rule,
        calendar_type=result.calendar_type,
        original_time_expr=result.original_time_expr,
    )

    # Schedule in JobQueue
    schedule_reminder_job(context.application.job_queue, reminder.id, result.remind_at_utc)

    # Format response
    local_dt = result.remind_at.astimezone(tz)
    now_local = datetime.now(pytz.UTC).astimezone(tz)
    due_str = full_due_str(local_dt, now_local)

    recurrence_map = {
        "daily": "هر روز",
        "weekly": "هر هفته",
        "even_days": "روزهای زوج (شنبه، دوشنبه، چهارشنبه)",
        "odd_days": "روزهای فرد (یکشنبه، سه‌شنبه، پنج‌شنبه)",
        "monthly": "ماهانه",
    }

    rec_line = ""
    if result.recurrence_type != "none":
        rec_line = f"\n🔄 **تکرار:** {recurrence_map.get(result.recurrence_type, 'دوره‌ای')}"

    warning_line = ""
    if result.is_past_warning:
        warning_line = (
            "\n\n⚠️ *توجه: ساعت واردشده برای امروز سپری شده است؛ به همین دلیل نزدیک‌ترین موعد پیش‌رو تنظیم شد.*"
        )

    response_text = (
        f"✅ **یادآوری با موفقیت تنظیم شد!**\n\n"
        f"📌 **کار:** {result.task}\n"
        f"⏰ **موعد:** {due_str}"
        f"{rec_line}"
        f"{warning_line}"
    )

    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("❌ لغو این یادآوری", callback_data=f"cancel_{reminder.id}")]]
    )

    await message.reply_text(response_text, parse_mode="Markdown", reply_markup=keyboard)
