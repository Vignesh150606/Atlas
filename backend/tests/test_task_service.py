import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.task_service import TaskService
from app.schemas.task import TaskCreate, TaskUpdate
from app.models.task import TaskStatus, TaskPriority


@pytest.mark.asyncio
async def test_create_task_defaults(db_session: AsyncSession):
    service = TaskService(db_session)
    task = await service.create(TaskCreate(title="Write essay"))
    assert task.title == "Write essay"
    assert task.status == TaskStatus.PENDING.value
    assert task.priority == TaskPriority.MEDIUM.value


@pytest.mark.asyncio
async def test_complete_task(db_session: AsyncSession):
    service = TaskService(db_session)
    task = await service.create(TaskCreate(title="Finish thesis"))
    completed = await service.complete(task.id)
    assert completed.status == TaskStatus.COMPLETED.value
    assert completed.completed_at is not None


@pytest.mark.asyncio
async def test_cancel_task(db_session: AsyncSession):
    service = TaskService(db_session)
    task = await service.create(TaskCreate(title="Drop this"))
    cancelled = await service.cancel(task.id)
    assert cancelled.status == TaskStatus.CANCELLED.value


@pytest.mark.asyncio
async def test_prioritize_task(db_session: AsyncSession):
    service = TaskService(db_session)
    task = await service.create(TaskCreate(title="Important thing"))
    updated = await service.prioritize(task.id, TaskPriority.HIGH.value)
    assert updated.priority == TaskPriority.HIGH.value


@pytest.mark.asyncio
async def test_list_incomplete_excludes_completed_and_cancelled(db_session: AsyncSession):
    service = TaskService(db_session)
    pending = await service.create(TaskCreate(title="Pending"))
    done = await service.create(TaskCreate(title="Done"))
    cancelled = await service.create(TaskCreate(title="Cancelled"))
    await service.complete(done.id)
    await service.cancel(cancelled.id)

    incomplete = await service.list_incomplete()
    ids = {t.id for t in incomplete}
    assert pending.id in ids
    assert done.id not in ids
    assert cancelled.id not in ids


@pytest.mark.asyncio
async def test_find_incomplete_by_title_fragment(db_session: AsyncSession):
    service = TaskService(db_session)
    await service.create(TaskCreate(title="Submit the quarterly report"))
    found = await service.find_incomplete_by_title("quarterly report")
    assert found is not None
    assert found.title == "Submit the quarterly report"


@pytest.mark.asyncio
async def test_find_incomplete_by_title_ignores_completed(db_session: AsyncSession):
    service = TaskService(db_session)
    task = await service.create(TaskCreate(title="Buy groceries"))
    await service.complete(task.id)
    found = await service.find_incomplete_by_title("groceries")
    assert found is None


@pytest.mark.asyncio
async def test_update_task(db_session: AsyncSession):
    service = TaskService(db_session)
    task = await service.create(TaskCreate(title="Original"))
    updated = await service.update(task.id, TaskUpdate(description="Some detail"))
    assert updated.description == "Some detail"


@pytest.mark.asyncio
async def test_complete_unknown_task_returns_none(db_session: AsyncSession):
    service = TaskService(db_session)
    result = await service.complete("not-a-real-id")
    assert result is None
