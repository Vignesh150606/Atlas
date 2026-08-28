"""Phase 10: deterministic relative-date/time parser for the Reminder
system (mission brief section 2: "The system must correctly interpret
absolute dates, relative dates, times, recurring schedules").

Same architectural philosophy as the rest of this codebase's cognitive
layer (see `CLAUDE.md`'s "Architecture philosophy" #1 and
`app/retrieval/ranking.py`'s weight comment): a small set of explainable,
regex/table-driven rules, not a general-purpose NLP date library and not
an LLM call. This is deliberately the *first layer* the mission brief
asks for - `ReminderService` (see `app/services/reminder_service.py`) is
the seam where an optional, explicitly-flagged LLM-assist fallback could
sit for phrases this parser doesn't recognize, without this module itself
needing to change (see that module's docstring for the honest current
state: the fallback hook exists, nothing calls an LLM by default).

Every branch tracks the character span(s) it matched in the input, so
`ParsedSchedule.remaining_text` can hand back the input with the
recognized date/time/recurrence phrase removed - this is what lets
`ReminderService.create_from_text` turn "call mom tomorrow" into title
"call mom" instead of leaving "tomorrow" stuck in the task text (see
that module's docstring for why this matters: `MemoryExtractor.
parse_reminder` only ever splits off a trailing "at/by/on ..." clause,
so a bare trailing date word like "tomorrow" is still sitting in the
task text when it reaches this parser).

Deliberately NOT attempted here (documented, not silently missing):
- Timezone-aware arithmetic beyond passing an IANA-name-or-offset string
  through verbatim on the Reminder row. `reference` is a naive datetime
  the caller has already localized; see ReminderService for the current
  single-user assumption (see docs/Phase10_KnownLimitations.md).
- A general RRULE grammar. RecurrenceType (app/models/reminder.py) is a
  small closed set (NONE/DAILY/WEEKLY/WEEKDAYS/CUSTOM) - "every Tuesday
  and Thursday" is CUSTOM with two recurrence_days, not an arbitrary rule.
- Resolving ambiguous bare weekday mentions against a stated cutoff time
  ("Friday" said at 11pm Thursday - is that ~13 hours away or a week
  away?) beyond the single, documented "today counts if the weekday
  matches and hasn't fully passed" rule below.
"""
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, time as dt_time, date as dt_date
from typing import List, Optional, Tuple

from app.models.reminder import RecurrenceType

Span = Tuple[int, int]

# When only a date (no time-of-day) is recognized, a reminder needs *some*
# concrete time to actually fire/sort by. 9am is a deliberately documented,
# unsurprising default (same "explainable over clever" reasoning as e.g.
# MemoryLifecycleService's DEFAULT_STALE_AFTER_DAYS) - callers can always
# see this happened via ParsedSchedule.has_explicit_time=False.
DEFAULT_REMINDER_HOUR = 9
# "tonight" gets its own, more specific default than the generic 9am.
TONIGHT_DEFAULT_HOUR = 20

_WEEKDAY_NAMES = {
    "monday": 0, "mon": 0,
    "tuesday": 1, "tue": 1, "tues": 1,
    "wednesday": 2, "wed": 2,
    "thursday": 3, "thu": 3, "thurs": 3,
    "friday": 4, "fri": 4,
    "saturday": 5, "sat": 5,
    "sunday": 6, "sun": 6,
}
_WEEKDAY_PATTERN = "|".join(sorted(_WEEKDAY_NAMES, key=len, reverse=True))

_NUMBER_WORDS = {
    "a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
    "twelve": 12, "couple": 2, "few": 3,
}

_IN_OFFSET_PATTERN = re.compile(
    r"\bin\s+(\d+|" + "|".join(_NUMBER_WORDS) + r")\s+"
    r"(minute|minutes|min|mins|hour|hours|hr|hrs|day|days|week|weeks)\b",
    re.IGNORECASE,
)

_NEXT_OR_THIS_WEEKDAY_PATTERN = re.compile(
    r"\b(next|this)?\s*(" + _WEEKDAY_PATTERN + r")\b", re.IGNORECASE
)

