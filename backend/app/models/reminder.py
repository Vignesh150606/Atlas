"""Phase 10: real Reminder domain model.

Pre-Phase-10, "remind me to X" only ever produced a generic `Memory` row
(memory_type=TASK, structured_data={"task": ..., "due_date": <free text>})
via `MemoryExtractor` rule 5 - useful as a searchable memory of what was
said, but not an actionable, schedulable, completable object: no real
`due_at` (raw text like "Friday" was stored verbatim, never resolved - see
`docs/Phase9_KnownLimitations.md` #4), no way to mark it done, no way to
list "what's due soon", nothing a Daily Briefing or a proactive-suggestion
service could query cheaply.

This is a genuinely new, dedicated resource - not a duplicate of Memory.
`MemoryExtractor` rule 5 is deliberately left completely unchanged (see
`app/memory/memory_extractor.py` - Phase 10 does not touch it): a chat
message like "remind me to call John tomorrow" still produces a Memory
row (passive record of "the user said this") *and*, via `ReminderSkill`
(see `app/skills/reminder_skill.py`), a real `Reminder` row (active,
schedulable, completable) when a db session is available. Two rows, two
different purposes, no disagreement possible about which one is
authoritative for what: Memory answers "what did the user tell me?",
Reminder answers "what does ATLAS still need to remind the user about?".
"""
import uuid
from enum import Enum
from sqlalchemy import Column, String, Text, DateTime, JSON
from app.models.base import TimestampModel


class ReminderStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class RecurrenceType(str, Enum):
    """Deliberately a small, closed set of deterministic recurrence shapes
    (see `app/nlp/datetime_parser.py`) rather than a full RRULE grammar -
    matches this codebase's "deterministic, explainable heuristics over a
    general-purpose parser" philosophy (see e.g. `app/retrieval/ranking.py`,
    `app/services/memory_lifecycle_service.py`). CUSTOM covers an explicit
    weekday set that isn't "every day" or "every weekday" (e.g. "every
    Tuesday and Thursday") via `Reminder.recurrence_days`.
    """
    NONE = "none"
    DAILY = "daily"
    WEEKLY = "weekly"
    WEEKDAYS = "weekdays"  # Mon-Fri
    CUSTOM = "custom"


class Reminder(TimestampModel):
    __tablename__ = "reminders"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    title = Column(String, nullable=False)
    # Resolved, schedulable datetime (naive, interpreted in `timezone`
    # below) - None only when the source text genuinely had no
    # recognizable date/time and the caller chose to save the reminder
    # anyway (better than silently discarding the request - see
    # ReminderService.create_from_text).
    due_at = Column(DateTime, nullable=True, index=True)
    # The original, unparsed "when" fragment ("Friday", "in two hours") -
    # kept verbatim so the UI/LLM can always show what the user actually
    # said, even when due_at is a resolved guess.
    raw_when_text = Column(String, nullable=True)
    timezone = Column(String, nullable=False, default="UTC")

    recurrence = Column(String, nullable=False, default=RecurrenceType.NONE.value, index=True)
    # ISO weekday ints (0=Monday ... 6=Sunday), only meaningful for
    # WEEKLY/CUSTOM recurrence - see app/nlp/datetime_parser.py.
    recurrence_days = Column(JSON, nullable=False, default=list)

    status = Column(String, nullable=False, default=ReminderStatus.PENDING.value, index=True)
    completed_at = Column(DateTime, nullable=True)

    # "chat" (created via ReminderSkill from a message) or "api" (created
    # directly, e.g. from an Android "Add Reminder" screen with a real
    # date/time picker - see app/schemas/reminder.py::ReminderCreate).
    source = Column(String, nullable=False, default="chat", index=True)
    conversation_id = Column(String, nullable=True, index=True)  # best-effort trace back to origin; not a FK (Conversation.id is an int PK on a different lifecycle - see note in reminder_service.py)

    notes = Column(Text, nullable=True)
