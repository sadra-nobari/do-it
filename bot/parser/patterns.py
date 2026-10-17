import re
from typing import Dict, List, Tuple

# Jalali Months
JALALI_MONTHS: Dict[str, int] = {
    "فروردین": 1,
    "اردیبهشت": 2,
    "خرداد": 3,
    "تیر": 4,
    "مرداد": 5,
    "شهریور": 6,
    "مهر": 7,
    "آبان": 8,
    "آذر": 9,
    "دی": 10,
    "بهمن": 11,
    "اسفند": 12,
}

# Gregorian Months (English & Transliterated Persian)
GREGORIAN_MONTHS: Dict[str, int] = {
    # English
    "january": 1,
    "jan": 1,
    "february": 2,
    "feb": 2,
    "march": 3,
    "mar": 3,
    "april": 4,
    "apr": 4,
    "may": 5,
    "june": 6,
    "jun": 6,
    "july": 7,
    "jul": 7,
    "august": 8,
    "aug": 8,
    "september": 9,
    "sep": 9,
    "sept": 9,
    "october": 10,
    "oct": 10,
    "november": 11,
    "nov": 11,
    "december": 12,
    "dec": 12,
    # Persian Transliteration
    "ژانویه": 1,
    "فوریه": 2,
    "مارس": 3,
    "آوریل": 4,
    "مه": 5,
    "می": 5,
    "ژوئن": 6,
    "ژوئیه": 7,
    "جولای": 7,
    "اوت": 8,
    "آگوست": 8,
    "سپتامبر": 9,
    "اکتبر": 10,
    "نوامبر": 11,
    "دسامبر": 12,
}

# Python weekday mapping: Monday=0, Tuesday=1, Wednesday=2, Thursday=3, Friday=4, Saturday=5, Sunday=6
WEEKDAY_MAP: Dict[str, int] = {
    # Persian (ordered from longest to shortest to avoid partial matches on 'شنبه')
    "چهار شنبه": 2,
    "چهارشنبه": 2,
    "یک شنبه": 6,
    "یکشنبه": 6,
    "پنج شنبه": 3,
    "سه شنبه": 1,
    "دو شنبه": 0,
    "دوشنبه": 0,
    "جمعه": 4,
    "شنبه": 5,
    # English
    "wednesday": 2,
    "thursday": 3,
    "saturday": 5,
    "tuesday": 1,
    "monday": 0,
    "friday": 4,
    "sunday": 6,
    "mon": 0,
    "tue": 1,
    "wed": 2,
    "thu": 3,
    "fri": 4,
    "sat": 5,
    "sun": 6,
}

# Days relative to today
DAY_OFFSETS: Dict[str, int] = {
    "امروز": 0,
    "امشب": 0,
    "فردا": 1,
    "پس فردا": 2,
    "پسفردا": 2,
    "today": 0,
    "tonight": 0,
    "tomorrow": 1,
}

# Day periods (ordered: 'بعد از ظهر' before 'ظهر')
PERIOD_MORNING = "morning"  # صبح
PERIOD_AFTERNOON = "afternoon"  # عصر / بعد از ظهر
PERIOD_NOON = "noon"  # ظهر
PERIOD_EVENING = "evening"  # غروب
PERIOD_NIGHT = "night"  # شب
PERIOD_MIDNIGHT = "midnight"  # نیمه شب / بامداد

DAY_PERIOD_PATTERNS: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"\b(?:عصر|بعد\s*از\s*ظهر|بعدازظهر|pm)\b", re.IGNORECASE), PERIOD_AFTERNOON),
    (re.compile(r"\b(?:ظهر)\b", re.IGNORECASE), PERIOD_NOON),
    (re.compile(r"\b(?:صبح|بامداد|am)\b", re.IGNORECASE), PERIOD_MORNING),
    (re.compile(r"\b(?:غروب)\b", re.IGNORECASE), PERIOD_EVENING),
    (re.compile(r"\b(?:شب|امشب)\b", re.IGNORECASE), PERIOD_NIGHT),
    (re.compile(r"\b(?:نیمه\s*شب)\b", re.IGNORECASE), PERIOD_MIDNIGHT),
]

# Recurrence patterns
RECURRENCE_DAILY = re.compile(r"\b(?:هر\s*روز|روزانه|every\s*day|daily)\b", re.IGNORECASE)
RECURRENCE_WEEKLY = re.compile(r"\b(?:هر\s*هفته|هفتگی|every\s*week|weekly)\b", re.IGNORECASE)
RECURRENCE_MONTHLY = re.compile(r"\b(?:هر\s*ماه|ماهانه|every\s*month|monthly)\b", re.IGNORECASE)
RECURRENCE_EVEN_DAYS = re.compile(r"\b(?:روزهای\s*زوج|روز\s*های\s*زوج)\b", re.IGNORECASE)
RECURRENCE_ODD_DAYS = re.compile(r"\b(?:روزهای\s*فرد|روز\s*های\s*فرد)\b", re.IGNORECASE)

# Relative time units
RELATIVE_PATTERN = re.compile(
    r"(\d+(?:\.\d+)?)\s*(ثانیه|دقیقه|ساعت|روز|هفته|ماه|sec(?:ond)?s?|min(?:ute)?s?|hours?|days?|weeks?)\s*(?:دیگه|بعد|دیگر|آینده|later)?",
    re.IGNORECASE,
)

# Fraction words in relative or time context
# e.g., نیم ساعت دیگه -> 30 mins, یک ربع دیگه -> 15 mins
SPECIAL_RELATIVE_PATTERNS = [
    (re.compile(r"\b(?:یک\s*)?نیم\s*ساعت\s*(?:دیگه|بعد|دیگر)?\b"), 30, "دقیقه"),
    (re.compile(r"\b(?:یک\s*)?ربع\s*ساعت\s*(?:دیگه|بعد|دیگر)?\b"), 15, "دقیقه"),
    (re.compile(r"\b(?:یک\s*)?ربع\s*(?:دیگه|بعد|دیگر)\b"), 15, "دقیقه"),
    (re.compile(r"\b(?:یک\s*)?ساعت\s*(?:دیگه|بعد|دیگر)\b"), 1, "ساعت"),
]