_EVERY_WEEKDAY_LIST_PATTERN = re.compile(
    r"\bevery\s+((?:" + _WEEKDAY_PATTERN + r")(?:\s*(?:,|and)\s*(?:" + _WEEKDAY_PATTERN + r"))*)\b",
    re.IGNORECASE,
)
_DAILY_PATTERN = re.compile(r"\bevery\s*day\b|\bdaily\b|\beach\s*day\b", re.IGNORECASE)
_WEEKDAYS_PATTERN = re.compile(r"\bevery\s*weekday\b|\bon\s*weekdays\b|\bweekdays\b", re.IGNORECASE)
_EVERY_WEEK_PATTERN = re.compile(r"\bevery\s*week\b", re.IGNORECASE)

_AT_TIME_PATTERN = re.compile(
    r"\bat\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", re.IGNORECASE
)
_BARE_TIME_PATTERN = re.compile(
    r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b", re.IGNORECASE
)
_NOON_PATTERN = re.compile(r"\bnoon\b", re.IGNORECASE)
_MIDNIGHT_PATTERN = re.compile(r"\bmidnight\b", re.IGNORECASE)

_TOMORROW_PATTERN = re.compile(r"\btomorrow\b", re.IGNORECASE)
_TONIGHT_PATTERN = re.compile(r"\btonight\b", re.IGNORECASE)
_TODAY_PATTERN = re.compile(r"\btoday\b", re.IGNORECASE)

_LEFTOVER_CONNECTOR_PATTERN = re.compile(r"^(and|on|at|by)\b[\s,]*|[\s,]*\b(and|on|at|by)$", re.IGNORECASE)


@dataclass
class ParsedSchedule:
    """Result of parsing a "when" fragment (or a full "task + when"
    string - see remaining_text below). `matched` is False only when
    nothing at all was recognized - callers should fall back to storing
    the raw text with no due_at rather than guessing.
    """
    due_at: Optional[datetime] = None
    recurrence: RecurrenceType = RecurrenceType.NONE
    recurrence_days: List[int] = field(default_factory=list)
    has_explicit_time: bool = False
    matched: bool = False
    # Input text with every recognized date/time/recurrence phrase
    # removed and whitespace collapsed - e.g. parsing "call mom tomorrow"
    # gives remaining_text="call mom". Equal to the original input when
    # matched=False (nothing was removed).
    remaining_text: str = ""
    # The concatenation of exactly the phrase(s) that were recognized and
    # removed to produce remaining_text (e.g. "tomorrow", "every Monday at 9am").
    matched_text: str = ""


def _parse_number(token: str) -> int:
    token_lower = token.lower()
    if token_lower in _NUMBER_WORDS:
        return _NUMBER_WORDS[token_lower]
    return int(token)


def _extract_time(text: str) -> Tuple[Optional[dt_time], bool, Optional[Span]]:
    """Returns (time_of_day, matched, span). Tries "at H(:MM)(am/pm)"
    first (more specific lead-in), then a bare "H(:MM)am/pm", then
    noon/midnight. 12-hour math: 12am -> 0, 12pm -> 12, otherwise +12 for pm.
    """
    match = _AT_TIME_PATTERN.search(text) or _BARE_TIME_PATTERN.search(text)
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2)) if match.group(2) else 0
        meridiem = (match.group(3) or "").lower()
        if meridiem == "pm" and hour != 12:
            hour += 12
        elif meridiem == "am" and hour == 12:
            hour = 0
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return dt_time(hour, minute), True, match.span()
        return None, False, None
    match = _NOON_PATTERN.search(text)
    if match:
        return dt_time(12, 0), True, match.span()
    match = _MIDNIGHT_PATTERN.search(text)
    if match:
        return dt_time(0, 0), True, match.span()
    return None, False, None


def next_weekday_on_or_after(reference_date: dt_date, target_weekday: int, strictly_after: bool = False) -> dt_date:
    """Nearest date >= reference_date (or > reference_date if
    strictly_after) that falls on `target_weekday` (0=Monday).
    """
    days_ahead = (target_weekday - reference_date.weekday()) % 7
    if days_ahead == 0 and strictly_after:
        days_ahead = 7
    return reference_date + timedelta(days=days_ahead)


