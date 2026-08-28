import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.retrieval.retrieval_service import RetrievalService
from app.repositories.memory_repository import MemoryRepository
from app.models.memory import MemoryType


async def _seed_memory(db_session: AsyncSession, **overrides):
    repo = MemoryRepository(db_session)
    defaults = dict(
        title="Math 101",
        content="Math class is at 9am on Mondays",
        memory_type=MemoryType.CLASS.value,
        category="academics",
        importance=3,
        is_pinned=False,
        source="manual",
        tags=[],
        structured_data={},
    )
    defaults.update(overrides)
    return await repo.create_memory(defaults)


@pytest.mark.asyncio
async def test_retrieval_matches_intent_by_type(db_session: AsyncSession):
    await _seed_memory(db_session, title="Math 101", memory_type=MemoryType.CLASS.value)
    await _seed_memory(
        db_session,
        title="Favorite color",
        content="Blue",
        memory_type=MemoryType.PREFERENCE.value,
        category="preferences",
    )

    service = RetrievalService(db_session)
    results = await service.retrieve("When is my next class?")

    assert any(m.memory_type == MemoryType.CLASS.value for m in results)
    assert all(m.memory_type != MemoryType.PREFERENCE.value for m in results)


@pytest.mark.asyncio
async def test_retrieval_falls_back_to_keyword_search(db_session: AsyncSession):
    await _seed_memory(
        db_session,
        title="Roommate's name",
        content="My roommate's name is Sam",
        memory_type=MemoryType.FACT.value,
        category="general",
    )

    service = RetrievalService(db_session)
    results = await service.retrieve("What is my roommate's name?")

    assert any("Sam" in m.content for m in results)


@pytest.mark.asyncio
async def test_retrieval_no_duplicates_across_strategies(db_session: AsyncSession):
    await _seed_memory(
        db_session,
        title="Pinned task",
        content="Finish the report by Friday",
        memory_type=MemoryType.TASK.value,
        category="tasks",
        is_pinned=True,
    )

    service = RetrievalService(db_session)
    results = await service.retrieve("What tasks do I have?")

    ids = [m.id for m in results]
    assert len(ids) == len(set(ids))


@pytest.mark.asyncio
async def test_retrieval_respects_limit(db_session: AsyncSession):
    for i in range(10):
        await _seed_memory(
            db_session,
            title=f"Task {i}",
            content=f"Task number {i} is due soon",
            memory_type=MemoryType.TASK.value,
        )

    service = RetrievalService(db_session)
    results = await service.retrieve("What are my tasks?", limit=3)
    assert len(results) <= 3
