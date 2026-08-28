from datetime import datetime
from app.utils.time import utc_now
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.routine_repository import RoutineRepository
from app.models.routine import Routine
from app.schemas.routine import RoutineCreate, RoutineUpdate


class RoutineService:
    """Phase 10: explicit-only routine CRUD (mission brief section 5).
    No method here ever creates or edits a Routine except in direct
    response to a user action - see app/models/routine.py's docstring."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repository = RoutineRepository(db)

    async def create(self, data: RoutineCreate) -> Routine:
        payload = {
            "name": data.name.strip(),
            "description": data.description,
            "steps": data.steps,
            "time_of_day": data.time_of_day,
            "days_of_week": data.days_of_week,
            "is_active": True,
        }
        return await self.repository.create(payload)

    async def get(self, routine_id: str) -> Optional[Routine]:
        return await self.repository.get(routine_id)

    async def get_by_name(self, name: str) -> Optional[Routine]:
        return await self.repository.get_by_name(name)

    async def search_by_name_fragment(self, fragment: str) -> Optional[Routine]:
        return await self.repository.search_by_name_fragment(fragment)

    async def list(self, is_active: Optional[bool] = None, skip: int = 0, limit: int = 100) -> List[Routine]:
        return await self.repository.get_filtered(is_active=is_active, skip=skip, limit=limit)

    async def update(self, routine_id: str, data: RoutineUpdate) -> Optional[Routine]:
        routine = await self.repository.get(routine_id)
        if not routine:
            return None
        update_data = data.model_dump(exclude_unset=True)
        return await self.repository.update(routine, update_data)

    async def delete(self, routine_id: str) -> Optional[Routine]:
        return await self.repository.delete(routine_id)

    async def get_active_around(self, reference: Optional[datetime] = None, window_minutes: int = 60) -> List[Routine]:
        """Active routines whose `time_of_day` falls within
        `window_minutes` of `reference` (default: now) on a day they
        apply - what DailyBriefingService/ProactiveSuggestionService use
        for "your morning routine" style surfacing. Pure in-process
        filtering over an already-small table (routines are hand-authored
        by one user - dozens at most, not thousands), so no need for a
        SQL time-window query.
        """
        reference = reference or utc_now()
        routines = await self.repository.get_filtered(is_active=True, limit=1000)
        matches: List[Routine] = []
        for routine in routines:
            if routine.days_of_week and reference.weekday() not in routine.days_of_week:
                continue
            if not routine.time_of_day:
                continue
            try:
                hour, minute = (int(p) for p in routine.time_of_day.split(":", 1))
            except (ValueError, AttributeError):
                continue
            routine_minutes = hour * 60 + minute
            reference_minutes = reference.hour * 60 + reference.minute
            # Circular distance on a 24h clock (1440 minutes), not a plain
            # absolute difference - otherwise a routine just before
            # midnight (e.g. 23:50) checked just after (e.g. 00:05) reads
            # as ~1430 minutes apart instead of the real 15, and never
            # matches any reasonable window.
            raw_diff = abs(routine_minutes - reference_minutes)
            circular_diff = min(raw_diff, 24 * 60 - raw_diff)
            if circular_diff <= window_minutes:
                matches.append(routine)
        return matches
