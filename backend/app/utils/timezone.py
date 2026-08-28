"""Phase 12 (ARCH-TZ): timezone resolution and conversion helpers.

Every DateTime column in this codebase is naive and stores UTC (see
app/utils/time.py's docstring for why storage deliberately stays that way -
this module does NOT change that). What was missing was a rendering/
resolution layer: something that knows how to turn a UTC-naive value into
"8am in the user's timezone" and back, without ever making a stored value
timezone-aware.

Uses stdlib `zoneinfo` only - no new dependency. `zoneinfo` requires the
system tzdata database; on Windows dev machines this comes from the
`tzdata` PyPI package if the OS database isn't present (see
requirements.txt) - Linux/macOS deployment targets have it built in.

All functions here operate on *naive* datetimes on both sides: a naive
datetime is always interpreted as being in the timezone explicitly passed
alongside it (either the IANA zone name, or implicitly UTC for storage).
Nothing in this module ever returns a timezone-aware datetime - the
boundary between "naive-but-known-to-be-local" and "naive-but-known-to-be-UTC"
is the *caller's* responsibility, exactly as it already is for utc_now().
"""
from datetime import datetime, timezone as dt_timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from typing import Optional, Tuple

from app.core.config import settings


def resolve_zone(name: Optional[str]) -> ZoneInfo:
    """Resolves an IANA zone name to a ZoneInfo, falling back to
    settings.DEFAULT_TIMEZONE for None/blank/unrecognized input rather than
    raising - a malformed or missing client timezone should degrade to a
    sane default, not break the chat turn."""
    candidate = (name or "").strip() or settings.DEFAULT_TIMEZONE
    try:
        return ZoneInfo(candidate)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo(settings.DEFAULT_TIMEZONE)


def to_local(utc_naive: datetime, zone: Optional[str]) -> datetime:
    """Converts a naive UTC datetime (as stored on every model in this
    codebase) to a naive local datetime in the given zone. The returned
    value has no tzinfo - it is a local wall-clock reading, matching the
    naive-everywhere convention used throughout the rest of the app."""
    aware_utc = utc_naive.replace(tzinfo=dt_timezone.utc)
    aware_local = aware_utc.astimezone(resolve_zone(zone))
    return aware_local.replace(tzinfo=None)


def to_utc(local_naive: datetime, zone: Optional[str]) -> datetime:
    """Inverse of to_local: interprets a naive datetime as wall-clock time
    in the given zone and returns the equivalent naive UTC datetime, ready
    to store in a DateTime column."""
    aware_local = local_naive.replace(tzinfo=resolve_zone(zone))
    aware_utc = aware_local.astimezone(dt_timezone.utc)
    return aware_utc.replace(tzinfo=None)


def local_now(zone: Optional[str]) -> datetime:
    """Current wall-clock time in the given zone, naive. The counterpart to
    utc_now() for callers that need "what time does the user's clock read
    right now" rather than "what time is it in UTC right now"."""
    return datetime.now(resolve_zone(zone)).replace(tzinfo=None)


def local_day_bounds(zone: Optional[str], reference_utc: Optional[datetime] = None) -> Tuple[datetime, datetime]:
    """Returns (start_utc, end_utc): the UTC-naive bounds of the local
    calendar day containing `reference_utc` (or the current moment, if
    omitted), in the given zone. Used anywhere "today" needs to mean the
    user's today, not UTC's today - e.g. the daily briefing and proactive
    routine-time matching, both of which were previously off by up to the
    zone's UTC offset for a portion of every day.
    """
    from datetime import timedelta

    reference_utc = reference_utc if reference_utc is not None else datetime.now(dt_timezone.utc).replace(tzinfo=None)
    local_reference = to_local(reference_utc, zone)
    local_midnight = local_reference.replace(hour=0, minute=0, second=0, microsecond=0)
    local_next_midnight = local_midnight + timedelta(days=1)
    return to_utc(local_midnight, zone), to_utc(local_next_midnight, zone)


def weekday_name(local_naive: datetime) -> str:
    """Full weekday name (Monday=0 ... Sunday=6 per Python's convention) for
    a naive *local* datetime - i.e. call this on the output of to_local()/
    local_now(), never on a raw UTC value, or the reported weekday can be
    wrong near midnight."""
    return local_naive.strftime("%A")
