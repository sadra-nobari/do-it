import json
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional
import aiosqlite
import pytz

from bot.config import DATABASE_PATH
from bot.database.models import Reminder, ReminderStatus, User


@asynccontextmanager
async def get_db(db_path: Optional[str] = None) -> AsyncGenerator[aiosqlite.Connection, None]:
    """Async context manager providing a configured SQLite connection."""
    path = db_path or DATABASE_PATH
    async with aiosqlite.connect(path) as conn:
        conn.row_factory = aiosqlite.Row
        yield conn


async def init_db(db_path: Optional[str] = None) -> None:
    """Initializes SQLite schema and indexes."""
    async with get_db(db_path) as conn:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                chat_id INTEGER NOT NULL,
                task_text TEXT NOT NULL,
                remind_at_utc TEXT NOT NULL,
                recurrence_type TEXT NOT NULL DEFAULT 'none',
                recurrence_rule TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                calendar_type TEXT NOT NULL DEFAULT 'time_only',
                original_time_expr TEXT,
                created_at TEXT NOT NULL
            );
            """
        )
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                chat_id INTEGER NOT NULL,
                timezone TEXT NOT NULL DEFAULT 'Asia/Tehran',
                created_at TEXT NOT NULL
            );
            """
        )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_reminders_status_time ON reminders(status, remind_at_utc);"
        )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_reminders_user ON reminders(user_id, status);"
        )
        await conn.commit()


async def create_reminder(
    user_id: int,
    chat_id: int,
    task_text: str,
    remind_at_utc: datetime,
    recurrence_type: str = "none",
    recurrence_rule: Optional[Dict[str, Any]] = None,
    calendar_type: str = "time_only",
    original_time_expr: str = "",
    db_path: Optional[str] = None,
) -> Reminder:
    """Creates and persists a new reminder in SQLite."""
    now_utc_str = datetime.now(pytz.UTC).isoformat()
    remind_at_utc_str = remind_at_utc.astimezone(pytz.UTC).isoformat()
    rule_json = json.dumps(recurrence_rule) if recurrence_rule else None

    async with get_db(db_path) as conn:
        cursor = await conn.execute(
            """
            INSERT INTO reminders (
                user_id, chat_id, task_text, remind_at_utc,
                recurrence_type, recurrence_rule, status,
                calendar_type, original_time_expr, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                chat_id,
                task_text,
                remind_at_utc_str,
                recurrence_type,
                rule_json,
                ReminderStatus.PENDING,
                calendar_type,
                original_time_expr,
                now_utc_str,
            ),
        )
        await conn.commit()
        reminder_id = cursor.lastrowid

    return Reminder(
        id=reminder_id,
        user_id=user_id,
        chat_id=chat_id,
        task_text=task_text,
        remind_at_utc=remind_at_utc.astimezone(pytz.UTC),
        recurrence_type=recurrence_type,
        recurrence_rule=recurrence_rule,
        status=ReminderStatus.PENDING,
        calendar_type=calendar_type,
        original_time_expr=original_time_expr,
        created_at=datetime.fromisoformat(now_utc_str),
    )


def _row_to_reminder(row: aiosqlite.Row) -> Reminder:
    rule = json.loads(row["recurrence_rule"]) if row["recurrence_rule"] else None
    return Reminder(
        id=row["id"],
        user_id=row["user_id"],
        chat_id=row["chat_id"],
        task_text=row["task_text"],
        remind_at_utc=datetime.fromisoformat(row["remind_at_utc"]),
        recurrence_type=row["recurrence_type"],
        recurrence_rule=rule,
        status=row["status"],
        calendar_type=row["calendar_type"],
        original_time_expr=row["original_time_expr"],
        created_at=datetime.fromisoformat(row["created_at"]),
    )


async def get_reminder(
    reminder_id: int, db_path: Optional[str] = None
) -> Optional[Reminder]:
    async with get_db(db_path) as conn:
        cursor = await conn.execute(
            "SELECT * FROM reminders WHERE id = ?", (reminder_id,)
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return _row_to_reminder(row)


async def get_user_pending_reminders(
    user_id: int, db_path: Optional[str] = None
) -> List[Reminder]:
    async with get_db(db_path) as conn:
        cursor = await conn.execute(
            """
            SELECT * FROM reminders
            WHERE user_id = ? AND status = ?
            ORDER BY remind_at_utc ASC
            """,
            (user_id, ReminderStatus.PENDING),
        )
        rows = await cursor.fetchall()
        return [_row_to_reminder(r) for r in rows]


async def get_all_pending_reminders(
    db_path: Optional[str] = None,
) -> List[Reminder]:
    async with get_db(db_path) as conn:
        cursor = await conn.execute(
            """
            SELECT * FROM reminders
            WHERE status = ?
            ORDER BY remind_at_utc ASC
            """,
            (ReminderStatus.PENDING,),
        )
        rows = await cursor.fetchall()
        return [_row_to_reminder(r) for r in rows]


async def update_reminder_status(
    reminder_id: int, status: str, db_path: Optional[str] = None
) -> None:
    async with get_db(db_path) as conn:
        await conn.execute(
            "UPDATE reminders SET status = ? WHERE id = ?", (status, reminder_id)
        )
        await conn.commit()


async def update_reminder_time(
    reminder_id: int, new_remind_at_utc: datetime, db_path: Optional[str] = None
) -> None:
    dt_str = new_remind_at_utc.astimezone(pytz.UTC).isoformat()
    async with get_db(db_path) as conn:
        await conn.execute(
            "UPDATE reminders SET remind_at_utc = ?, status = ? WHERE id = ?",
            (dt_str, ReminderStatus.PENDING, reminder_id),
        )
        await conn.commit()


async def get_or_create_user(
    user_id: int,
    chat_id: int,
    default_tz: str = "Asia/Tehran",
    db_path: Optional[str] = None,
) -> User:
    async with get_db(db_path) as conn:
        cursor = await conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        if row:
            return User(
                user_id=row["user_id"],
                chat_id=row["chat_id"],
                timezone=row["timezone"],
                created_at=datetime.fromisoformat(row["created_at"]),
            )

        now_str = datetime.now(pytz.UTC).isoformat()
        await conn.execute(
            "INSERT INTO users (user_id, chat_id, timezone, created_at) VALUES (?, ?, ?, ?)",
            (user_id, chat_id, default_tz, now_str),
        )
        await conn.commit()
        return User(
            user_id=user_id,
            chat_id=chat_id,
            timezone=default_tz,
            created_at=datetime.fromisoformat(now_str),
        )


async def update_user_timezone(
    user_id: int, timezone: str, db_path: Optional[str] = None
) -> None:
    async with get_db(db_path) as conn:
        await conn.execute(
            "UPDATE users SET timezone = ? WHERE user_id = ?", (timezone, user_id)
        )
        await conn.commit()
