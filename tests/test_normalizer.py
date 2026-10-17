from bot.parser.normalizer import (
    normalize_digits,
    normalize_characters,
    convert_word_numbers_in_time_context,
    normalize_text,
)


def test_normalize_digits():
    assert normalize_digits("۰۱۲۳۴۵۶۷۸۹") == "0123456789"
    assert normalize_digits("٠١٢٣٤٥٦٧٨٩") == "0123456789"
    assert normalize_digits("ساعت ۷:۳۰") == "ساعت 7:30"


def test_normalize_characters():
    assert normalize_characters("كتاب يادآوري") == "کتاب یادآوری"
    assert normalize_characters("پنج‌شنبه") == "پنج شنبه"
    assert normalize_characters("بعد‌از‌ظهر") == "بعد از ظهر"


def test_word_numbers_in_time_context():
    assert convert_word_numbers_in_time_context("ساعت هفت") == "ساعت 7"
    assert convert_word_numbers_in_time_context("دو ساعت بعد") == "2 ساعت بعد"
    # Make sure weekdays are NOT converted to digits
    assert convert_word_numbers_in_time_context("پنج شنبه") == "پنج شنبه"
    assert convert_word_numbers_in_time_context("سه شنبه") == "سه شنبه"


def test_normalize_text():
    raw = "يادآوري جلسه + پنج‌شنبه ساعت ٧ بعد‌از‌ظهر"
    res = normalize_text(raw)
    assert "یادآوری" in res
    assert "پنج شنبه" in res
    assert "7" in res
    assert "بعد از ظهر" in res