def _extract_recurrence(text: str) -> Tuple[RecurrenceType, List[int], Optional[Span]]:
    """Returns (recurrence_type, recurrence_days, span)."""
    match = _DAILY_PATTERN.search(text)
    if match:
        return RecurrenceType.DAILY, [], match.span()

    match = _WEEKDAYS_PATTERN.search(text)
    if match:
        return RecurrenceType.WEEKDAYS, [0, 1, 2, 3, 4], match.span()

    match = _EVERY_WEEKDAY_LIST_PATTERN.search(text)
    if match:
        tokens = re.split(r"\s*(?:,|and)\s*", match.group(1), flags=re.IGNORECASE)
        days = sorted({_WEEKDAY_NAMES[t.lower()] for t in tokens if t.lower() in _WEEKDAY_NAMES})
        recurrence = RecurrenceType.WEEKLY if len(days) == 1 else RecurrenceType.CUSTOM
        return recurrence, days, match.span()

    match = _EVERY_WEEK_PATTERN.search(text)
    if match:
        return RecurrenceType.WEEKLY, [], match.span()

    return RecurrenceType.NONE, [], None


def _strip_spans(text: str, spans: List[Optional[Span]]) -> Tuple[str, str]:
    """Returns (remaining_text, matched_text). Removes every non-None span
    from `text` (processed right-to-left so earlier offsets stay valid),
    collapses whitespace, and trims stray leading/trailing connector
    words ("at", "on", "by", "and") a removal can leave behind (e.g.
    "call mom at" after stripping a trailing "tomorrow" from "call mom
    at tomorrow" - not realistic English, but the same trimming also
    handles the very real "submit the report by" -> "submit the report"
    case for parse_reminder's own at/by/on split, which this function is
    also used to double-check via ReminderService)."""
    real_spans = [s for s in spans if s]
    matched_text = " ".join(text[start:end] for start, end in sorted(real_spans, key=lambda s: s[0]))
    remaining = text
    for start, end in sorted(real_spans, key=lambda s: s[0], reverse=True):
        remaining = remaining[:start] + " " + remaining[end:]
    remaining = re.sub(r"\s+", " ", remaining).strip()
    # Iterate: a removal can expose a new leading/trailing connector.
    previous = None
    while previous != remaining:
        previous = remaining
        remaining = _LEFTOVER_CONNECTOR_PATTERN.sub("", remaining).strip(" ,")
    return remaining, matched_text


