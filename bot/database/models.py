from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional


class ReminderStatus:
    PENDING = "pending"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


@dataclass
class Reminder:
    id: Optional[int]
    user_id: int
    chat_id: int
    task_text: str
    remind_at_utc: datetime
    recurrence_type: str  # 'none', 'daily', 'weekly', 'monthly', 'even_days', 'odd_days'
    recurrence_rule: Optional[Dict[str, Any]]
    status: str
    calendar_type: str
    original_time_expr: str
    created_at: datetime


@dataclass
class User:
    user_id: int
    chat_id: int
    timezone: str
    created_at: datetime
