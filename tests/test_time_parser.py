from datetime import datetime
import pytest
import pytz

from bot.parser.time_parser import parse_reminder


@pytest.fixture
def tehran_tz():
    return pytz.timezone("Asia/Tehran")


@pytest.fixture
def ref_time(tehran_tz):
    # Reference time: 1405-07-25 14:00 (Saturday, 2026-10-17 14:00:00+03:30)
    # Saturday in Tehran
    return tehran_tz.localize(datetime(2026, 10, 17, 14, 0, 0))


def test_hour_afternoon(ref_time):
    # 'خرید نان + ساعت ۷ عصر'
    res = parse_reminder("خرید نان + ساعت ۷ عصر", now=ref_time)
    assert res.task == "خرید نان"
    assert res.remind_at.hour == 19
    assert res.remind_at.minute == 0
    assert res.remind_at.date() == ref_time.date()
    assert res.recurrence_type == "none"


def test_hour_afternoon_without_plus(ref_time):
    # 'خرید نان ساعت ۷ عصر'
    res = parse_reminder("خرید نان ساعت ۷ عصر", now=ref_time)
    assert res.task == "خرید نان"
    assert res.remind_at.hour == 19
    assert res.remind_at.minute == 0
    assert res.remind_at.date() == ref_time.date()


def test_tomorrow_hour(ref_time):
    # 'فردا ساعت ۶ برم دکتر'
    res = parse_reminder("فردا ساعت ۶ برم دکتر", now=ref_time)
    assert res.task == "برم دکتر"
    # Tomorrow is 2026-10-18
    assert res.remind_at.day == 18
    assert res.remind_at.hour == 18


def test_daily_recurrence(ref_time):
    # 'ورزش + هر روز ۷ صبح'
    res = parse_reminder("ورزش + هر روز ۷ صبح", now=ref_time)
    assert res.task == "ورزش"
    assert res.recurrence_type == "daily"
    assert res.remind_at.hour == 7
    assert res.remind_at.minute == 0


def test_daily_recurrence_without_plus(ref_time):
    # 'هر روز ۷ صبح ورزش کن'
    res = parse_reminder("هر روز ۷ صبح ورزش کن", now=ref_time)
    assert res.task == "ورزش کن"
    assert res.recurrence_type == "daily"
    assert res.remind_at.hour == 7


def test_weekday_thursday_afternoon(ref_time):
    # 'استخر + پنج شنبه ۷ بعد از ظهر'
    # ref_time is Saturday 2026-10-17. Next Thursday is 2026-10-22.
    res = parse_reminder("استخر + پنج شنبه ۷ بعد از ظهر", now=ref_time)
    assert res.task == "استخر"
    assert res.remind_at.hour == 19
    assert res.remind_at.minute == 0
    # Thursday is weekday 3 in Python
    assert res.remind_at.weekday() == 3
    assert res.remind_at.day == 22


def test_weekday_with_halfspace(ref_time):
    # 'پنج‌شنبه ساعت ۸ شب کتاب بخون'
    res = parse_reminder("پنج‌شنبه ساعت ۸ شب کتاب بخون", now=ref_time)
    assert res.task == "کتاب بخون"
    assert res.remind_at.hour == 20
    assert res.remind_at.weekday() == 3


def test_jalali_date(ref_time):
    # '۲۵ مهر ماه' -> in 1405, 25 Mehr is 2026-10-17.
    # Since ref_time is 14:00 and default hour is 09:00, 25 Mehr 09:00 has passed today,
    # so it schedules for next year (or user gets next 25 Mehr).
    res = parse_reminder("جلسه کاری + ۲۵ مهر ماه", now=ref_time)
    assert res.task == "جلسه کاری"
    assert res.calendar_type == "jalali"
    assert res.remind_at.hour == 9


def test_jalali_date_with_hour(ref_time):
    # '۲۵ مهر ساعت ۴ بعد از ظهر' -> today 16:00 (future relative to 14:00)
    res = parse_reminder("۲۵ مهر ساعت ۴ بعد از ظهر جلسه اولیا", now=ref_time)
    assert res.task == "جلسه اولیا"
    assert res.remind_at.hour == 16
    assert res.remind_at.day == 17
    assert res.remind_at.month == 10


def test_gregorian_date_persian_name(ref_time):
    # '۲۵ اکتبر ساعت ۱۶' -> October 25, 2026 at 16:00
    res = parse_reminder("ارسال گزارش + ۲۵ اکتبر ساعت ۱۶", now=ref_time)
    assert res.task == "ارسال گزارش"
    assert res.calendar_type == "gregorian"
    assert res.remind_at.day == 25
    assert res.remind_at.month == 10
    assert res.remind_at.hour == 16


