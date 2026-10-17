import datetime

import pytz

from bot.formatting import (
    describe_due,
    full_due_str,
    gregorian_str,
    jalali_date_str,
    short_jalali_day_str,
    time_str,
    to_persian_digits,
    weekday_name_fa,
)

TZ = pytz.timezone("Asia/Tehran")


def _local(year: int, month: int, day: int, hour: int = 19, minute: int = 0) -> datetime.datetime:
    return TZ.localize(datetime.datetime(year, month, day, hour, minute))


def test_to_persian_digits():
    assert to_persian_digits("2026-10-25 19:00") == "۲۰۲۶-۱۰-۲۵ ۱۹:۰۰"


def test_jalali_date_str_known_dates():
    assert jalali_date_str(_local(2026, 10, 17)) == "۱۴۰۵/۰۷/۲۵"
    assert jalali_date_str(_local(2026, 3, 21)) == "۱۴۰۵/۰۱/۰۱"


def test_time_str():
    assert time_str(_local(2026, 10, 17, hour=7, minute=5)) == "۰۷:۰۵"


def test_weekday_name_fa():
    # 2026-10-17 is Saturday
    assert weekday_name_fa(_local(2026, 10, 17)) == "شنبه"
    assert weekday_name_fa(_local(2026, 10, 20)) == "سه‌شنبه"


def test_short_jalali_day_str():
    assert short_jalali_day_str(_local(2026, 10, 17)) == "۲۵ مهر"
    assert short_jalali_day_str(_local(2026, 3, 21)) == "۱ فروردین"


def test_describe_due_relative_days():
    now = _local(2026, 10, 17, hour=10)
    assert describe_due(_local(2026, 10, 17, hour=19), now) == "امروز ساعت ۱۹:۰۰"
    assert describe_due(_local(2026, 10, 18, hour=9), now) == "فردا ساعت ۰۹:۰۰"
    assert describe_due(_local(2026, 10, 19, hour=9), now) == "پس‌فردا ساعت ۰۹:۰۰"


def test_describe_due_within_week_uses_weekday():
    now = _local(2026, 10, 17, hour=10)
    assert describe_due(_local(2026, 10, 22, hour=9), now).startswith("پنج‌شنبه ساعت ۰۹:۰۰")


def test_describe_due_beyond_week_uses_jalali_day():
    now = _local(2026, 10, 17, hour=10)
    desc = describe_due(_local(2026, 10, 25, hour=9), now)
    assert "آبان" in desc
    assert desc.endswith("ساعت ۰۹:۰۰")


def test_describe_due_past_uses_full_jalali_date():
    now = _local(2026, 10, 17, hour=10)
    assert describe_due(_local(2026, 10, 10, hour=9), now) == "۱۴۰۵/۰۷/۱۸ ساعت ۰۹:۰۰"


def test_gregorian_and_full_due_str():
    dt = _local(2026, 10, 25, hour=16)
    now = _local(2026, 10, 17, hour=10)
    assert gregorian_str(dt) == "2026-10-25 16:00"
    full = full_due_str(dt, now)
    assert full == "۳ آبان، ساعت ۱۶:۰۰ (2026-10-25 16:00)"
