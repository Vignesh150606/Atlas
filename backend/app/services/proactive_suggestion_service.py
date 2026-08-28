"""Phase 10: Proactive Intelligence foundation (mission brief section 6).

Deliberately produces *suggestions only* - a list of small, deterministic
facts about the world ("this reminder is overdue", "this task has sat
untouched for 3 days") - never an instruction that gets auto-executed.
Nothing in this module calls the LLM, writes to the database, or fires a
device action; it is read-only, cheap, pure SQL-backed queries reusing
`ReminderRepository`/`TaskRepository`/`RoutineService`/
`MemoryLifecycleService` (see mission brief section 16: don't build a
second implementation of "what's overdue" - `ReminderRepository.
get_overdue`/`get_due_within` are the one definition, also used by
`DailyBriefingService`).

Performance (mission brief section 17): this is meant to be called
on-demand - when the Android app is foregrounded, or on a periodic
WorkManager job (e.g. every 15-30 minutes), NOT a tight backend polling
loop or a constant LLM call. There is no scheduler in this backend (no
Celery/APScheduler dependency) and Phase 10 deliberately doesn't add one
for this - ATLAS still has no iterative/background agent loop (see
CLAUDE.md's Architecture philosophy #2); this is a stateless query a
client asks for when it wants an answer, not a background process this
backend runs on its own initiative.
"""
from datetime import datetime, timedelta
from app.utils.time import utc_now
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.reminder_repository import ReminderRepository
from app.services.routine_service import RoutineService
from app.repositories.memory_repository import MemoryRepository
from app.models.memory import VerificationState
from app.schemas.briefing import ProactiveSuggestion, ProactiveSuggestionsResponse

DUE_SOON_WINDOW = timedelta(minutes=30)
STALE_MEMORY_SUGGESTION_THRESHOLD = 5  # only worth mentioning once there's a real backlog


class ProactiveSuggestionService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.reminder_repository = ReminderRepository(db)
        self.routine_service = RoutineService(db)
        self.memory_repository = MemoryRepository(db)

    async def get_suggestions(self, reference: Optional[datetime] = None) -> ProactiveSuggestionsResponse:
        reference = reference or utc_now()
        suggestions = []

        overdue = await self.reminder_repository.get_overdue(reference)
        for reminder in overdue:
            suggestions.append(ProactiveSuggestion(
                suggestion_type="overdue_reminder",
                message=f"You have an overdue reminder: \"{reminder.title}\".",
                related_id=reminder.id,
                related_type="reminder",
            ))

        due_soon = await self.reminder_repository.get_due_within(reference, DUE_SOON_WINDOW)
        overdue_ids = {r.id for r in overdue}
        for reminder in due_soon:
            if reminder.id in overdue_ids:
                continue
            minutes_left = max(0, int((reminder.due_at - reference).total_seconds() // 60))
            suggestions.append(ProactiveSuggestion(
                suggestion_type="due_soon_reminder",
                message=f"Reminder in {minutes_left} minute{'s' if minutes_left != 1 else ''}: \"{reminder.title}\".",
                related_id=reminder.id,
                related_type="reminder",
            ))

        routines_now = await self.routine_service.get_active_around(reference, window_minutes=15)
        for routine in routines_now:
            suggestions.append(ProactiveSuggestion(
                suggestion_type="routine_time",
                message=f"It's around the usual time for your \"{routine.name}\" routine.",
                related_id=routine.id,
                related_type="routine",
            ))

        stale = await self.memory_repository.get_filtered(limit=1000)
        stale_count = sum(1 for m in stale if m.verification_state == VerificationState.STALE.value)
        if stale_count >= STALE_MEMORY_SUGGESTION_THRESHOLD:
            suggestions.append(ProactiveSuggestion(
                suggestion_type="stale_memories",
                message=f"{stale_count} memories are flagged stale and might be worth reviewing.",
                related_id=None,
                related_type="memory",
            ))

        return ProactiveSuggestionsResponse(generated_at=reference, suggestions=suggestions)
