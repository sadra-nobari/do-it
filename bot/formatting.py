"""Shared Persian formatting helpers for dates, times and due descriptions.

Used by handlers and scheduler so every user-facing message shows the
same Jalali/Gregorian/relative formats.
"""

from datetime import datetime
from typing import Optional

import jdatetime

from bot.parser.normalizer import PERSIAN_DIGITS

PERSIAN_DIGIT_MAP = {
    ord(ascii_digit): ord(persian_digit)
    for persian_digit, ascii_digit in zip(PERSIAN_DIGITS, "0123456789")
}

TODAY = "امروز"
TOMORROW = "فردا"
DAY_AFTER_TOMORROW = "پس‌فردا"


def to_persian_digits(text: str) -> str:
    """Converts ASCII digits in the given text to Persian digits."""
    return text.translate(PERSIAN_DIGIT_MAP)


def weekday_name_fa(dt: datetime) -> str:
    """Returns the Persian weekday name (شنبه ... جمعه) for a local datetime."""
    jdt = jdatetime.datetime.fromgregorian(datetime=dt)
    return jdatetime.date.j_weekdays_fa[jdt.weekday()]


def jalali_date_str(dt: datetime) -> str:
    """Formats a local datetime as a Jalali date string, e.g. ۱۴۰۵/۰۷/۲۵."""
    jdt = jdatetime.datetime.fromgregorian(datetime=dt)
    return to_persian_digits(jdt.strftime("%Y/%m/%d"))


def time_str(dt: datetime) -> str:
    """Formats the HH:MM part of a local datetime with Persian digits."""
    return to_persian_digits(dt.strftime("%H:%M"))


def short_jalali_day_str(dt: datetime) -> str:
    """Formats a local datetime as a short Jalali day, e.g. ۲۵ مهر."""
    jdt = jdatetime.datetime.fromgregorian(datetime=dt)
    month_fa = jdatetime.datetime.j_months_fa[jdt.month - 1]
    return f"{to_persian_digits(str(jdt.day))} {month_fa}"


def describe_due(local_dt: datetime, now_local: Optional[datetime] = None) -> str:
    """
    Builds a human-friendly Persian description of a due datetime,
    e.g. «امروز ساعت ۱۹:۰۰» or «۵شنبه ۲۵ مهر، ساعت ۰۹:۰۰».
    """
    if now_local is None:
        now_local = datetime.now(local_dt.tzinfo) if local_dt.tzinfo else datetime.now()
    day_diff = (local_dt.date() - now_local.date()).days
    clock = f"ساعت {time_str(local_dt)}"

    if day_diff == 0:
        return f"{TODAY} {clock}"
    if day_diff == 1:
        return f"{TOMORROW} {clock}"
    if day_diff == 2:
        return f"{DAY_AFTER_TOMORROW} {clock}"
    if 0 < day_diff < 7:
        return f"{weekday_name_fa(local_dt)} {clock}"
    if day_diff <= 0:
        return f"{jalali_date_str(local_dt)} {clock}"

    year_prefix = ""
    jdt = jdatetime.datetime.fromgregorian(datetime=local_dt)
    jnow = jdatetime.datetime.fromgregorian(datetime=now_local)
    if jdt.year != jnow.year:
        year_prefix = f"{to_persian_digits(str(jdt.year))} "
    return f"{year_prefix}{short_jalali_day_str(local_dt)}، {clock}"


def gregorian_str(dt: datetime) -> str:
    """Formats a local datetime as a Gregorian string, e.g. 2026-10-25 19:00."""
    return dt.strftime("%Y-%m-%d %H:%M")


def full_due_str(local_dt: datetime, now_local: Optional[datetime] = None) -> str:
    """
    Combination used in reminder cards: relative/Persian description
    plus the Gregorian equivalent, e.g.
    «شنبه ۲۵ مهر، ساعت ۱۹:۰۰ (2026-10-25 19:00)».
    """
    return f"{describe_due(local_dt, now_local)} ({gregorian_str(local_dt)})"