def parse_datetime_expression(text: str, reference: datetime) -> ParsedSchedule:
    """Parse a natural-language string containing a date/time/recurrence
    expression (e.g. "tomorrow at 7pm", "every Monday", "in two hours",
    "Friday", or a longer string like "call mom tomorrow" where the
    expression is embedded) relative to `reference` (a naive datetime
    already localized to the caller's timezone - see ReminderService).
    Never raises: an unrecognized string returns
    `ParsedSchedule(matched=False, remaining_text=text)` rather than
    guessing.
    """
    if not text or not text.strip():
        return ParsedSchedule(remaining_text=(text or "").strip())
    raw = text.strip()

    # "in N <unit>" is a complete, self-sufficient offset - it fully
    # determines both date and time, so it's resolved first and returned
    # immediately rather than being combined with the date/time logic
    # below (a phrase like "in two hours at 5pm" is a contradiction, not
    # a combination worth supporting).
    offset_match = _IN_OFFSET_PATTERN.search(raw)
    if offset_match:
        amount = _parse_number(offset_match.group(1))
        unit = offset_match.group(2).lower()
        if unit.startswith("min"):
            delta = timedelta(minutes=amount)
        elif unit.startswith(("hour", "hr")):
            delta = timedelta(hours=amount)
        elif unit.startswith("day"):
            delta = timedelta(days=amount)
        else:  # week/weeks
            delta = timedelta(weeks=amount)
        remaining_text, matched_text = _strip_spans(raw, [offset_match.span()])
        return ParsedSchedule(
            due_at=reference + delta,
            recurrence=RecurrenceType.NONE,
            recurrence_days=[],
            has_explicit_time=True,
            matched=True,
            remaining_text=remaining_text,
            matched_text=matched_text,
        )

    recurrence, recurrence_days, recurrence_span = _extract_recurrence(raw)
    time_of_day, time_matched, time_span = _extract_time(raw)
    default_hour = DEFAULT_REMINDER_HOUR

    date_part: Optional[dt_date] = None
    date_span: Optional[Span] = None
    reference_date = reference.date()

    if recurrence in (RecurrenceType.WEEKLY, RecurrenceType.CUSTOM) and recurrence_days:
        # Anchor to the *nearest* upcoming recurrence day, not just the
        # first one in the (numerically sorted) list - for a single day
        # these are the same thing, but for CUSTOM's multiple days
        # picking recurrence_days[0] would always anchor to the lowest
        # weekday number (e.g. Monday) even when another listed day
        # falls sooner (e.g. "every Tuesday and Thursday" said on a
        # Wednesday must anchor to the next day, Thursday - not skip it
        # in favor of Tuesday nearly a week away). This mirrors
        # ReminderService._advance_recurrence's own min-of-candidates
        # logic for the same reason.
        date_part = min(next_weekday_on_or_after(reference_date, d) for d in recurrence_days)
    elif recurrence == RecurrenceType.DAILY:
        date_part = reference_date
    elif recurrence == RecurrenceType.WEEKDAYS:
        date_part = reference_date if reference_date.weekday() < 5 else next_weekday_on_or_after(reference_date, 0)
    elif recurrence == RecurrenceType.WEEKLY:  # "every week", no explicit weekday -> anchor to reference's weekday
        recurrence_days = [reference_date.weekday()]
        date_part = reference_date
    else:
        # Recurrence phrases (if any) don't imply a date_part of their own
        # beyond the branches above, so a plain date word can still be
        # checked for - and since recurrence is RecurrenceType.NONE
        # whenever we reach here, there's no risk of e.g. "every Monday"'s
        # "Monday" being double-counted by the weekday-date pattern below.
        match = _TOMORROW_PATTERN.search(raw)
        if match:
            date_part = reference_date + timedelta(days=1)
            date_span = match.span()
        else:
            match = _TONIGHT_PATTERN.search(raw)
            if match:
                date_part = reference_date
                default_hour = TONIGHT_DEFAULT_HOUR
                date_span = match.span()
            else:
                match = _TODAY_PATTERN.search(raw)
                if match:
                    date_part = reference_date
                    date_span = match.span()
                else:
                    match = _NEXT_OR_THIS_WEEKDAY_PATTERN.search(raw)
                    if match:
                        target = _WEEKDAY_NAMES[match.group(2).lower()]
                        strictly_after = (match.group(1) or "").lower() == "next"
                        date_part = next_weekday_on_or_after(reference_date, target, strictly_after=strictly_after)
                        date_span = match.span()

    if date_part is None and not time_matched and recurrence == RecurrenceType.NONE:
        return ParsedSchedule(matched=False, remaining_text=raw)

    if date_part is None:
        # Time-only expression ("remind me at 7pm") - anchor to today,
        # rolling to tomorrow if that time has already passed.
        date_part = reference_date

    hour, minute = (time_of_day.hour, time_of_day.minute) if time_of_day else (default_hour, 0)
    due_at = datetime.combine(date_part, dt_time(hour, minute))

    # Roll forward exactly one day for a same-day, time-only (no explicit
    # date word, non-recurring) expression whose time has already passed -
    # "remind me at 7pm" said at 9pm should mean tomorrow, not an
    # impossible past time today. Explicit-date expressions ("today at
    # 7am" said at 9pm) are left as the user's literal, if odd, request -
    # not silently reinterpreted. Recurring reminders are never rolled
    # here; ReminderService.complete_reminder advances their due_at
    # instead (see that module).
    if (
        recurrence == RecurrenceType.NONE
        and date_span is None
        and time_matched
        and due_at <= reference
    ):
        due_at += timedelta(days=1)

    remaining_text, matched_text = _strip_spans(raw, [recurrence_span, time_span, date_span])

    return ParsedSchedule(
        due_at=due_at,
        recurrence=recurrence,
        recurrence_days=recurrence_days,
        has_explicit_time=time_matched,
        matched=True,
        remaining_text=remaining_text,
        matched_text=matched_text,
    )
