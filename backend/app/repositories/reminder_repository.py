from typing import List, Optional
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.repositories.base import BaseRepository
from app.models.reminder import Reminder, ReminderStatus


class ReminderRepository(BaseRepository[Reminder]):
    def __init__(self, db: AsyncSession):
        super().__init__(Reminder, db)

    async def get_filtered(
        self,
        status: Optional[str] = None,
        due_before: Optional[datetime] = None,
        due_after: Optional[datetime] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Reminder]:
        query = select(Reminder)
        if status:
            query = query.filter(Reminder.status == status)
        if due_before is not None:
            query = query.filter(Reminder.due_at.is_not(None), Reminder.due_at <= due_before)
        if due_after is not None:
            query = query.filter(Reminder.due_at.is_not(None), Reminder.due_at >= due_after)
        query = query.order_by(Reminder.due_at.asc().nulls_last()).offset(skip).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_due_within(self, reference: datetime, within: timedelta) -> List[Reminder]:
        """PENDING reminders due between now and `reference + within` -
        used by both DailyBriefingService and ProactiveSuggestionService
        so "what's coming up" is defined exactly once (see mission brief
        section 16's architectural rule against parallel implementations)."""
        window_end = reference + within
        query = select(Reminder).filter(
            Reminder.status == ReminderStatus.PENDING.value,
            Reminder.due_at.is_not(None),
            Reminder.due_at <= window_end,
        ).order_by(Reminder.due_at.asc())
        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_overdue(self, reference: datetime) -> List[Reminder]:
        query = select(Reminder).filter(
            Reminder.status == ReminderStatus.PENDING.value,
            Reminder.due_at.is_not(None),
            Reminder.due_at < reference,
        ).order_by(Reminder.due_at.asc())
        result = await self.db.execute(query)
        return result.scalars().all()
