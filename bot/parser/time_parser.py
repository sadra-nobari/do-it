import re
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Any, Dict, List, Optional, Tuple
import jdatetime
import pytz

from bot.parser.normalizer import normalize_text
from bot.parser.patterns import (
    DAY_OFFSETS,
    DAY_PERIOD_PATTERNS,
    GREGORIAN_MONTHS,
    JALALI_MONTHS,
    PERIOD_AFTERNOON,
    PERIOD_EVENING,
    PERIOD_MIDNIGHT,
    PERIOD_MORNING,
    PERIOD_NIGHT,
    PERIOD_NOON,
    RECURRENCE_DAILY,
    RECURRENCE_EVEN_DAYS,
    RECURRENCE_MONTHLY,
    RECURRENCE_ODD_DAYS,
    RECURRENCE_WEEKLY,
    RELATIVE_PATTERN,
    SPECIAL_RELATIVE_PATTERNS,
    WEEKDAY_MAP,
)


@dataclass
class ParseResult:
    task: str
    remind_at: datetime  # Timezone-aware datetime in user's timezone
    remind_at_utc: datetime  # UTC datetime for scheduler & DB
    recurrence_type: str  # 'none', 'daily', 'weekly', 'monthly', 'even_days', 'odd_days'
    recurrence_rule: Optional[Dict[str, Any]]
    original_time_expr: str
    calendar_type: str  # 'jalali', 'gregorian', 'relative', 'time_only'
    is_past_warning: bool = False


# Words that introduce or glue tasks and times
GLUE_WORDS = {"که", "رو", "را"}


def split_task_and_time(raw_text: str) -> Tuple[str, str]:
    """
    Separates the task description and the time expression from raw user input.
    Supports:
    1. Explicit '+' separator (e.g. 'خرید نان + ساعت ۷ عصر')
    2. Alternative explicit separators: newline, ' - ', '، '
    3. Flexible natural language: identifies time phrases anywhere (start, end, or middle)
    """
    cleaned = normalize_text(raw_text)

    # 1. Check for explicit '+'
    if "+" in cleaned:
        parts = cleaned.split("+")
        # In case of multiple '+', last one is time, preceding ones are task
        time_part = parts[-1].strip()
        task_part = "+".join(parts[:-1]).strip()
        if time_part and task_part:
            return clean_task_text(task_part), time_part

    # 2. Check for explicit newline
    if "\n" in cleaned:
        lines = [line.strip() for line in cleaned.split("\n") if line.strip()]
        if len(lines) >= 2:
            # Check if last line looks like a time expr
            if looks_like_time(lines[-1]):
                return clean_task_text(" ".join(lines[:-1])), lines[-1]
            if looks_like_time(lines[0]):
                return clean_task_text(" ".join(lines[1:])), lines[0]

    # 3. Check for ' - ' or '، '
    for sep in [" - ", "، ", " ، "]:
        if sep in cleaned:
            parts = cleaned.split(sep)
            if len(parts) == 2:
                if looks_like_time(parts[1]):
                    return clean_task_text(parts[0]), parts[1].strip()
                if looks_like_time(parts[0]):
                    return clean_task_text(parts[1]), parts[0].strip()

    # 4. Pattern-based boundary search
    # Find the best time span inside the message
    span = find_time_span(cleaned)
    if span:
        start, end = span
        time_part = cleaned[start:end].strip()
        task_part = (cleaned[:start] + " " + cleaned[end:]).strip()
        if task_part and time_part:
            return clean_task_text(task_part), time_part

    # Fallback: couldn't separate cleanly, return whole text as time if it looks like time
    if looks_like_time(cleaned):
        return "یادآوری", cleaned

    return cleaned, ""


def clean_task_text(text: str) -> str:
    """Cleans task description from boundary punctuation and glue prepositions."""
    text = text.strip(" +-_،,:;.!?")
    tokens = text.split()
    while tokens and tokens[0].lower() in GLUE_WORDS:
        tokens.pop(0)
    while tokens and tokens[-1].lower() in GLUE_WORDS:
        tokens.pop()
    result = " ".join(tokens).strip(" +-_،,:;.!?")
    return result or text


