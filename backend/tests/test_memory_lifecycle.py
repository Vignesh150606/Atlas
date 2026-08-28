from datetime import datetime, timedelta, timezone
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.memory_repository import MemoryRepository
from app.services.memory_lifecycle_service import MemoryLifecycleService
from app.models.memory import MemoryType, VerificationState


async def _create(repo: MemoryRepository, **overrides) -> "Memory":
    defaults = dict(
        title="Old fact", content="Something the user said a while ago.",
        memory_type=MemoryType.FACT.value, category="general", importance=2,
        is_pinned=False, source="manual", tags=[], structured_data={},
        confidence=40,
    )
    defaults.update(overrides)
    return await repo.create_memory(defaults)


@pytest.mark.asyncio
async def test_flags_old_low_confidence_unused_memory_as_stale(db_session: AsyncSession):
    repo = MemoryRepository(db_session)
    mem = await _create(repo, confidence=30)
    # Backdate created_at past the staleness cutoff directly (no last_used).
    mem.created_at = datetime.now(timezone.utc) - timedelta(days=200)
    db_session.add(mem)
    await db_session.flush()

    service = MemoryLifecycleService(db_session)
    report = await service.flag_stale_memories(stale_after_days=90, confidence_threshold=50)

    assert mem.id in report.flagged_stale
    refreshed = await repo.get_by_id(mem.id)
    assert refreshed.verification_state == VerificationState.STALE.value


@pytest.mark.asyncio
async def test_does_not_flag_recent_memory_even_if_low_confidence(db_session: AsyncSession):
    repo = MemoryRepository(db_session)
    mem = await _create(repo, confidence=20)  # created "now" - not old

    service = MemoryLifecycleService(db_session)
    report = await service.flag_stale_memories(stale_after_days=90, confidence_threshold=50)

    assert mem.id not in report.flagged_stale


@pytest.mark.asyncio
async def test_does_not_flag_old_memory_with_high_confidence(db_session: AsyncSession):
    repo = MemoryRepository(db_session)
    mem = await _create(repo, confidence=95)
    mem.created_at = datetime.now(timezone.utc) - timedelta(days=200)
    db_session.add(mem)
    await db_session.flush()

    service = MemoryLifecycleService(db_session)
    report = await service.flag_stale_memories(stale_after_days=90, confidence_threshold=50)

    assert mem.id not in report.flagged_stale


@pytest.mark.asyncio
async def test_pinned_memory_is_never_auto_flagged_stale(db_session: AsyncSession):
    repo = MemoryRepository(db_session)
    mem = await _create(repo, confidence=10, is_pinned=True)
    mem.created_at = datetime.now(timezone.utc) - timedelta(days=400)
    db_session.add(mem)
    await db_session.flush()

    service = MemoryLifecycleService(db_session)
    report = await service.flag_stale_memories(stale_after_days=90, confidence_threshold=50)

    assert mem.id not in report.flagged_stale
    assert report.pinned_skipped >= 1


@pytest.mark.asyncio
async def test_confirmed_memory_is_not_auto_flagged_stale(db_session: AsyncSession):
    repo = MemoryRepository(db_session)
    mem = await _create(repo, confidence=10)
    mem.created_at = datetime.now(timezone.utc) - timedelta(days=400)
    mem.verification_state = VerificationState.CONFIRMED.value
    db_session.add(mem)
    await db_session.flush()

    service = MemoryLifecycleService(db_session)
    report = await service.flag_stale_memories(stale_after_days=90, confidence_threshold=50)

    assert mem.id not in report.flagged_stale


@pytest.mark.asyncio
async def test_already_stale_memory_is_counted_not_reflagged(db_session: AsyncSession):
    repo = MemoryRepository(db_session)
    mem = await _create(repo, confidence=10)
    mem.created_at = datetime.now(timezone.utc) - timedelta(days=400)
    mem.verification_state = VerificationState.STALE.value
    db_session.add(mem)
    await db_session.flush()

    service = MemoryLifecycleService(db_session)
    report = await service.flag_stale_memories(stale_after_days=90, confidence_threshold=50)

    assert mem.id not in report.flagged_stale  # not re-added to the "newly flagged" list
    assert report.already_stale >= 1


@pytest.mark.asyncio
async def test_last_used_overrides_created_at_for_staleness_reference(db_session: AsyncSession):
    """A memory created long ago but used recently should NOT be flagged -
    mirrors rank_memories' recency logic (last_used takes priority)."""
    repo = MemoryRepository(db_session)
    mem = await _create(repo, confidence=20)
    mem.created_at = datetime.now(timezone.utc) - timedelta(days=400)
    mem.last_used = datetime.now(timezone.utc) - timedelta(days=1)
    db_session.add(mem)
    await db_session.flush()

    service = MemoryLifecycleService(db_session)
    report = await service.flag_stale_memories(stale_after_days=90, confidence_threshold=50)

    assert mem.id not in report.flagged_stale


# --- Phase 10: expire_temporary_context (see MemoryLifecycleService and
# app/services/memory_service.py's create_temporary_context) ----------------
@pytest.mark.asyncio
async def test_expire_temporary_context_hard_deletes_expired_rows(db_session: AsyncSession):
    from app.services.memory_service import MemoryService
    memory_service = MemoryService(db_session)
    expired = await memory_service.create_temporary_context(
        title="Old session context", content="Was working on X", ttl_minutes=60
    )
    expired.expires_at = datetime.now(timezone.utc) - timedelta(minutes=5)
    fresh = await memory_service.create_temporary_context(
        title="Current session context", content="Working on Y", ttl_minutes=60
    )
    await db_session.flush()

    service = MemoryLifecycleService(db_session)
    report = await service.expire_temporary_context()

    assert expired.id in report.deleted
    assert fresh.id not in report.deleted
    remaining = await MemoryRepository(db_session).get_filtered(include_expired=True)
    assert expired.id not in {m.id for m in remaining}
    assert fresh.id in {m.id for m in remaining}


@pytest.mark.asyncio
async def test_expire_temporary_context_never_touches_permanent_memories(db_session: AsyncSession):
    repo = MemoryRepository(db_session)
    permanent = await _create(repo, title="Permanent", confidence=90)
    service = MemoryLifecycleService(db_session)
    report = await service.expire_temporary_context()
    assert permanent.id not in report.deleted
