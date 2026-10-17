import logging
from datetime import datetime, time, timedelta
from typing import Optional
import jdatetime
import pytz
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.config import DEFAULT_TIMEZONE
from bot.database.db import (
    get_all_pending_reminders,
    get_or_create_user,
    get_reminder,
    update_reminder_status,
    update_reminder_time,
)
from bot.database.models import Reminder, ReminderStatus
from bot.parser.time_parser import find_next_weekday_occurrence

logger = logging.getLogger(__name__)


def build_reminder_keyboard(reminder_id: int) -> InlineKeyboardMarkup:
    """Creates inline action buttons for a triggered reminder."""
    keyboard = [
        [InlineKeyboardButton("✅ انجام شد", callback_data=f"done_{reminder_id}")],
        [
            InlineKeyboardButton("⏰ ۵ دقیقه بعد", callback_data=f"snooze_{reminder_id}_5"),
            InlineKeyboardButton("⏰ ۱۵ دقیقه بعد", callback_data=f"snooze_{reminder_id}_15"),
        ],
        [
            InlineKeyboardButton("⏰ ۱ ساعت بعد", callback_data=f"snooze_{reminder_id}_60"),
            InlineKeyboardButton("⏰ فردا همین ساعت", callback_data=f"snooze_{reminder_id}_1440"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def calculate_next_occurrence(reminder: Reminder, now: Optional[datetime] = None) -> Optional[datetime]:
    """
    Calculates the next occurrence for recurring reminders.
    Returns UTC datetime, or None if reminder is one-off.
    """
    if reminder.recurrence_type == "none":
        return None

    tz = pytz.timezone(DEFAULT_TIMEZONE)
    if now is None:
        now = datetime.now(pytz.UTC)

    now_local = now.astimezone(tz)
    rule = reminder.recurrence_rule or {}
    target_hour = rule.get("hour", 9)
    target_minute = rule.get("minute", 0)
    target_time = time(target_hour, target_minute)

    if reminder.recurrence_type == "daily":
        next_local = tz.localize(datetime.combine(now_local.date() + timedelta(days=1), target_time))
        return next_local.astimezone(pytz.UTC)

    if reminder.recurrence_type == "even_days":
        even_weekdays = [5, 0, 2]  # Sat, Mon, Wed
        next_local = find_next_weekday_occurrence(now_local, even_weekdays, target_time, tz)
        return next_local.astimezone(pytz.UTC)

    if reminder.recurrence_type == "odd_days":
        odd_weekdays = [6, 1, 3]  # Sun, Tue, Thu
        next_local = find_next_weekday_occurrence(now_local, odd_weekdays, target_time, tz)
        return next_local.astimezone(pytz.UTC)

    if reminder.recurrence_type == "weekly":
        weekday = rule.get("weekday", now_local.weekday())
        next_local = find_next_weekday_occurrence(now_local, [weekday], target_time, tz)
        return next_local.astimezone(pytz.UTC)

    if reminder.recurrence_type == "monthly":
        target_day = rule.get("day", 1)
        jnow = jdatetime.datetime.fromgregorian(datetime=now_local)
        j_year = jnow.year
        j_month = jnow.month + 1
        if j_month > 12:
            j_year += 1
            j_month = 1
        try:
            jdt = jdatetime.datetime(j_year, j_month, target_day, target_hour, target_minute)
            next_local = tz.localize(jdt.togregorian())
        except Exception:
            next_local = now_local + timedelta(days=30)
        return next_local.astimezone(pytz.UTC)

    return None


async def execute_reminder_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Called by JobQueue when a reminder's target time arrives."""
    job = context.job
    reminder_id = job.data.get("reminder_id") if job and job.data else None
    if not reminder_id:
        return

    reminder = await get_reminder(reminder_id)
    if not reminder or reminder.status != ReminderStatus.PENDING:
        return

    user = await get_or_create_user(reminder.user_id, reminder.chat_id)
    tz = pytz.timezone(user.timezone)
    local_dt = reminder.remind_at_utc.astimezone(tz)
    jdt = jdatetime.datetime.fromgregorian(datetime=local_dt)
    formatted_time = f"{jdt.strftime('%Y/%m/%d %H:%M')} ({local_dt.strftime('%Y-%m-%d %H:%M')})"

    recurrence_notice = ""
    if reminder.recurrence_type != "none":
        recurrence_map = {
            "daily": "روزانه",
            "weekly": "هفتگی",
            "even_days": "روزهای زوج",
            "odd_days": "روزهای فرد",
            "monthly": "ماهانه",
        }
        recurrence_notice = f"\n🔄 تکرار: {recurrence_map.get(reminder.recurrence_type, 'دوره‌ای')}"

    text = (
        f"🔔 **یادآوری انجام کار:**\n\n"
        f"📌 **{reminder.task_text}**\n\n"
        f"⏰ موعد: `{formatted_time}`"
        f"{recurrence_notice}"
    )

    try:
        await context.bot.send_message(
            chat_id=reminder.chat_id,
            text=text,
            parse_mode="Markdown",
            reply_markup=build_reminder_keyboard(reminder.id),
        )
    except Exception as e:
        logger.error("Failed to send reminder message for #%s: %s", reminder.id, e)

    # Check for recurrence
    if reminder.recurrence_type != "none":
        next_utc = calculate_next_occurrence(reminder)
        if next_utc:
            await update_reminder_time(reminder.id, next_utc)
            # Re-schedule next occurrence
            schedule_reminder_job(context.application.job_queue, reminder.id, next_utc)
            return

    # One-off reminder delivered, mark completed
    await update_reminder_status(reminder.id, ReminderStatus.COMPLETED)


def schedule_reminder_job(job_queue, reminder_id: int, remind_at_utc: datetime) -> None:
    """Schedules or reschedules a single job in PTB JobQueue."""
    if job_queue is None:
        logger.warning("JobQueue is not initialized. Skipping job scheduling.")
        return

    # Cancel existing jobs for this reminder_id
    existing_jobs = job_queue.get_jobs_by_name(f"reminder_{reminder_id}")
    for j in existing_jobs:
        j.schedule_removal()

    # Schedule new job
    job_queue.run_once(
        execute_reminder_job,
        when=remind_at_utc,
        data={"reminder_id": reminder_id},
        name=f"reminder_{reminder_id}",
    )
    logger.info("Scheduled job for reminder #%s at %s UTC", reminder_id, remind_at_utc)


async def restore_pending_jobs(application) -> None:
    """
    Restores and reschedules all pending reminders upon bot startup.
    Handles missed reminders while offline.
    """
    job_queue = application.job_queue
    if job_queue is None:
        logger.warning("JobQueue is not available during restore_pending_jobs.")
        return

    now_utc = datetime.now(pytz.UTC)
    pending_reminders = await get_all_pending_reminders()
    logger.info("Found %d pending reminders to restore.", len(pending_reminders))

    for rem in pending_reminders:
        if rem.remind_at_utc <= now_utc:
            # Missed reminder while offline!
            user = await get_or_create_user(rem.user_id, rem.chat_id)
            tz = pytz.timezone(user.timezone)
            local_dt = rem.remind_at_utc.astimezone(tz)
            jdt = jdatetime.datetime.fromgregorian(datetime=local_dt)
            formatted_time = f"{jdt.strftime('%Y/%m/%d %H:%M')} ({local_dt.strftime('%Y-%m-%d %H:%M')})"

            try:
                await application.bot.send_message(
                    chat_id=rem.chat_id,
                    text=(
                        f"⚠️ **یادآوری سپری‌شده (زمان آفلاین بودن ربات):**\n\n"
                        f"📌 **{rem.task_text}**\n\n"
                        f"⏰ موعد اصلی: `{formatted_time}`"
                    ),
                    parse_mode="Markdown",
                    reply_markup=build_reminder_keyboard(rem.id),
                )
            except Exception as e:
                logger.error("Failed to deliver missed reminder #%s: %s", rem.id, e)

            # Handle recurrence if applicable
            if rem.recurrence_type != "none":
                next_utc = calculate_next_occurrence(rem, now=now_utc)
                if next_utc:
                    await update_reminder_time(rem.id, next_utc)
                    schedule_reminder_job(job_queue, rem.id, next_utc)
                    continue

            await update_reminder_status(rem.id, ReminderStatus.COMPLETED)
        else:
            # Future reminder: schedule regularly
            schedule_reminder_job(job_queue, rem.id, rem.remind_at_utc)
