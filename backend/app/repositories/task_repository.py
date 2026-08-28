from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.repositories.base import BaseRepository
from app.models.task import Task, TaskStatus


class TaskRepository(BaseRepository[Task]):
    def __init__(self, db: AsyncSession):
        super().__init__(Task, db)

    async def get_filtered(
        self,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Task]:
        query = select(Task)
        if status:
            query = query.filter(Task.status == status)
        if priority:
            query = query.filter(Task.priority == priority)
        query = query.order_by(Task.created_at.desc()).offset(skip).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_incomplete(self, limit: int = 100) -> List[Task]:
        query = select(Task).filter(
            Task.status.in_([TaskStatus.PENDING.value, TaskStatus.IN_PROGRESS.value])
        ).order_by(Task.created_at.asc()).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def find_incomplete_by_title(self, title_fragment: str) -> Optional[Task]:
        """Best-effort lookup for chat-driven "complete task X"/"cancel
        task X" (see app/skills/task_skill.py) where the user names a task
        by its title text, not an id they were never shown. Most-recent
        incomplete match wins on multiple hits - a deliberately simple,
        explainable tie-break (same philosophy as the rest of this
        codebase's heuristics), not a similarity-ranked search."""
        query = select(Task).filter(
            Task.status.in_([TaskStatus.PENDING.value, TaskStatus.IN_PROGRESS.value]),
            Task.title.ilike(f"%{title_fragment.strip()}%"),
        ).order_by(Task.created_at.desc())
        result = await self.db.execute(query)
        return result.scalars().first()
