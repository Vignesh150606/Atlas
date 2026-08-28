"""Phase 10: ReminderService - the real reminder architecture the mission
brief (section 2) asks for, on top of `Reminder` (app/models/reminder.py)
and the deterministic parser (app/nlp/datetime_parser.py).

Two creation paths, deliberately kept explicit rather than merged into
one "smart" constructor:
- `create_from_text` - chat-driven ("remind me to X [when]"); reuses
  `MemoryExtractor.parse_reminder`'s task/when split (the exact same
  regex ReminderSkill's Phase 9 confirmation used - see that module) so
  the task text extracted here can never drift from what the skill
  reports back to the user, then resolves the "when" fragment with
  `parse_datetime_expression`.
- `create` - direct/API creation with an already-resolved `due_at` (no
  text parsing at all) - what a real date/time picker UI would call.
"""
from datetime import datetime, timedelta, timezone as dt_timezone
from app.utils.time import utc_now
from app.utils.timezone import to_local, to_utc
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.reminder_repository import ReminderRepository
from app.models.reminder import Reminder, ReminderStatus, RecurrenceType
from app.memory.memory_extractor import MemoryExtractor
from app.nlp.datetime_parser import parse_datetime_expression, next_weekday_on_or_after
from app.schemas.reminder import ReminderCreate, ReminderUpdate


