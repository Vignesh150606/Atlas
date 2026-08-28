"""Phase 12 (ARCH-TZ) tests.

Covers app/utils/timezone.py directly, plus the three concrete places the
pre-Phase-12 UTC-only assumption produced wrong answers for a non-UTC user:
ReminderService.create_from_text (due_at), ReminderService._advance_recurrence
(recurring due_at), PromptBuilder._format_datetime ("now"), and
RoutineService.get_active_around (routine time-of-day matching). See
CLAUDE.md's "Strategic Direction" section and docs/MASTER_PLAN.md for the
original finding.
"""
import pytest
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.utils.timezone import resolve_zone, to_local, to_utc, local_now, local_day_bounds, weekday_name
from app.core.config import settings
from app.prompts.prompt_builder import PromptBuilder
from app.services.reminder_service import ReminderService
from app.services.routine_service import RoutineService
from app.schemas.routine import RoutineCreate
from app.models.reminder import RecurrenceType


# --- app/utils/timezone.py, direct ------------------------------------

def test_resolve_zone_falls_back_on_none():
    zone = resolve_zone(None)
    assert zone.key == settings.DEFAULT_TIMEZONE


def test_resolve_zone_falls_back_on_blank_and_unrecognized():
    assert resolve_zone("").key == settings.DEFAULT_TIMEZONE
    assert resolve_zone("Not/AZone").key == settings.DEFAULT_TIMEZONE


def test_resolve_zone_accepts_a_real_iana_name():
    assert resolve_zone("America/New_York").key == "America/New_York"


def test_to_local_and_to_utc_are_inverses_for_ist():
    # 2026-08-28 02:30 UTC == 2026-08-28 08:00 IST (UTC+5:30, no DST)
    utc_value = datetime(2026, 8, 28, 2, 30)
    local_value = to_local(utc_value, "Asia/Kolkata")
    assert local_value == datetime(2026, 8, 28, 8, 0)
    assert to_utc(local_value, "Asia/Kolkata") == utc_value


def test_to_local_and_to_utc_round_trip_across_a_dst_transition():
    # 2026-03-08 is the US spring-forward date (2am -> 3am EST->EDT).
    # A reference well before it (EST, UTC-5) and one well after it
    # (EDT, UTC-4) must convert with *different* offsets - proves this is
    # a real zoneinfo-backed conversion, not a fixed-offset constant.
    before_dst = datetime(2026, 3, 1, 12, 0)  # UTC
    after_dst = datetime(2026, 3, 15, 12, 0)  # UTC
    local_before = to_local(before_dst, "America/New_York")
    local_after = to_local(after_dst, "America/New_York")
    assert local_before.hour == 7  # EST: UTC-5
    assert local_after.hour == 8  # EDT: UTC-4
    assert to_utc(local_before, "America/New_York") == before_dst
    assert to_utc(local_after, "America/New_York") == after_dst


def test_local_now_returns_naive_wall_clock():
    now = local_now("Asia/Kolkata")
    assert now.tzinfo is None


def test_local_day_bounds_span_exactly_24_hours_and_bracket_reference():
    reference = datetime(2026, 8, 28, 20, 0)  # 2026-08-29 01:30 IST
    start_utc, end_utc = local_day_bounds("Asia/Kolkata", reference)
    assert (end_utc - start_utc).total_seconds() == 24 * 3600
    assert start_utc <= reference < end_utc
    # The bounds are the local midnight-to-midnight for 2026-08-29 IST.
    assert to_local(start_utc, "Asia/Kolkata") == datetime(2026, 8, 29, 0, 0)


def test_local_day_bounds_defaults_reference_to_now():
    start_utc, end_utc = local_day_bounds("Asia/Kolkata")
    assert start_utc < end_utc


def test_weekday_name_on_local_value():
    assert weekday_name(datetime(2026, 8, 28)) == "Friday"


# --- PromptBuilder: renders local time, not UTC ------------------------

def test_prompt_builder_renders_local_time_for_client_timezone():
    from datetime import timezone as dt_timezone
    fixed_now_utc = datetime(2026, 8, 28, 2, 30, tzinfo=dt_timezone.utc)  # 08:00 IST
    ctx = PromptBuilder.build(
        history=[], current_message="Hi", now=fixed_now_utc, client_timezone="Asia/Kolkata"
    )
    assert "08:00" in ctx.system_prompt
    assert "Friday" in ctx.system_prompt
    assert "Asia/Kolkata" in ctx.system_prompt


def test_prompt_builder_falls_back_to_default_timezone_when_none_given():
    from datetime import timezone as dt_timezone
    fixed_now_utc = datetime(2026, 8, 28, 2, 30, tzinfo=dt_timezone.utc)
    ctx = PromptBuilder.build(history=[], current_message="Hi", now=fixed_now_utc)
    # No client_timezone passed -> falls back to settings.DEFAULT_TIMEZONE
    # (Asia/Kolkata), so this still renders 08:00, not UTC's 02:30.
    assert "08:00" in ctx.system_prompt


# --- ReminderService.create_from_text: the actual daily-driver bug -----

