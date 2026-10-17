import re
from typing import Dict

# Map Persian and Arabic digits to ASCII
PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
ARABIC_DIGITS = "٠١٢٣٤٥٦٧٨٩"
ASCII_DIGITS = "0123456789"

DIGIT_MAP = {ord(p): ord(a) for p, a in zip(PERSIAN_DIGITS, ASCII_DIGITS)}
DIGIT_MAP.update({ord(p): ord(a) for p, a in zip(ARABIC_DIGITS, ASCII_DIGITS)})

# Persian word numbers to integer values
PERSIAN_WORDS_TO_NUM: Dict[str, int] = {
    "یک": 1,
    "اول": 1,
    "یکم": 1,
    "دو": 2,
    "دوم": 2,
    "سه": 3,
    "سوم": 3,
    "چهار": 4,
    "چهارم": 4,
    "پنج": 5,
    "پنجم": 5,
    "شش": 6,
    "شیش": 6,
    "ششم": 6,
    "هفت": 7,
    "هفتم": 7,
    "هشت": 8,
    "هشتم": 8,
    "نه": 9,
    "نهم": 9,
    "ده": 10,
    "دهم": 10,
    "یازده": 11,
    "یازدهم": 11,
    "دوازده": 12,
    "دوازدهم": 12,
    "سیزده": 13,
    "سیزدهم": 13,
    "چهارده": 14,
    "چهاردهم": 14,
    "پانزده": 15,
    "پونزده": 15,
    "پانزدهم": 15,
    "شانزده": 16,
    "شونزده": 16,
    "شانزدهم": 16,
    "هفده": 17,
    "هفدهم": 17,
    "هجده": 18,
    "هجدهم": 18,
    "نوزده": 19,
    "نوزدهم": 19,
    "بیست": 20,
    "بیستم": 20,
    "سی": 30,
    "سی ام": 30,
    "سی‌ام": 30,
    "چهل": 40,
    "پنجاه": 50,
}

# Ordinal suffix patterns like 25ام, 25 ام, 25th
ORDINAL_PATTERN = re.compile(r"(\d+)\s*(?:ام|th|st|nd|rd)\b", re.IGNORECASE)


def normalize_digits(text: str) -> str:
    """Converts Persian and Arabic digits to standard ASCII digits."""
    if not text:
        return ""
    return text.translate(DIGIT_MAP)


def normalize_characters(text: str) -> str:
    """Normalizes Persian characters: fixes Arabic kaf/yeh, collapses spaces and handles ZWNJ."""
    if not text:
        return ""
    # Arabic to Persian chars
    text = text.replace("ك", "ک").replace("ي", "ی").replace("ى", "ی").replace("ة", "ه")
    # Replace non-breaking spaces
    text = text.replace("\xa0", " ")
    # Replace ZWNJ with space in compound time words for easier regex matching
    # e.g., پنج‌شنبه -> پنج شنبه, بعد‌از‌ظهر -> بعد از ظهر
    text = text.replace("\u200c", " ")
    # Collapse multiple whitespaces
    text = re.sub(r"[ \t]+", " ", text).strip()
    return text


def convert_word_numbers_in_time_context(text: str) -> str:
    """
    Replaces Persian word numbers in time contexts with digits.
    E.g.: 'ساعت هفت' -> 'ساعت 7', 'دو ساعت بعد' -> '2 ساعت بعد'.
    """
    normalized = text
    # First remove ordinal suffixes like '۲۵ ام' -> '25'
    normalized = ORDINAL_PATTERN.sub(r"\1", normalized)

    # Convert compound word numbers like 'بیست و پنج' -> 25, 'سی و یک' -> 31
    for tens_word, tens_val in [("بیست", 20), ("سی", 30), ("چهل", 40), ("پنجاه", 50)]:
        for units_word, units_val in PERSIAN_WORDS_TO_NUM.items():
            if units_val < 10 and not units_word.endswith("م"):
                compound = f"{tens_word} و {units_word}"
                normalized = re.sub(
                    rf"\b{compound}\b", str(tens_val + units_val), normalized
                )

    # Convert single word numbers (do NOT convert if followed by شنبه, e.g. پنج شنبه, سه شنبه, چهار شنبه)
    for word, num in sorted(
        PERSIAN_WORDS_TO_NUM.items(), key=lambda x: len(x[0]), reverse=True
    ):
        # Match as whole word, not followed by 'شنبه'
        pattern = rf"(?<![\w]){word}(?![\w])(?!\s*شنبه)"
        normalized = re.sub(pattern, str(num), normalized)

    return normalized


def normalize_text(text: str) -> str:
    """Applies all normalizations to a given text."""
    if not text:
        return ""
    t = normalize_digits(text)
    t = normalize_characters(t)
    t = convert_word_numbers_in_time_context(t)
    return t
