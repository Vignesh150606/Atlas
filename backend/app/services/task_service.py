from datetime import datetime
from app.utils.time import utc_now
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.task_repository import TaskRepository
from app.models.task import Task, TaskStatus
from app.schemas.task import TaskCreate, TaskUpdate


class TaskService:
    """Phase 10: lightweight personal task management (mission brief
    section 3). Deliberately a flat status/priority model with no
    subtasks, dependencies, assignees, or projects - "keep it personal
    and assistant-oriented", not a project-management platform."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repository = TaskRepository(db)

    async def create(self, data: TaskCreate, source: str = "api") -> Task:
        payload = {
            "title": data.title.strip(),
            "description": data.description,
            "priority": data.priority.value,
            "due_at": data.due_at,
            "conversation_id": data.conversation_id,
            "source": source,
            "status": TaskStatus.PENDING.value,
        }
        return await self.repository.create(payload)

    async def get(self, task_id: str) -> Optional[Task]:
        return await self.repository.get(task_id)

    async def list(
        self, status: Optional[str] = None, priority: Optional[str] = None, skip: int = 0, limit: int = 100
    ) -> List[Task]:
        return await self.repository.get_filtered(status=status, priority=priority, skip=skip, limit=limit)

    async def list_incomplete(self, limit: int = 100) -> List[Task]:
        return await self.repository.get_incomplete(limit=limit)

    async def find_incomplete_by_title(self, title_fragment: str) -> Optional[Task]:
        return await self.repository.find_incomplete_by_title(title_fragment)

    async def update(self, task_id: str, data: TaskUpdate) -> Optional[Task]:
        task = await self.repository.get(task_id)
        if not task:
            return None
        update_data = data.model_dump(exclude_unset=True)
        if "status" in update_data and update_data["status"] is not None:
            update_data["status"] = update_data["status"].value
        if "priority" in update_data and update_data["priority"] is not None:
            update_data["priority"] = update_data["priority"].value
        return await self.repository.update(task, update_data)

    async def complete(self, task_id: str) -> Optional[Task]:
        task = await self.repository.get(task_id)
        if not task:
            return None
        return await self.repository.update(task, {
            "status": TaskStatus.COMPLETED.value,
            "completed_at": utc_now(),
        })

    async def cancel(self, task_id: str) -> Optional[Task]:
        task = await self.repository.get(task_id)
        if not task:
            return None
        return await self.repository.update(task, {"status": TaskStatus.CANCELLED.value})

    async def prioritize(self, task_id: str, priority: str) -> Optional[Task]:
        task = await self.repository.get(task_id)
        if not task:
            return None
        return await self.repository.update(task, {"priority": priority})

    async def delete(self, task_id: str) -> Optional[Task]:
        return await self.repository.delete(task_id)