def looks_like_time(text: str) -> bool:
    """Quick heuristic check if a phrase contains temporal keywords."""
    t = text.lower()
    # Check keywords
    if any(k in t for k in ["ساعت", "فردا", "امروز", "امشب", "پس فردا", "دیگه", "بعد"]):
        return True
    if any(w in t for w in WEEKDAY_MAP.keys()):
        return True
    if any(m in t for m in JALALI_MONTHS.keys()):
        return True
    if any(m in t for m in GREGORIAN_MONTHS.keys()):
        return True
    if any(
        k in t for k in ["هر روز", "هر هفته", "روزهای زوج", "روزهای فرد", "هر ماه"]
    ):
        return True
    if re.search(r"\b\d{1,2}(?::\d{2})?\s*(?:صبح|عصر|ظهر|شب|am|pm)?\b", t):
        return True
    return False


def find_time_span(text: str) -> Optional[Tuple[int, int]]:
    """
    Finds the start and end character indices of the time expression in the text.
    Handles time at the beginning, end, or middle.
    """
    # Comprehensive candidate patterns for time phrases
    time_regexes = [
        # Relative time: ۱۰ دقیقه دیگه, ۲ ساعت بعد, نیم ساعت دیگه
        r"(?:یک\s*)?(?:نیم|ربع|\d+(?:\.\d+)?)\s*(?:ثانیه|دقیقه|ساعت|روز|هفته|ماه)\s*(?:دیگه|بعد|دیگر|آینده)?",
        r"(?:یک\s*)?(?:نیم\s*ساعت|ربع\s*ساعت|یک\s*ربع)\s*(?:دیگه|بعد|دیگر)?",
        # Recurrence with time: هر روز ساعت ۷ صبح, روزهای زوج ساعت ۵ عصر, هر هفته پنج شنبه ۸ شب
        r"(?:هر\s*روز|هر\s*هفته|روزهای\s*زوج|روز\s*های\s*زوج|روزهای\s*فرد|روز\s*های\s*فرد|هر\s*ماه)(?:\s+(?:شنبه|یکشنبه|یک\s*شنبه|دوشنبه|دو\s*شنبه|سه\s*شنبه|چهارشنبه|چهار\s*شنبه|پنج\s*شنبه|جمعه))?(?:\s+(?:ساعت\s*)?\d{1,2}(?::\d{2})?(?:\s*(?:و\s*نیم|و\s*ربع))?(?:\s*(?:صبح|ظهر|عصر|بعد\s*از\s*ظهر|غروب|شب|بامداد|am|pm))?)?",
        # Days + Weekdays + Time: فردا ساعت ۶, پنج شنبه ۷ بعد از ظهر, این شنبه ساعت ۱۰
        r"(?:این\s+|هفته\s+بعد\s+)?(?:امروز|امشب|فردا|پس\s*فردا|شنبه|یکشنبه|یک\s*شنبه|دوشنبه|دو\s*شنبه|سه\s*شنبه|چهارشنبه|چهار\s*شنبه|پنج\s*شنبه|جمعه)(?:\s+(?:صبح|ظهر|عصر|بعد\s*از\s*ظهر|غروب|شب|بامداد))?(?:\s*(?:ساعت\s*)?\d{1,2}(?::\d{2})?(?:\s*(?:و\s*نیم|و\s*ربع))?(?:\s*(?:صبح|ظهر|عصر|بعد\s*از\s*ظهر|غروب|شب|بامداد|am|pm))?)?",
        # Jalali dates: ۲۵ مهر ماه, ۲۵ مهر ساعت ۴ عصر, اول آبان ساعت ۱۰
        r"\b\d{1,2}\s*(?:فروردین|اردیبهشت|خرداد|تیر|مرداد|شهریور|مهر|آبان|آذر|دی|بهمن|اسفند)(?:\s*ماه)?(?:\s+(?:سال\s*)?\d{4})?(?:\s*(?:ساعت\s*)?\d{1,2}(?::\d{2})?(?:\s*(?:و\s*نیم|و\s*ربع))?(?:\s*(?:صبح|ظهر|عصر|بعد\s*از\s*ظهر|بعدازظهر|غروب|شب|بامداد|am|pm))?)?",
        # Gregorian dates: 25 October, 25 اکتبر ساعت ۴ عصر, 15th Nov 8 pm
        r"\b\d{1,2}(?:st|nd|rd|th)?\s*(?:ژانویه|فوریه|مارس|آوریل|مه|می|ژوئن|ژوئیه|جولای|اوت|آگوست|سپتامبر|اکتبر|نوامبر|دسامبر|january|jan|february|feb|march|mar|april|apr|may|june|jun|july|jul|august|aug|september|sep|sept|october|oct|november|nov|december|dec)(?:\s+(?:سال\s*)?\d{4})?(?:\s*(?:ساعت\s*)?\d{1,2}(?::\d{2})?(?:\s*(?:و\s*نیم|و\s*ربع))?(?:\s*(?:صبح|ظهر|عصر|بعد\s*از\s*ظهر|بعدازظهر|غروب|شب|بامداد|am|pm))?)?",
        # Clock time only: ساعت ۷ عصر, ساعت ۱۹:۳۰, ساعت ۶ و نیم شب
        r"\bساعت\s*\d{1,2}(?::\d{2})?(?:\s*(?:و\s*نیم|و\s*ربع))?(?:\s*(?:صبح|ظهر|عصر|بعد\s*از\s*ظهر|غروب|شب|بامداد|am|pm))?",
        # Standalone numeric time with period: 7 صبح, 8 شب, 19:00
        r"\b\d{1,2}:\d{2}\s*(?:صبح|عصر|شب|ظهر|am|pm)?\b",
        r"\b\d{1,2}\s*(?:صبح|عصر|بعد\s*از\s*ظهر|شب|ظهر)\b",
    ]

    best_match = None
    best_len = 0

    for pat in time_regexes:
        for match in re.finditer(pat, text, re.IGNORECASE):
            match_len = match.end() - match.start()
            # We prefer longer, more comprehensive matches
            if match_len > best_len:
                best_len = match_len
                best_match = (match.start(), match.end())

    return best_match


