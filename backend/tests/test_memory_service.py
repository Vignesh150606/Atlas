import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.memory_service import MemoryService
from app.schemas.memory import MemoryCreate, MemoryUpdate, MemoryFilterParams
from app.models.memory import MemoryType

@pytest.mark.asyncio
async def test_memory_service_duplicate_detection(db_session: AsyncSession):
    service = MemoryService(db_session)

    mem_in = MemoryCreate(
        title="Python Course",
        content="Enrolled in Advanced Python Course.",
        memory_type=MemoryType.CLASS,
        category="academics"
    )

    mem1 = await service.create_memory(mem_in)
    assert mem1.id is not None

    # Duplicate creation attempt (should return existing memory)
    mem2 = await service.create_memory(mem_in, allow_duplicate=False)
    assert mem2.id == mem1.id

    # Update
    updated = await service.update_memory(mem1.id, MemoryUpdate(importance=5, is_pinned=True))
    assert updated.importance == 5
    assert updated.is_pinned is True

    # Pinned list
    pinned = await service.get_pinned_memories()
    assert len(pinned) == 1
    assert pinned[0].id == mem1.id


# --- Phase 10: Personal Context Engine - temporary context (see
# MemoryService.create_temporary_context) --------------------------------
@pytest.mark.asyncio
async def test_create_temporary_context_sets_expiry_and_category(db_session: AsyncSession):
    service = MemoryService(db_session)
    memory = await service.create_temporary_context(
        title="Currently working on", content="Drafting the Q3 report", ttl_minutes=60
    )
    assert memory.category == "temporary_context"
    assert memory.expires_at is not None
    assert "temporary_context" in memory.tags


@pytest.mark.asyncio
async def test_expired_temporary_context_excluded_from_get_filtered(db_session: AsyncSession):
    from datetime import timedelta
    from app.utils.time import utc_now
    service = MemoryService(db_session)
    memory = await service.create_temporary_context(title="Stale context", content="No longer relevant")
    memory.expires_at = utc_now() - timedelta(minutes=1)  # force-expire
    await db_session.flush()

    results = await service.repository.get_filtered()
    assert memory.id not in {m.id for m in results}


@pytest.mark.asyncio
async def test_non_expired_temporary_context_still_included(db_session: AsyncSession):
    service = MemoryService(db_session)
    memory = await service.create_temporary_context(title="Fresh context", content="Still relevant", ttl_minutes=60)
    results = await service.repository.get_filtered()
    assert memory.id in {m.id for m in results}


@pytest.mark.asyncio
async def test_permanent_memories_unaffected_by_expiry_filter(db_session: AsyncSession):
    """expires_at is None for every ordinary memory - the expiry filter
    must be a strict no-op for them (see MemoryRepository.get_filtered)."""
    service = MemoryService(db_session)
    memory = await service.create_memory(MemoryCreate(
        title="Permanent fact", content="Real, lasting preference", memory_type=MemoryType.PREFERENCE,
    ))
    assert memory.expires_at is None
    results = await service.repository.get_filtered()
    assert memory.id in {m.id for m in results}
