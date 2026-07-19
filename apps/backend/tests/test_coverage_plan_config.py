from decimal import Decimal

from app.services.coverage_plan_config import (
    MAX_LESSON_MINUTES,
    MAX_LESSON_WORDS,
    WORDS_PER_MINUTE,
    content_type_multiplier,
    count_words,
    words_to_minutes,
)


def test_words_per_minute_and_limit_are_consistent():
    assert MAX_LESSON_WORDS == WORDS_PER_MINUTE * MAX_LESSON_MINUTES


def test_count_words_handles_none_and_empty():
    assert count_words(None) == 0
    assert count_words("") == 0
    assert count_words("uma frase com cinco palavras aqui") == 6


def test_words_to_minutes_rounds_half_up():
    assert words_to_minutes(0) == Decimal("0")
    assert words_to_minutes(WORDS_PER_MINUTE) == Decimal("1.00")
    assert words_to_minutes(WORDS_PER_MINUTE * 10) == Decimal("10.00")


def test_content_type_multiplier_known_and_unknown():
    assert content_type_multiplier("procedure") > content_type_multiplier("quotation")
    assert content_type_multiplier("this-type-does-not-exist") == 1.4
