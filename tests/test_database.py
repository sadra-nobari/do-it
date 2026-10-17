import os
import tempfile
from datetime import datetime, timedelta
import pytest
import pytest_asyncio
import pytz

from bot.database import (
    ReminderStatus,
    create_reminder,
    get_all_pending_reminders,
    get_or_create_user,
    get_reminder,
    get_user_pending_reminders,
    init_db,
    update_reminder_status,
    update_reminder_time,
    update_user_timezone,
)


@pytest_asyncio.fixture
async def temp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    await init_db(path)
    yield path
    if os.path.exists(path):
        os.remove(path)


@pytest.mark.asyncio
async def test_create_and_get_reminder(temp_db):
    now_utc = datetime.now(pytz.UTC)
    remind_at = now_utc + timedelta(hours=2)

    rem = await create_reminder(
        user_id=123,
        chat_id=456,
        task_text="خرید نان",
        remind_at_utc=remind_at,
        recurrence_type="daily",
        recurrence_rule={"hour": 7, "minute": 0},
        calendar_type="time_only",
        original_time_expr="هر روز ۷ صبح",
        db_path=temp_db,
    )

    assert rem.id is not None
    assert rem.user_id == 123
    assert rem.task_text == "خرید نان"
    assert rem.status == ReminderStatus.PENDING

    fetched = await get_reminder(rem.id, db_path=temp_db)
    assert fetched is not None
    assert fetched.id == rem.id
    assert fetched.recurrence_type == "daily"
    assert fetched.recurrence_rule == {"hour": 7, "minute": 0}


@pytest.mark.asyncio
async def test_update_status_and_time(temp_db):
    now_utc = datetime.now(pytz.UTC)
    rem = await create_reminder(
        user_id=123,
        chat_id=456,
        task_text="تماس با دکتر",
        remind_at_utc=now_utc + timedelta(hours=1),
        db_path=temp_db,
    )

    await update_reminder_status(rem.id, ReminderStatus.COMPLETED, db_path=temp_db)
    fetched = await get_reminder(rem.id, db_path=temp_db)
    assert fetched.status == ReminderStatus.COMPLETED

    new_time = now_utc + timedelta(hours=3)
    await update_reminder_time(rem.id, new_time, db_path=temp_db)
    fetched2 = await get_reminder(rem.id, db_path=temp_db)
    assert fetched2.status == ReminderStatus.PENDING
    assert abs((fetched2.remind_at_utc - new_time).total_seconds()) < 2


@pytest.mark.asyncio
async def test_pending_reminders_list(temp_db):
    now_utc = datetime.now(pytz.UTC)

    rem1 = await create_reminder(
        user_id=10,
        chat_id=10,
        task_text="کار ۱",
        remind_at_utc=now_utc + timedelta(minutes=10),
        db_path=temp_db,
    )
    rem2 = await create_reminder(
        user_id=10,
        chat_id=10,
        task_text="کار ۲",
        remind_at_utc=now_utc + timedelta(minutes=20),
        db_path=temp_db,
    )
    _ = await create_reminder(
        user_id=20,
        chat_id=20,
        task_text="کار کاربر دیگر",
        remind_at_utc=now_utc + timedelta(minutes=30),
        db_path=temp_db,
    )

    user10_pending = await get_user_pending_reminders(10, db_path=temp_db)
    assert len(user10_pending) == 2
    assert [r.id for r in user10_pending] == [rem1.id, rem2.id]

    all_pending = await get_all_pending_reminders(db_path=temp_db)
    assert len(all_pending) == 3


@pytest.mark.asyncio
async def test_user_preferences(temp_db):
    user = await get_or_create_user(999, 888, default_tz="Asia/Tehran", db_path=temp_db)
    assert user.user_id == 999
    assert user.timezone == "Asia/Tehran"

    await update_user_timezone(999, "Europe/London", db_path=temp_db)
    user_updated = await get_or_create_user(999, 888, db_path=temp_db)
    assert user_updated.timezone == "Europe/London"