def test_gregorian_date_english(ref_time):
    # '15 November send report'
    res = parse_reminder("15 November send report", now=ref_time)
    assert res.task == "send report"
    assert res.calendar_type == "gregorian"
    assert res.remind_at.day == 15
    assert res.remind_at.month == 11
    assert res.remind_at.hour == 9


def test_relative_minutes(ref_time):
    # 'چک کردن فر + ۱۰ دقیقه دیگه'
    res = parse_reminder("چک کردن فر + ۱۰ دقیقه دیگه", now=ref_time)
    assert res.task == "چک کردن فر"
    delta = (res.remind_at - ref_time).total_seconds()
    assert delta == 600  # 10 minutes


def test_relative_special_half_hour(ref_time):
    # 'نیم ساعت دیگه به علی زنگ بزن'
    res = parse_reminder("نیم ساعت دیگه به علی زنگ بزن", now=ref_time)
    assert res.task == "به علی زنگ بزن"
    delta = (res.remind_at - ref_time).total_seconds()
    assert delta == 1800  # 30 minutes


def test_relative_quarter_hour(ref_time):
    # 'یک ربع دیگه'
    res = parse_reminder("قرص + یک ربع دیگه", now=ref_time)
    assert res.task == "قرص"
    delta = (res.remind_at - ref_time).total_seconds()
    assert delta == 900  # 15 minutes


def test_even_days_recurrence(ref_time):
    # 'روزهای زوج ساعت ۵ عصر کلاس زبان'
    res = parse_reminder("روزهای زوج ساعت ۵ عصر کلاس زبان", now=ref_time)
    assert res.task == "کلاس زبان"
    assert res.recurrence_type == "even_days"
    assert res.remind_at.hour == 17
    # Saturday is even day and 17:00 > 14:00, so it schedules for today Saturday 17:00!
    assert res.remind_at.weekday() == 5
    assert res.remind_at.day == 17


def test_odd_days_recurrence(ref_time):
    # 'روزهای فرد ساعت ۵ عصر ورزش'
    res = parse_reminder("روزهای فرد ساعت ۵ عصر ورزش", now=ref_time)
    assert res.task == "ورزش"
    assert res.recurrence_type == "odd_days"
    assert res.remind_at.hour == 17
    # ref_time is Saturday (5). Next odd day is Sunday (6).
    assert res.remind_at.weekday() == 6
    assert res.remind_at.day == 18


def test_multiple_pluses_in_task(ref_time):
    # 'خرید نان + شیر + پنیر + فردا ۸ صبح'
    res = parse_reminder("خرید نان + شیر + پنیر + فردا ۸ صبح", now=ref_time)
    assert res.task == "خرید نان + شیر + پنیر"
    assert res.remind_at.hour == 8
    assert res.remind_at.day == 18


def test_newline_separator(ref_time):
    # "جلسه شرکت\nفردا ساعت ۱۰"
    res = parse_reminder("جلسه شرکت\nفردا ساعت ۱۰", now=ref_time)
    assert res.task == "جلسه شرکت"
    assert res.remind_at.day == 18
    assert res.remind_at.hour == 10


def test_hyphen_separator(ref_time):
    # "تماس با پشتیبانی - یک ربع دیگه"
    res = parse_reminder("تماس با پشتیبانی - یک ربع دیگه", now=ref_time)
    assert res.task == "تماس با پشتیبانی"
    assert (res.remind_at - ref_time).total_seconds() == 900


def test_arabic_digits(ref_time):
    # "جلسه + ساعت ٧ عصر" using Arabic numeral ٧
    res = parse_reminder("جلسه + ساعت ٧ عصر", now=ref_time)
    assert res.task == "جلسه"
    assert res.remind_at.hour == 19


def test_half_and_quarter_time(ref_time):
    # "دیدن فیلم + ساعت ۷ و نیم شب"
    res = parse_reminder("دیدن فیلم + ساعت ۷ و نیم شب", now=ref_time)
    assert res.task == "دیدن فیلم"
    assert res.remind_at.hour == 19
    assert res.remind_at.minute == 30


def test_past_time_today(ref_time):
    # ref_time is 14:00 today. "امروز ساعت ۱۰ صبح"
    res = parse_reminder("امروز ساعت ۱۰ صبح رفتن به بانک", now=ref_time)
    assert res.task == "رفتن به بانک"
    assert res.is_past_warning is True
    # Should be scheduled for tomorrow 10:00 AM as a fallback
    assert res.remind_at.hour == 10
    assert res.remind_at.day == 18