class ReminderService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repository = ReminderRepository(db)

    async def create(self, data: ReminderCreate, source: str = "api", conversation_id: Optional[str] = None) -> Reminder:
        payload = {
            "title": data.title.strip(),
            "due_at": data.due_at,
            "timezone": data.timezone,
            "recurrence": data.recurrence.value,
            "recurrence_days": data.recurrence_days,
            "notes": data.notes,
            "source": source,
            "conversation_id": conversation_id,
            "status": ReminderStatus.PENDING.value,
        }
        return await self.repository.create(payload)

    async def create_from_text(
        self,
        text: str,
        reference_time: Optional[datetime] = None,
        timezone: str = "UTC",
        conversation_id: Optional[str] = None,
        source: str = "chat",
    ) -> Optional[Reminder]:
        """Returns None only if the text doesn't even match "remind me to
        ..." at all (see MemoryExtractor.parse_reminder) - a genuinely
        unrelated message, not this service's concern. A recognized
        reminder phrase with an unparseable "when" fragment still creates
        a Reminder (due_at=None, raw_when_text preserved) rather than
        being silently dropped - "I heard the task but not when" is more
        honest and more useful than discarding the whole request.

        `MemoryExtractor.parse_reminder` only ever splits off a trailing
        "at/by/on <when>" clause (see that function's docstring), so a
        recurrence word appearing *before* it - "take my medicine every
        day at 8am" splits into task="take my medicine every day",
        due_date="8am" - would lose "every day" if only the due_date
        fragment were parsed for scheduling. Recombining task+due_date
        into one string and re-parsing it with
        `parse_datetime_expression` (which finds recurrence/date/time
        patterns via independent searches over the whole string, not a
        left-to-right single pass) sees "every day" and "8am" together
        regardless of which half of parse_reminder's split they landed
        in, and `ParsedSchedule.remaining_text` then gives back a clean
        title with every recognized phrase removed - see
        app/nlp/datetime_parser.py's docstring.

        Phase 12 (ARCH-TZ): `parse_datetime_expression` does pure date/time
        arithmetic ("tomorrow" = reference + 1 day) with no zone awareness
        of its own - it just trusts whatever frame `reference` is in. Before
        this phase, `reference` (UTC) was fed straight in and the result was
        stored as-is, so "tomorrow at 8am" from an IST caller silently
        became 8am *UTC* = 1:30pm IST. The fix: convert `reference` (UTC) to
        the caller's local wall-clock time via `timezone` before parsing, so
        "tomorrow"/"8am"/etc resolve against the user's actual calendar day
        and clock, then convert the resulting due_at back to UTC before
        storing (every DateTime column stays naive-UTC - see
        app/utils/time.py). For the default zone "UTC" this round-trip is
        the identity transform, which is why every pre-Phase-12 test below
        keeps passing unchanged.
        """
        parsed = MemoryExtractor.parse_reminder(text)
        if not parsed:
            return None

        reference_utc = reference_time or utc_now()
        reference = to_local(reference_utc, timezone)
        combined = parsed["task"]
        if parsed.get("due_date"):
            combined = f"{combined} {parsed['due_date']}"

        schedule = parse_datetime_expression(combined, reference)

        if schedule.matched:
            # schedule.due_at is in the *local* frame (it was computed
            # against the local `reference` above) - convert back to UTC
            # before it ever reaches storage or the repository, so
            # Reminder.due_at stays naive-UTC like every other DateTime
            # column in this codebase.
            due_at = to_utc(schedule.due_at, timezone) if schedule.due_at else None
            recurrence = schedule.recurrence
            recurrence_days = schedule.recurrence_days
            when_text = schedule.matched_text
            title = schedule.remaining_text or parsed["task"]
        else:
            due_at = None
            recurrence = RecurrenceType.NONE
            recurrence_days = []
            when_text = parsed.get("due_date")
            title = parsed["task"]

        payload = {
            "title": title,
            "due_at": due_at,
            "raw_when_text": when_text,
            "timezone": timezone,
            "recurrence": recurrence.value,
            "recurrence_days": recurrence_days,
            "status": ReminderStatus.PENDING.value,
            "source": source,
            "conversation_id": conversation_id,
        }
        return await self.repository.create(payload)

    async def get(self, reminder_id: str) -> Optional[Reminder]:
        return await self.repository.get(reminder_id)

    async def list(
        self, status: Optional[str] = None, skip: int = 0, limit: int = 100
    ) -> List[Reminder]:
        return await self.repository.get_filtered(status=status, skip=skip, limit=limit)

    async def update(self, reminder_id: str, data: ReminderUpdate) -> Optional[Reminder]:
        reminder = await self.repository.get(reminder_id)
        if not reminder:
            return None
        update_data = data.model_dump(exclude_unset=True)
        if "recurrence" in update_data and update_data["recurrence"] is not None:
            update_data["recurrence"] = update_data["recurrence"].value
        if "status" in update_data and update_data["status"] is not None:
            update_data["status"] = update_data["status"].value
        return await self.repository.update(reminder, update_data)

    async def complete(self, reminder_id: str) -> Optional[Reminder]:
        """Non-recurring: marks COMPLETED, done. Recurring: this
        occurrence is done, so due_at advances to the next occurrence and
        the reminder stays PENDING - a recurring reminder is never
        "completed" in the terminal sense, only individual firings are
        (see Reminder.completed_at, which tracks the *last* completed
        occurrence, not a final state)."""
        reminder = await self.repository.get(reminder_id)
        if not reminder:
            return None
        now = utc_now()
        if reminder.recurrence == RecurrenceType.NONE.value:
            return await self.repository.update(reminder, {
                "status": ReminderStatus.COMPLETED.value,
                "completed_at": now,
            })
        next_due = self._advance_recurrence(reminder, now)
        return await self.repository.update(reminder, {
            "due_at": next_due,  # already converted back to UTC inside _advance_recurrence
            "completed_at": now,
            "status": ReminderStatus.PENDING.value,
        })

    async def cancel(self, reminder_id: str) -> Optional[Reminder]:
        reminder = await self.repository.get(reminder_id)
        if not reminder:
            return None
        return await self.repository.update(reminder, {"status": ReminderStatus.CANCELLED.value})

    async def delete(self, reminder_id: str) -> Optional[Reminder]:
        return await self.repository.delete(reminder_id)

    async def get_upcoming(self, within: timedelta, reference: Optional[datetime] = None) -> List[Reminder]:
        return await self.repository.get_due_within(reference or utc_now(), within)

    async def get_overdue(self, reference: Optional[datetime] = None) -> List[Reminder]:
        return await self.repository.get_overdue(reference or utc_now())

    @staticmethod
    def _advance_recurrence(reminder: Reminder, now: datetime) -> datetime:
        """Computes the next occurrence strictly after `now` (not just
        after the old due_at - a reminder completed late shouldn't
        immediately re-fire for a slot that's already passed).

        Phase 12 (ARCH-TZ): `now` arrives as UTC (utc_now(), from
        complete() above) and `reminder.due_at` is stored as UTC too - but
        "what calendar day is today" and "what clock time does this
        reminder repeat at" are both *local* concepts to the user. Doing
        this arithmetic directly in UTC is the same class of bug as
        create_from_text's pre-Phase-12 behavior: near local midnight, the
        UTC calendar day and the local calendar day disagree, so "the next
        occurrence" could silently land a day off. Converting `now` and the
        stored due_at into `reminder.timezone` before the date/time math,
        then converting the result back to UTC before returning, fixes
        this the same way create_from_text was fixed. For reminder.timezone
        == "UTC" (every pre-Phase-12 reminder, and the default for new
        ones unless a client says otherwise) this round-trip is the
        identity transform.
        """
        zone = reminder.timezone
        local_now = to_local(now, zone)
        recurrence = reminder.recurrence
        days = reminder.recurrence_days or []
        base_date = local_now.date()
        time_of_day = to_local(reminder.due_at, zone).time() if reminder.due_at else local_now.time()

        if recurrence == RecurrenceType.DAILY.value:
            next_date = base_date + timedelta(days=1)
        elif recurrence == RecurrenceType.WEEKDAYS.value:
            next_date = next_weekday_on_or_after(base_date + timedelta(days=1), 0) \
                if (base_date + timedelta(days=1)).weekday() >= 5 else base_date + timedelta(days=1)
        elif recurrence in (RecurrenceType.WEEKLY.value, RecurrenceType.CUSTOM.value) and days:
            # Next matching weekday strictly after today, picking the
            # earliest of possibly-multiple recurrence_days (CUSTOM).
            candidates = [next_weekday_on_or_after(base_date, d, strictly_after=True) for d in days]
            next_date = min(candidates)
        else:
            next_date = base_date + timedelta(days=1)

        next_local = datetime.combine(next_date, time_of_day)
        return to_utc(next_local, zone)
