from datetime import datetime, time, timedelta
import pytz

from bot.database.models import Reminder, ReminderStatus
from bot.scheduler.job_manager import (
    build_reminder_keyboard,
    calculate_next_occurrence,
)


def create_mock_reminder(recurrence_type, recurrence_rule=None):
    now_utc = datetime.now(pytz.UTC)
    return Reminder(
        id=1,
        user_id=100,
        chat_id=100,
        task_text="تست",
        remind_at_utc=now_utc,
        recurrence_type=recurrence_type,
        recurrence_rule=recurrence_rule,
        status=ReminderStatus.PENDING,
        calendar_type="time_only",
        original_time_expr="تست",
        created_at=now_utc,
    )


def test_calculate_next_occurrence_daily():
    tz = pytz.timezone("Asia/Tehran")
    ref_time = tz.localize(datetime(2026, 10, 17, 14, 0, 0))  # Saturday
    rem = create_mock_reminder("daily", {"hour": 7, "minute": 0})

    next_utc = calculate_next_occurrence(rem, now=ref_time)
    next_local = next_utc.astimezone(tz)
    assert next_local.day == 18
    assert next_local.hour == 7
    assert next_local.minute == 0


def test_calculate_next_occurrence_even_days():
    tz = pytz.timezone("Asia/Tehran")
    # Saturday 2026-10-17 18:00 (after 17:00). Next even day is Monday 2026-10-19.
    ref_time = tz.localize(datetime(2026, 10, 17, 18, 0, 0))
    rem = create_mock_reminder("even_days", {"hour": 17, "minute": 0})

    next_utc = calculate_next_occurrence(rem, now=ref_time)
    next_local = next_utc.astimezone(tz)
    # Monday is weekday 0
    assert next_local.weekday() == 0
    assert next_local.day == 19
    assert next_local.hour == 17


def test_calculate_next_occurrence_odd_days():
    tz = pytz.timezone("Asia/Tehran")
    # Saturday 2026-10-17 14:00. Next odd day is Sunday 2026-10-18.
    ref_time = tz.localize(datetime(2026, 10, 17, 14, 0, 0))
    rem = create_mock_reminder("odd_days", {"hour": 17, "minute": 0})

    next_utc = calculate_next_occurrence(rem, now=ref_time)
    next_local = next_utc.astimezone(tz)
    # Sunday is weekday 6
    assert next_local.weekday() == 6
    assert next_local.day == 18
    assert next_local.hour == 17


def test_calculate_next_occurrence_none():
    rem = create_mock_reminder("none")
    assert calculate_next_occurrence(rem) is None


def test_build_reminder_keyboard():
    kb = build_reminder_keyboard(42)
    # Check that buttons contain callback data with reminder ID 42
    callbacks = [btn.callback_data for row in kb.inline_keyboard for btn in row]
    assert "done_42" in callbacks
    assert "snooze_42_5" in callbacks
    assert "snooze_42_15" in callbacks
    assert "snooze_42_60" in callbacks
    assert "snooze_42_1440" in callbacks
