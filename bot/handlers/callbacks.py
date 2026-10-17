from datetime import datetime, timedelta
import jdatetime
import pytz
from telegram import Update
from telegram.ext import ContextTypes

from bot.database.db import (
    get_or_create_user,
    get_reminder,
    update_reminder_status,
    update_reminder_time,
)
from bot.database.models import ReminderStatus
from bot.scheduler.job_manager import schedule_reminder_job


async def callback_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles inline keyboard button clicks for reminders."""
    query = update.callback_query
    if not query or not query.data:
        return

    await query.answer()
    data = query.data

    # 1. Action: Done
    if data.startswith("done_"):
        reminder_id = int(data.split("_")[1])
        reminder = await get_reminder(reminder_id)
        if reminder:
            await update_reminder_status(reminder_id, ReminderStatus.COMPLETED)
            task_title = reminder.task_text
            await query.edit_message_text(
                f"🎉 **آفرین! انجام شد:**\n\n📌 ~~{task_title}~~",
                parse_mode="Markdown",
            )
        return

    # 2. Action: Snooze
    if data.startswith("snooze_"):
        parts = data.split("_")
        reminder_id = int(parts[1])
        minutes = int(parts[2])

        reminder = await get_reminder(reminder_id)
        if not reminder:
            await query.edit_message_text("❌ یادآوری مورد نظر یافت نشد.")
            return

        user = await get_or_create_user(reminder.user_id, reminder.chat_id)
        tz = pytz.timezone(user.timezone)

        new_utc = datetime.now(pytz.UTC) + timedelta(minutes=minutes)
        await update_reminder_time(reminder_id, new_utc)

        # Reschedule in JobQueue
        schedule_reminder_job(context.application.job_queue, reminder_id, new_utc)

        new_local = new_utc.astimezone(tz)
        jdt = jdatetime.datetime.fromgregorian(datetime=new_local)
        time_str = f"{jdt.strftime('%H:%M')} ({new_local.strftime('%H:%M')})"

        snooze_label = (
            f"{minutes} دقیقه"
            if minutes < 60
            else f"{minutes // 60} ساعت"
            if minutes < 1440
            else "فردا همین ساعت"
        )

        await query.edit_message_text(
            f"⏰ **یادآوری به تعویق افتاد!**\n\n"
            f"📌 **{reminder.task_text}**\n"
            f"⏳ تعویق: `{snooze_label}`\n"
            f"⏰ موعد جدید: ساعت `{time_str}`",
            parse_mode="Markdown",
        )
        return

    # 3. Action: Cancel
    if data.startswith("cancel_"):
        reminder_id = int(data.split("_")[1])
        reminder = await get_reminder(reminder_id)
        if reminder:
            await update_reminder_status(reminder_id, ReminderStatus.CANCELLED)
            # Remove from job queue
            if context.application.job_queue:
                jobs = context.application.job_queue.get_jobs_by_name(f"reminder_{reminder_id}")
                for j in jobs:
                    j.schedule_removal()

            await query.edit_message_text(
                f"🗑 **یادآوری لغو شد:**\n\n📌 ~~{reminder.task_text}~~",
                parse_mode="Markdown",
            )
        return
