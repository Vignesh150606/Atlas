"""Phase 10: tests for app/nlp/datetime_parser.py - the deterministic
first layer of the reminder system's date/time understanding.
"""
from datetime import datetime
from app.nlp.datetime_parser import parse_datetime_expression, DEFAULT_REMINDER_HOUR, TONIGHT_DEFAULT_HOUR
from app.models.reminder import RecurrenceType

# Wednesday, 2026-08-05, 10:00 - a fixed reference point so every test is
# deterministic regardless of when it's actually run.
REF = datetime(2026, 8, 5, 10, 0, 0)


def test_tomorrow_defaults_to_default_hour():
    result = parse_datetime_expression("tomorrow", REF)
    assert result.matched
    assert result.due_at == datetime(2026, 8, 6, DEFAULT_REMINDER_HOUR, 0)
    assert result.has_explicit_time is False
    assert result.recurrence == RecurrenceType.NONE


def test_tomorrow_with_explicit_time():
    result = parse_datetime_expression("tomorrow at 7pm", REF)
    assert result.due_at == datetime(2026, 8, 6, 19, 0)
    assert result.has_explicit_time is True


def test_today_at_explicit_time_in_the_past_is_not_rolled():
    # Explicit "today" is left as literally requested even if odd -
    # only bare time-only expressions get rolled forward.
    result = parse_datetime_expression("today at 7am", REF)  # REF is 10:00
    assert result.due_at == datetime(2026, 8, 5, 7, 0)


def test_bare_time_only_rolls_to_tomorrow_if_already_passed():
    result = parse_datetime_expression("at 7am", REF)  # REF is 10:00, 7am already passed
    assert result.due_at == datetime(2026, 8, 6, 7, 0)


def test_bare_time_only_same_day_if_still_upcoming():
    result = parse_datetime_expression("at 7 PM", REF)
    assert result.due_at == datetime(2026, 8, 5, 19, 0)


def test_tonight_defaults_to_evening_hour():
    result = parse_datetime_expression("tonight", REF)
    assert result.due_at == datetime(2026, 8, 5, TONIGHT_DEFAULT_HOUR, 0)
    assert result.has_explicit_time is False


def test_in_two_hours():
    result = parse_datetime_expression("in two hours", REF)
    assert result.due_at == datetime(2026, 8, 5, 12, 0)
    assert result.has_explicit_time is True


def test_in_30_minutes_numeric():
    result = parse_datetime_expression("in 30 minutes", REF)
    assert result.due_at == datetime(2026, 8, 5, 10, 30)


def test_in_a_week():
    result = parse_datetime_expression("in a week", REF)
    assert result.due_at == datetime(2026, 8, 12, 10, 0)


def test_bare_weekday_this_week_if_upcoming():
    # REF is Wednesday 2026-08-05; Friday is upcoming this week.
    result = parse_datetime_expression("Friday", REF)
    assert result.due_at == datetime(2026, 8, 7, DEFAULT_REMINDER_HOUR, 0)


def test_bare_weekday_same_day_counts_as_match():
    result = parse_datetime_expression("Wednesday", REF)  # REF itself is Wednesday
    assert result.due_at.date() == REF.date()


def test_next_weekday_skips_this_week_even_if_matching():
    result = parse_datetime_expression("next Wednesday", REF)  # REF itself is Wednesday
    assert result.due_at.date() == datetime(2026, 8, 12).date()


def test_this_weekday_prefix():
    result = parse_datetime_expression("this Friday", REF)
    assert result.due_at.date() == datetime(2026, 8, 7).date()


def test_every_day_recurrence():
    result = parse_datetime_expression("every day at 8am", REF)
    assert result.recurrence == RecurrenceType.DAILY
    assert result.due_at == datetime(2026, 8, 5, 8, 0)


def test_every_monday_recurrence():
    result = parse_datetime_expression("every Monday", REF)
    assert result.recurrence == RecurrenceType.WEEKLY
    assert result.recurrence_days == [0]
    # Next Monday on/after Wed 2026-08-05 is 2026-08-10.
    assert result.due_at == datetime(2026, 8, 10, DEFAULT_REMINDER_HOUR, 0)