@pytest.mark.asyncio
async def test_create_from_text_resolves_tomorrow_against_local_reference(db_session: AsyncSession):
    """The concrete bug from docs/MASTER_PLAN.md: 'remind me tomorrow at
    8am' from an IST caller must fire at 8am IST (02:30 UTC the next day),
    not 8am UTC (1:30pm IST)."""
    service = ReminderService(db_session)
    # 2026-08-05 10:00 UTC = 2026-08-05 15:30 IST (still Wednesday in IST).
    reference_utc = datetime(2026, 8, 5, 10, 0, 0)
    reminder = await service.create_from_text(
        "remind me to submit the assignment tomorrow at 8am",
        reference_time=reference_utc,
        timezone="Asia/Kolkata",
    )
    assert reminder is not None
    # Tomorrow (IST) at 8am IST == 2026-08-06 02:30 UTC.
    assert reminder.due_at == datetime(2026, 8, 6, 2, 30)
    assert reminder.timezone == "Asia/Kolkata"


@pytest.mark.asyncio
async def test_create_from_text_default_utc_zone_is_unchanged(db_session: AsyncSession):
    """Identity-transform guarantee: the default zone is still literally
    'UTC', so every pre-Phase-12 caller/test keeps its exact behavior."""
    service = ReminderService(db_session)
    reference = datetime(2026, 8, 5, 10, 0, 0)
    reminder = await service.create_from_text(
        "remind me to submit the assignment tomorrow", reference_time=reference
    )
    assert reminder.due_at == datetime(2026, 8, 6, 9, 0)  # DEFAULT_REMINDER_HOUR, unchanged


@pytest.mark.asyncio
async def test_create_from_text_near_local_midnight_picks_correct_local_day(db_session: AsyncSession):
    """The precise failure mode: a reference just after local midnight but
    still the *previous* UTC day must resolve 'tomorrow' against the local
    calendar day, not the UTC one."""
    service = ReminderService(db_session)
    # 2026-08-05 19:00 UTC = 2026-08-06 00:30 IST (i.e. local day is
    # already Aug 6, while the UTC day is still Aug 5).
    reference_utc = datetime(2026, 8, 5, 19, 0, 0)
    reminder = await service.create_from_text(
        "remind me to call mom tomorrow at 9am", reference_time=reference_utc, timezone="Asia/Kolkata"
    )
    assert reminder is not None
    # "tomorrow" from local Aug 6 is Aug 7, 9am IST = 03:30 UTC.
    assert reminder.due_at == datetime(2026, 8, 7, 3, 30)


# --- ReminderService._advance_recurrence: recurring reminders ----------

@pytest.mark.asyncio
async def test_recurring_reminder_advances_in_local_time(db_session: AsyncSession):
    service = ReminderService(db_session)
    reference_utc = datetime(2026, 8, 5, 10, 0, 0)
    reminder = await service.create_from_text(
        "remind me to take my medicine every day at 8am",
        reference_time=reference_utc,
        timezone="Asia/Kolkata",
    )
    assert reminder.recurrence == RecurrenceType.DAILY.value
    # First occurrence: today (IST) at 8am IST = 02:30 UTC.
    assert reminder.due_at == datetime(2026, 8, 5, 2, 30)

    completed = await service.complete(reminder.id)
    # Completed "now" isn't controlled by this test (uses utc_now()), but
    # the *time of day* of the next occurrence must still read 8am IST
    # (02:30 UTC), not 8am UTC - proving the advance happened in local time.
    assert completed.due_at.hour == 2
    assert completed.due_at.minute == 30


# --- RoutineService.get_active_around: local time-of-day matching ------

@pytest.mark.asyncio
async def test_routine_matching_backward_compatible_without_zone(db_session: AsyncSession):
    """zone=None (the default) keeps exact pre-Phase-12 behavior: an
    explicit, already-local reference is compared directly, unconverted -
    this is what every existing test in test_routine_service.py relies on."""
    service = RoutineService(db_session)
    await service.create(RoutineCreate(name="Morning", time_of_day="07:15", days_of_week=[0, 1, 2, 3, 4]))
    reference = datetime(2026, 8, 5, 7, 30)  # Wednesday, naive, treated as local
    matches = await service.get_active_around(reference, window_minutes=30)
    assert "Morning" in {r.name for r in matches}


@pytest.mark.asyncio
async def test_routine_matching_converts_utc_reference_with_zone(db_session: AsyncSession):
    """The real caller shape: a genuine UTC reference (e.g. utc_now())
    plus an explicit zone must be converted before comparison - a routine
    at 07:15 IST should NOT match a UTC reference of 07:15 (which is
    12:45 IST, well outside a 30-minute window), but SHOULD match the
    correct UTC instant for 07:15 IST (01:45 UTC)."""
    service = RoutineService(db_session)
    await service.create(RoutineCreate(name="Morning", time_of_day="07:15", days_of_week=[]))

    utc_reference_same_clock_digits = datetime(2026, 8, 5, 7, 15)  # 07:15 UTC = 12:45 IST
    no_match = await service.get_active_around(
        utc_reference_same_clock_digits, window_minutes=30, zone="Asia/Kolkata"
    )
    assert "Morning" not in {r.name for r in no_match}

    correct_utc_instant = datetime(2026, 8, 5, 1, 45)  # 01:45 UTC = 07:15 IST
    match = await service.get_active_around(correct_utc_instant, window_minutes=15, zone="Asia/Kolkata")
    assert "Morning" in {r.name for r in match}