def parse_clock_time(
    text: str, default_hour: int = 9, default_minute: int = 0
) -> Tuple[int, int, bool]:
    """
    Extracts hour (0-23) and minute (0-59) from text, taking into account:
    - Period markers: صبح, عصر, بعد از ظهر, شب, ظهر, نیمه شب, بامداد, am, pm.
    - Fractions: و نیم (30m), و ربع (15m).
    - 24h formats: 19:30, 08:00.
    Returns: (hour, minute, has_explicit_time)
    """
    has_explicit_time = False
    hour = default_hour
    minute = default_minute

    # Detect period of day
    period = None
    for pattern, p_name in DAY_PERIOD_PATTERNS:
        if pattern.search(text):
            period = p_name
            break

    # Look for HH:MM format
    hh_mm = re.search(r"\b(\d{1,2}):(\d{2})\b", text)
    if hh_mm:
        hour = int(hh_mm.group(1))
        minute = int(hh_mm.group(2))
        has_explicit_time = True
    elif "ساعت" in text:
        h_match = re.search(r"ساعت\s*(\d{1,2})\b", text)
        if h_match:
            hour = int(h_match.group(1))
            has_explicit_time = True
    elif period:
        # e.g., 7 صبح, 8 شب, 5 عصر, 7 am
        h_match = re.search(
            r"\b(\d{1,2})\s*(?:صبح|عصر|بعد\s*از\s*ظهر|بعدازظهر|غروب|شب|ظهر|am|pm)\b",
            text,
            re.IGNORECASE,
        )
        if not h_match:
            h_match = re.search(
                r"\b(?:صبح|عصر|شب|ظهر)\s*(\d{1,2})\b", text, re.IGNORECASE
            )
        if h_match:
            hour = int(h_match.group(1))
            has_explicit_time = True

    # Check for fractions
    if has_explicit_time or "ساعت" in text:
        if "نیم" in text:
            minute = 30
        elif "ربع" in text:
            minute = 15

    # Adjust hour based on period
    if has_explicit_time:
        if period in [PERIOD_AFTERNOON, PERIOD_EVENING, PERIOD_NIGHT]:
            if hour < 12:
                hour += 12
        elif period == PERIOD_NOON:
            if hour < 12:
                hour = 12
        elif period == PERIOD_MIDNIGHT:
            if hour == 12:
                hour = 0
        elif period == PERIOD_MORNING:
            if hour == 12:
                hour = 0
        elif not period:
            # Smart default when period is not specified:
            # If hour <= 6, it is usually evening (e.g. ساعت ۵ -> ۱۷:۰۰, ساعت ۶ -> ۱۸:۰۰)
            # unless context implies otherwise.
            if 1 <= hour <= 6:
                hour += 12

    return hour, minute, has_explicit_time


