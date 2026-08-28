from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.repositories.base import BaseRepository
from app.models.routine import Routine


class RoutineRepository(BaseRepository[Routine]):
    def __init__(self, db: AsyncSession):
        super().__init__(Routine, db)

    async def get_filtered(
        self,
        is_active: Optional[bool] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Routine]:
        query = select(Routine)
        if is_active is not None:
            query = query.filter(Routine.is_active == is_active)
        query = query.order_by(Routine.name.asc()).offset(skip).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_by_name(self, name: str) -> Optional[Routine]:
        query = select(Routine).filter(Routine.name.ilike(name.strip()))
        result = await self.db.execute(query)
        return result.scalars().first()

    async def search_by_name_fragment(self, fragment: str) -> Optional[Routine]:
        """Used by RoutineSkill's "what's my <X> routine" chat phrasing,
        where <X> is a rough fragment ("morning") rather than the exact
        stored name ("Morning Routine") - same "contains, most-recent
        wins" tie-break as TaskRepository.find_incomplete_by_title."""
        query = select(Routine).filter(
            Routine.is_active.is_(True),
            Routine.name.ilike(f"%{fragment.strip()}%"),
        ).order_by(Routine.created_at.desc())
        result = await self.db.execute(query)
        return result.scalars().first()
