"""Phase 10: Daily Briefing (mission brief section 4).

Deliberately a thin composition over services that already exist -
`ReminderService`, `TaskService`, `RoutineService`, `MemoryRepository`,
`MemoryLifecycleService` - not a new orchestration system. The mission
brief is explicit about this ("The architecture must use existing
skills/tools rather than creating another parallel orchestration
system") and it's also just the DRY-est option: "what's due soon" is
already `ReminderRepository.get_due_within` (also used by
`ProactiveSuggestionService`), so it's defined once.

No LLM call: every section here is a real, structured query result. The
`narrative` field is a deterministic string join (same "Luhn-lite,
no-LLM" philosophy as `app/knowledge/summarizer.py`'s extractive
summary), not a model-generated paragraph - BriefingSkill (see
app/skills/briefing_skill.py) hands this structured data to the LLM as
tool_results so *it* can phrase a natural-language briefing if the user
asked in chat; the API route (app/api/v1/endpoints/briefing.py) returns
the structured form directly for a client that wants to render its own
UI instead of reading prose.
"""
from datetime import datetime, timedelta
from app.utils.time import utc_now
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.reminder_service import ReminderService
from app.services.task_service import TaskService
from app.services.routine_service import RoutineService
from app.services.memory_lifecycle_service import MemoryLifecycleService
from app.repositories.memory_repository import MemoryRepository
from app.schemas.reminder import ReminderResponse
from app.schemas.task import TaskResponse
from app.schemas.routine import RoutineResponse
from app.schemas.briefing import DailyBriefingResponse, BriefingMemoryItem
from app.models.memory import VerificationState

DEFAULT_UPCOMING_WINDOW = timedelta(hours=24)


class DailyBriefingService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.reminder_service = ReminderService(db)
        self.task_service = TaskService(db)
        self.routine_service = RoutineService(db)
        self.memory_repository = MemoryRepository(db)

    async def build(
        self,
        reference: Optional[datetime] = None,
        upcoming_window: timedelta = DEFAULT_UPCOMING_WINDOW,
        client_timezone: Optional[str] = None,
    ) -> DailyBriefingResponse:
        """Phase 12 (ARCH-TZ): client_timezone, when given, is used only
        for routine time-of-day matching below (see
        RoutineService.get_active_around) - reminders/tasks are already
        correct without it since they compare stored UTC values against a
        UTC reference. Defaults to None (no conversion), matching
        ProactiveSuggestionService's reasoning: existing tests pass an
        explicit, already-local `reference` and must keep their exact
        pre-Phase-12 meaning; GET /briefing/daily resolves a real zone
        before calling this.
        """
        reference = reference or utc_now()

        upcoming_reminders = await self.reminder_service.get_upcoming(upcoming_window, reference)
        overdue_reminders = await self.reminder_service.get_overdue(reference)
        # Overdue items belong in the briefing too (they're the most
        # actionable thing in it) - merged ahead of not-yet-due upcoming
        # ones, de-duplicated defensively even though the two repository
        # queries are disjoint by construction (overdue: due_at < now;
        # upcoming: due_at <= now + window, which also includes overdue
        # rows - see ReminderRepository.get_due_within).
        seen_ids = set()
        merged_reminders = []
        for r in [*overdue_reminders, *upcoming_reminders]:
            if r.id not in seen_ids:
                seen_ids.add(r.id)
                merged_reminders.append(r)

        incomplete_tasks = await self.task_service.list_incomplete(limit=50)
        routines_today = await self.routine_service.get_active_around(
            reference, window_minutes=12 * 60, zone=client_timezone
        )

        important_memories = await self.memory_repository.get_filtered(is_pinned=True, limit=5)
        if len(important_memories) < 5:
            extra = await self.memory_repository.get_filtered(importance=5, limit=5)
            for m in extra:
                if m.id not in {x.id for x in important_memories}:
                    important_memories.append(m)

        stale_memories = await self.memory_repository.get_filtered(limit=1000)
        stale_count = sum(1 for m in stale_memories if m.verification_state == VerificationState.STALE.value)

        reminder_responses = [ReminderResponse.model_validate(r) for r in merged_reminders]
        task_responses = [TaskResponse.model_validate(t) for t in incomplete_tasks]
        routine_responses = [RoutineResponse.model_validate(r) for r in routines_today]
        memory_items = [
            BriefingMemoryItem(id=m.id, title=m.title, category=m.category, importance=m.importance)
            for m in important_memories[:5]
        ]

        narrative = self._build_narrative(
            reminder_responses, task_responses, routine_responses, len(overdue_reminders)
        )

        return DailyBriefingResponse(
            generated_at=reference,
            upcoming_reminders=reminder_responses,
            incomplete_tasks=task_responses,
            routines_today=routine_responses,
            important_memories=memory_items,
            stale_memory_count=stale_count,
            narrative=narrative,
        )

    @staticmethod
    def _build_narrative(reminders, tasks, routines, overdue_count) -> str:
        parts = []
        if overdue_count:
            parts.append(f"{overdue_count} overdue reminder{'s' if overdue_count != 1 else ''}")
        # `reminders` is the merged (overdue + upcoming) list, so subtract
        # overdue_count to avoid double-counting/mislabeling overdue items
        # as "in the next 24 hours" - they were already reported above.
        upcoming_count = len(reminders) - overdue_count
        if upcoming_count:
            parts.append(f"{upcoming_count} reminder{'s' if upcoming_count != 1 else ''} in the next 24 hours")
        if tasks:
            parts.append(f"{len(tasks)} incomplete task{'s' if len(tasks) != 1 else ''}")
        if routines:
            names = ", ".join(r.name for r in routines[:3])
            parts.append(f"routines around now: {names}")
        if not parts:
            return "Nothing pressing - no upcoming reminders, no incomplete tasks, no routines scheduled around now."
        return "Today: " + "; ".join(parts) + "."