def parse_reminder(
    raw_input: str,
    now: Optional[datetime] = None,
    tz_name: str = "Asia/Tehran",
) -> ParseResult:
    """
    Main parser entry point. Parses raw input message into a ParseResult.
    """
    tz = pytz.timezone(tz_name)
    if now is None:
        now = datetime.now(tz)
    elif now.tzinfo is None:
        now = tz.localize(now)
    else:
        now = now.astimezone(tz)

    task_part, time_part = split_task_and_time(raw_input)
    if not time_part:
        # If no time part was separated, default to 1 hour from now
        target_dt = now + timedelta(hours=1)
        return ParseResult(
            task=task_part or "یادآوری",
            remind_at=target_dt,
            remind_at_utc=target_dt.astimezone(pytz.UTC),
            recurrence_type="none",
            recurrence_rule=None,
            original_time_expr="",
            calendar_type="relative",
        )

    t_norm = normalize_text(time_part).lower()

    # 1. Check Special & Relative times
    # E.g. ۱۰ دقیقه دیگه, ۲ ساعت بعد, نیم ساعت دیگه, یک ربع بعد
    for pat, delta_val, unit in SPECIAL_RELATIVE_PATTERNS:
        if pat.search(t_norm):
            if unit == "دقیقه":
                target_dt = now + timedelta(minutes=delta_val)
            else:
                target_dt = now + timedelta(hours=delta_val)
            return ParseResult(
                task=task_part or "یادآوری",
                remind_at=target_dt,
                remind_at_utc=target_dt.astimezone(pytz.UTC),
                recurrence_type="none",
                recurrence_rule=None,
                original_time_expr=time_part,
                calendar_type="relative",
            )

    rel_match = RELATIVE_PATTERN.search(t_norm)
    if rel_match and ("دیگه" in t_norm or "بعد" in t_norm or "later" in t_norm):
        amount = float(rel_match.group(1))
        unit_str = rel_match.group(2).lower()
        if any(u in unit_str for u in ["دقیقه", "min"]):
            delta = timedelta(minutes=amount)
        elif any(u in unit_str for u in ["ساعت", "hour"]):
            delta = timedelta(hours=amount)
        elif any(u in unit_str for u in ["روز", "day"]):
            delta = timedelta(days=amount)
        elif any(u in unit_str for u in ["هفته", "week"]):
            delta = timedelta(weeks=amount)
        elif any(u in unit_str for u in ["ثانیه", "sec"]):
            delta = timedelta(seconds=amount)
        else:
            delta = timedelta(hours=amount)

        target_dt = now + delta
        return ParseResult(
            task=task_part or "یادآوری",
            remind_at=target_dt,
            remind_at_utc=target_dt.astimezone(pytz.UTC),
            recurrence_type="none",
            recurrence_rule=None,
            original_time_expr=time_part,
            calendar_type="relative",
        )

    # 2. Check Recurrence (تکرار و تناوب)
    # Daily
    if RECURRENCE_DAILY.search(t_norm):
        hour, minute, _ = parse_clock_time(t_norm, default_hour=9, default_minute=0)
        target_time = time(hour, minute)
        target_dt = tz.localize(datetime.combine(now.date(), target_time))
        if target_dt <= now:
            target_dt += timedelta(days=1)
        return ParseResult(
            task=task_part or "یادآوری",
            remind_at=target_dt,
            remind_at_utc=target_dt.astimezone(pytz.UTC),
            recurrence_type="daily",
            recurrence_rule={"hour": hour, "minute": minute},
            original_time_expr=time_part,
            calendar_type="time_only",
        )

    # Even days (روزهای زوج: شنبه=5, دوشنبه=0, چهارشنبه=2)
    if RECURRENCE_EVEN_DAYS.search(t_norm):
        hour, minute, _ = parse_clock_time(t_norm, default_hour=9, default_minute=0)
        target_time = time(hour, minute)
        even_weekdays = [5, 0, 2]  # Sat, Mon, Wed
        # Find next occurrence among even days
        target_dt = find_next_weekday_occurrence(now, even_weekdays, target_time, tz)
        return ParseResult(
            task=task_part or "یادآوری",
            remind_at=target_dt,
            remind_at_utc=target_dt.astimezone(pytz.UTC),
            recurrence_type="even_days",
            recurrence_rule={
                "hour": hour,
                "minute": minute,
                "weekdays": even_weekdays,
            },
            original_time_expr=time_part,
            calendar_type="time_only",
        )

    # Odd days (روزهای فرد: یکشنبه=6, سه‌شنبه=1, پنج‌شنبه=3)
    if RECURRENCE_ODD_DAYS.search(t_norm):
        hour, minute, _ = parse_clock_time(t_norm, default_hour=9, default_minute=0)
        target_time = time(hour, minute)
        odd_weekdays = [6, 1, 3]  # Sun, Tue, Thu
        target_dt = find_next_weekday_occurrence(now, odd_weekdays, target_time, tz)
        return ParseResult(
            task=task_part or "یادآوری",
            remind_at=target_dt,
            remind_at_utc=target_dt.astimezone(pytz.UTC),
            recurrence_type="odd_days",
            recurrence_rule={"hour": hour, "minute": minute, "weekdays": odd_weekdays},
            original_time_expr=time_part,
            calendar_type="time_only",
        )

    # Weekly
    if RECURRENCE_WEEKLY.search(t_norm) or (
        re.search(r"\bهر\b", t_norm) and any(re.search(rf"\b{w}\b", t_norm) for w in WEEKDAY_MAP)
    ):
        hour, minute, _ = parse_clock_time(t_norm, default_hour=9, default_minute=0)
        target_time = time(hour, minute)
        # Find weekday
        matched_weekday = None
        for w_name, w_code in WEEKDAY_MAP.items():
            if re.search(rf"\b{w_name}\b", t_norm):
                matched_weekday = w_code
                break
        if matched_weekday is None:
            matched_weekday = now.weekday()

        target_dt = find_next_weekday_occurrence(
            now, [matched_weekday], target_time, tz
        )
        return ParseResult(
            task=task_part or "یادآوری",
            remind_at=target_dt,
            remind_at_utc=target_dt.astimezone(pytz.UTC),
            recurrence_type="weekly",
            recurrence_rule={
                "hour": hour,
                "minute": minute,
                "weekday": matched_weekday,
            },
            original_time_expr=time_part,
            calendar_type="time_only",
        )

    # Monthly
    if RECURRENCE_MONTHLY.search(t_norm):
        hour, minute, _ = parse_clock_time(t_norm, default_hour=9, default_minute=0)
        # Extract day of month if present (e.g. هر ماه ۲۵ ام)
        d_match = re.search(r"\b(\d{1,2})\b", t_norm)
        target_day = int(d_match.group(1)) if d_match else 1
        jnow = jdatetime.datetime.fromgregorian(datetime=now)
        # Schedule next occurrence in Jalali calendar
        j_year = jnow.year
        j_month = jnow.month
        target_time = time(hour, minute)
        try:
            jdt = jdatetime.datetime(
                j_year, j_month, target_day, hour, minute, tzinfo=tz
            )
            gdt = jdt.togregorian()
            if gdt.tzinfo is None:
                gdt = tz.localize(gdt)
            if gdt <= now:
                if j_month == 12:
                    j_year += 1
                    j_month = 1
                else:
                    j_month += 1
                jdt = jdatetime.datetime(
                    j_year, j_month, target_day, hour, minute, tzinfo=tz
                )
                gdt = tz.localize(jdt.togregorian())
        except Exception:
            gdt = now + timedelta(days=30)

        return ParseResult(
            task=task_part or "یادآوری",
            remind_at=gdt,
            remind_at_utc=gdt.astimezone(pytz.UTC),
            recurrence_type="monthly",
            recurrence_rule={"day": target_day, "hour": hour, "minute": minute},
            original_time_expr=time_part,
            calendar_type="jalali",
        )

    # 3. Check Specific Gregorian Dates
    # E.g. 25 October, 25 اکتبر, 15th Nov, 2026-10-25
    g_month = None
    g_month_name = None
    for name, month_num in GREGORIAN_MONTHS.items():
        if re.search(rf"\b{name}\b", t_norm, re.IGNORECASE):
            g_month = month_num
            g_month_name = name
            break

    # Numeric Gregorian date format: YYYY-MM-DD or YYYY/MM/DD (where YYYY > 1900)
    num_greg = re.search(r"\b(20\d{2})[-/](\d{1,2})[-/](\d{1,2})\b", t_norm)
    if num_greg:
        year = int(num_greg.group(1))
        month = int(num_greg.group(2))
        day = int(num_greg.group(3))
        hour, minute, _ = parse_clock_time(t_norm, default_hour=9, default_minute=0)
        target_dt = tz.localize(datetime(year, month, day, hour, minute))
        return ParseResult(
            task=task_part or "یادآوری",
            remind_at=target_dt,
            remind_at_utc=target_dt.astimezone(pytz.UTC),
            recurrence_type="none",
            recurrence_rule=None,
            original_time_expr=time_part,
            calendar_type="gregorian",
            is_past_warning=(target_dt <= now),
        )

    if g_month:
        pat_to_search = rf"\b(\d{{1,2}})\s*(?:st|nd|rd|th)?\s*{g_month_name}\b|\b{g_month_name}\s*(\d{{1,2}})\b"
        d_match = re.search(pat_to_search, t_norm, re.IGNORECASE)
        day = (
            int(d_match.group(1) or d_match.group(2))
            if d_match and (d_match.group(1) or d_match.group(2))
            else 1
        )
        # Extract year if present
        y_match = re.search(r"\b(20\d{2})\b", t_norm)
        year = int(y_match.group(1)) if y_match else now.year
        hour, minute, _ = parse_clock_time(t_norm, default_hour=9, default_minute=0)
        try:
            target_dt = tz.localize(datetime(year, g_month, day, hour, minute))
            # If year was not specified and date has already passed this year, advance to next year
            if not y_match and target_dt <= now:
                target_dt = tz.localize(datetime(year + 1, g_month, day, hour, minute))
        except ValueError:
            target_dt = now + timedelta(days=1)

        return ParseResult(
            task=task_part or "یادآوری",
            remind_at=target_dt,
            remind_at_utc=target_dt.astimezone(pytz.UTC),
            recurrence_type="none",
            recurrence_rule=None,
            original_time_expr=time_part,
            calendar_type="gregorian",
            is_past_warning=(target_dt <= now),
        )

    # 4. Check Jalali Dates
    # E.g. ۲۵ مهر ماه, ۲۵ مهر, اول آبان, 1405/07/25
    j_month = None
    j_month_name = None
    for name, month_num in JALALI_MONTHS.items():
        if re.search(rf"\b{name}\b", t_norm):
            j_month = month_num
            j_month_name = name
            break

    # Numeric Jalali format: 140X/MM/DD
    num_jalali = re.search(r"\b(1[34]\d{2})[-/](\d{1,2})[-/](\d{1,2})\b", t_norm)
    if num_jalali:
        j_year = int(num_jalali.group(1))
        j_month = int(num_jalali.group(2))
        j_day = int(num_jalali.group(3))
        hour, minute, _ = parse_clock_time(t_norm, default_hour=9, default_minute=0)
        jdt = jdatetime.datetime(j_year, j_month, j_day, hour, minute)
        target_dt = tz.localize(jdt.togregorian())
        return ParseResult(
            task=task_part or "یادآوری",
            remind_at=target_dt,
            remind_at_utc=target_dt.astimezone(pytz.UTC),
            recurrence_type="none",
            recurrence_rule=None,
            original_time_expr=time_part,
            calendar_type="jalali",
            is_past_warning=(target_dt <= now),
        )

    if j_month:
        jnow = jdatetime.datetime.fromgregorian(datetime=now)
        # Extract day number
        d_match = re.search(rf"\b(\d{{1,2}})\s*{j_month_name}\b|\b{j_month_name}\s*(\d{{1,2}})\b", t_norm)
        day = (
            int(d_match.group(1) or d_match.group(2))
            if d_match and (d_match.group(1) or d_match.group(2))
            else 1
        )
        # Extract year if present
        y_match = re.search(r"\b(1[34]\d{2})\b", t_norm)
        j_year = int(y_match.group(1)) if y_match else jnow.year
        hour, minute, _ = parse_clock_time(t_norm, default_hour=9, default_minute=0)

        try:
            jdt = jdatetime.datetime(j_year, j_month, day, hour, minute)
            target_dt = tz.localize(jdt.togregorian())
            # If year was not specified and date has passed this year, advance to next Jalali year
            if not y_match and target_dt <= now:
                jdt = jdatetime.datetime(j_year + 1, j_month, day, hour, minute)
                target_dt = tz.localize(jdt.togregorian())
        except ValueError:
            target_dt = now + timedelta(days=1)

        return ParseResult(
            task=task_part or "یادآوری",
            remind_at=target_dt,
            remind_at_utc=target_dt.astimezone(pytz.UTC),
            recurrence_type="none",
            recurrence_rule=None,
            original_time_expr=time_part,
            calendar_type="jalali",
            is_past_warning=(target_dt <= now),
        )

    # 5. Check Weekdays
    # E.g. پنج شنبه ۷ بعد از ظهر, این پنج‌شنبه ساعت ۸
    matched_weekday = None
    for w_name, w_code in WEEKDAY_MAP.items():
        if re.search(rf"\b{w_name}\b", t_norm):
            matched_weekday = w_code
            break

    if matched_weekday is not None:
        hour, minute, _ = parse_clock_time(t_norm, default_hour=9, default_minute=0)
        target_time = time(hour, minute)
        target_dt = find_next_weekday_occurrence(now, [matched_weekday], target_time, tz)
        return ParseResult(
            task=task_part or "یادآوری",
            remind_at=target_dt,
            remind_at_utc=target_dt.astimezone(pytz.UTC),
            recurrence_type="none",
            recurrence_rule=None,
            original_time_expr=time_part,
            calendar_type="time_only",
        )

    # 6. Check Specific Day Offsets (امروز, امشب, فردا, پس فردا)
    day_offset = None
    for day_word, offset in DAY_OFFSETS.items():
        if re.search(rf"\b{day_word}\b", t_norm):
            day_offset = offset
            break

    hour, minute, has_explicit_time = parse_clock_time(t_norm, default_hour=9, default_minute=0)
    target_time = time(hour, minute)

    if day_offset is not None:
        target_date = (now + timedelta(days=day_offset)).date()
        target_dt = tz.localize(datetime.combine(target_date, target_time))
        # Past time warning if user explicitly said 'امروز ساعت ...' and it's past
        is_past = (target_dt <= now)
        if is_past and day_offset == 0:
            # Advance to tomorrow or mark warning
            target_dt += timedelta(days=1)
        return ParseResult(
            task=task_part or "یادآوری",
            remind_at=target_dt,
            remind_at_utc=target_dt.astimezone(pytz.UTC),
            recurrence_type="none",
            recurrence_rule=None,
            original_time_expr=time_part,
            calendar_type="time_only",
            is_past_warning=is_past,
        )

    # 7. Clock Time Only (ساعت ۷ عصر, ساعت ۱۹:۰۰, etc.)
    if has_explicit_time or "ساعت" in t_norm:
        target_dt = tz.localize(datetime.combine(now.date(), target_time))
        # If the time has already passed today, schedule for tomorrow
        if target_dt <= now:
            target_dt += timedelta(days=1)
        return ParseResult(
            task=task_part or "یادآوری",
            remind_at=target_dt,
            remind_at_utc=target_dt.astimezone(pytz.UTC),
            recurrence_type="none",
            recurrence_rule=None,
            original_time_expr=time_part,
            calendar_type="time_only",
        )

    # Fallback default: 1 hour from now
    target_dt = now + timedelta(hours=1)
    return ParseResult(
        task=task_part or "یادآوری",
        remind_at=target_dt,
        remind_at_utc=target_dt.astimezone(pytz.UTC),
        recurrence_type="none",
        recurrence_rule=None,
        original_time_expr=time_part,
        calendar_type="relative",
    )


def find_next_weekday_occurrence(
    now: datetime, target_weekdays: List[int], target_time: time, tz: pytz.BaseTzInfo
) -> datetime:
    """
    Finds the earliest upcoming occurrence of one of the target_weekdays at target_time.
    target_weekdays uses Python weekday numbering: Mon=0, Tue=1, Wed=2, Thu=3, Fri=4, Sat=5, Sun=6.
    """
    for day_offset in range(0, 8):
        candidate_date = (now + timedelta(days=day_offset)).date()
        if candidate_date.weekday() in target_weekdays:
            candidate_dt = tz.localize(datetime.combine(candidate_date, target_time))
            if candidate_dt > now:
                return candidate_dt
    # Fallback
    return tz.localize(datetime.combine((now + timedelta(days=7)).date(), target_time))