def test_every_monday_at_9am():
    result = parse_datetime_expression("every Monday at 9am", REF)
    assert result.due_at == datetime(2026, 8, 10, 9, 0)
    assert result.has_explicit_time is True


def test_every_weekday_recurrence():
    result = parse_datetime_expression("every weekday at 7am", REF)
    assert result.recurrence == RecurrenceType.WEEKDAYS
    assert result.recurrence_days == [0, 1, 2, 3, 4]
    # REF (Wed) is itself a weekday, so today.
    assert result.due_at == datetime(2026, 8, 5, 7, 0)


def test_every_weekday_from_a_weekend_reference_rolls_to_monday():
    saturday_ref = datetime(2026, 8, 8, 10, 0)  # Saturday
    result = parse_datetime_expression("every weekday at 7am", saturday_ref)
    assert result.due_at.date() == datetime(2026, 8, 10).date()  # next Monday


def test_every_tuesday_and_thursday_is_custom_recurrence():
    result = parse_datetime_expression("every Tuesday and Thursday at 6pm", REF)
    assert result.recurrence == RecurrenceType.CUSTOM
    assert result.recurrence_days == [1, 3]
    # REF is Wed 2026-08-05. Of the two recurrence days, Thursday
    # 2026-08-06 is only one day away and Tuesday 2026-08-11 is six days
    # away - the nearer of the two (Thursday) must win. Anchoring to
    # recurrence_days[0] (Tuesday) unconditionally was a bug: it skipped
    # the very next occurrence in favor of one nearly a week later.
    assert result.due_at == datetime(2026, 8, 6, 18, 0)


def test_every_monday_and_friday_from_a_thursday_anchors_to_friday():
    # A second, independent case for the same nearest-day rule: from a
    # Thursday, Friday (1 day away) must beat Monday (4 days away).
    thursday_ref = datetime(2026, 8, 6, 10, 0)  # Thursday
    result = parse_datetime_expression("every Monday and Friday at 6pm", thursday_ref)
    assert result.recurrence == RecurrenceType.CUSTOM
    assert result.recurrence_days == [0, 4]
    assert result.due_at == datetime(2026, 8, 7, 18, 0)  # Friday, not the following Monday


def test_noon_and_midnight_keywords():
    assert parse_datetime_expression("tomorrow at noon", REF).due_at == datetime(2026, 8, 6, 12, 0)
    assert parse_datetime_expression("tomorrow at midnight", REF).due_at == datetime(2026, 8, 6, 0, 0)


def test_unrecognized_text_returns_unmatched():
    result = parse_datetime_expression("submit the report", REF)
    assert result.matched is False
    assert result.due_at is None


def test_empty_text_returns_unmatched():
    result = parse_datetime_expression("", REF)
    assert result.matched is False


def test_am_pm_boundary_hours():
    assert parse_datetime_expression("tomorrow at 12am", REF).due_at.time().hour == 0
    assert parse_datetime_expression("tomorrow at 12pm", REF).due_at.time().hour == 12


def test_remaining_text_strips_bare_trailing_date_word():
    result = parse_datetime_expression("call mom tomorrow", REF)
    assert result.remaining_text == "call mom"
    assert result.matched_text == "tomorrow"


def test_remaining_text_strips_recurrence_and_time():
    result = parse_datetime_expression("take my medicine every day at 8am", REF)
    assert result.remaining_text == "take my medicine"
    assert "every day" in result.matched_text
    assert "8am" in result.matched_text


def test_remaining_text_strips_offset_expression():
    result = parse_datetime_expression("call mom in two hours", REF)
    assert result.remaining_text == "call mom"
    assert result.matched_text == "in two hours"


def test_remaining_text_equals_input_when_unmatched():
    result = parse_datetime_expression("submit the report", REF)
    assert result.matched is False
    assert result.remaining_text == "submit the report"
