from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from app.database.session import get_db
from app.schemas.task import TaskCreate, TaskUpdate, TaskResponse
from app.models.task import TaskPriority
from app.services.task_service import TaskService

router = APIRouter()


class PrioritizeRequest(BaseModel):
    priority: TaskPriority = Field(...)


@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(request: TaskCreate, db: AsyncSession = Depends(get_db)):
    service = TaskService(db)
    task = await service.create(request, source="api")
    await db.commit()
    return task


@router.get("", response_model=List[TaskResponse])
async def list_tasks(
    status_filter: Optional[str] = Query(None, alias="status"),
    priority: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    service = TaskService(db)
    return await service.list(status=status_filter, priority=priority, skip=skip, limit=limit)


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str, db: AsyncSession = Depends(get_db)):
    service = TaskService(db)
    task = await service.get(task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task


@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task(task_id: str, request: TaskUpdate, db: AsyncSession = Depends(get_db)):
    service = TaskService(db)
    task = await service.update(task_id, request)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    await db.commit()
    return task


@router.post("/{task_id}/complete", response_model=TaskResponse)
async def complete_task(task_id: str, db: AsyncSession = Depends(get_db)):
    service = TaskService(db)
    task = await service.complete(task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    await db.commit()
    return task


@router.post("/{task_id}/cancel", response_model=TaskResponse)
async def cancel_task(task_id: str, db: AsyncSession = Depends(get_db)):
    service = TaskService(db)
    task = await service.cancel(task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    await db.commit()
    return task


@router.post("/{task_id}/prioritize", response_model=TaskResponse)
async def prioritize_task(task_id: str, request: PrioritizeRequest, db: AsyncSession = Depends(get_db)):
    service = TaskService(db)
    task = await service.prioritize(task_id, request.priority.value)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    await db.commit()
    return task


@router.delete("/{task_id}", response_model=TaskResponse)
async def delete_task(task_id: str, db: AsyncSession = Depends(get_db)):
    service = TaskService(db)
    task = await service.delete(task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    await db.commit()
    return task
