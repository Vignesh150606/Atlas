import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.memory_repository import MemoryRepository
from app.models.memory import MemoryType

@pytest.mark.asyncio
async def test_memory_repository_crud_and_fts(db_session: AsyncSession):
    repo = MemoryRepository(db_session)
    await repo.init_fts()

    # 1. Create
    mem = await repo.create_memory({
        "title": "Favorite Color",
        "content": "My favorite color is emerald green.",
        "memory_type": MemoryType.PREFERENCE.value,
        "category": "preferences",
        "importance": 5,
        "is_pinned": True,
        "tags": ["favorite", "color"]
    })
    assert mem.id is not None
    assert mem.title == "Favorite Color"

    # 2. Get & Filter
    fetched = await repo.get_by_id(mem.id)
    assert fetched is not None
    assert fetched.memory_type == MemoryType.PREFERENCE.value

    preferences = await repo.get_filtered(memory_type=MemoryType.PREFERENCE.value)
    assert len(preferences) == 1

    # 3. Search
    search_results = await repo.search("emerald")
    assert len(search_results) >= 1
    assert search_results[0].id == mem.id

    # 4. Soft Delete
    deleted = await repo.soft_delete(mem.id)
    assert deleted.deleted_at is not None

    active_memories = await repo.get_filtered(memory_type=MemoryType.PREFERENCE.value)
    assert len(active_memories) == 0


# --- Phase 9: near-duplicate detection ------------------------------------
@pytest.mark.asyncio
async def test_find_duplicate_still_matches_exact_title_or_content(db_session: AsyncSession):
    """Unchanged Phase 1-8 behavior: exact match wins before any
    similarity scan runs."""
    repo = MemoryRepository(db_session)
    mem = await repo.create_memory({
        "title": "Favorite Food", "content": "Pizza", "memory_type": MemoryType.PREFERENCE.value,
        "category": "preferences", "importance": 3, "is_pinned": False, "source": "manual",
        "tags": [], "structured_data": {},
    })
    found = await repo.find_duplicate("Favorite Food", "Pizza")
    assert found.id == mem.id


@pytest.mark.asyncio
async def test_find_duplicate_catches_paraphrased_restatement(db_session: AsyncSession):
    """A near-identical restatement (different title, very similar content)
    should be caught even though neither title nor content is an exact
    match - this is the Phase 9 addition."""
    repo = MemoryRepository(db_session)
    original = await repo.create_memory({
        "title": "Favorite Drink", "content": "My favorite drink is black coffee in the morning.",
        "memory_type": MemoryType.PREFERENCE.value, "category": "preferences", "importance": 3,
        "is_pinned": False, "source": "manual", "tags": [], "structured_data": {},
    })
    found = await repo.find_duplicate(
        "Drink Preference", "My favorite drink is black coffee every morning.",
        memory_type=MemoryType.PREFERENCE.value,
    )
    assert found is not None
    assert found.id == original.id


@pytest.mark.asyncio
async def test_find_duplicate_does_not_flag_genuinely_different_content(db_session: AsyncSession):
    repo = MemoryRepository(db_session)
    await repo.create_memory({
        "title": "Favorite Drink", "content": "My favorite drink is black coffee.",
        "memory_type": MemoryType.PREFERENCE.value, "category": "preferences", "importance": 3,
        "is_pinned": False, "source": "manual", "tags": [], "structured_data": {},
    })
    found = await repo.find_duplicate(
        "Favorite Movie", "My favorite movie is a 90s sci-fi classic.",
        memory_type=MemoryType.PREFERENCE.value,
    )
    assert found is None


@pytest.mark.asyncio
async def test_find_duplicate_scoped_to_memory_type_when_given(db_session: AsyncSession):
    """Near-identical (but not exact - exact match is intentionally
    type-unscoped, see test above) content in a *different* memory_type
    must not be flagged as a near-duplicate - a TASK and a NOTE that
    happen to be worded similarly are still two different kinds of thing."""
    repo = MemoryRepository(db_session)
    await repo.create_memory({
        "title": "Task Note", "content": "Submit the quarterly report by Friday afternoon please.",
        "memory_type": MemoryType.TASK.value, "category": "tasks", "importance": 3,
        "is_pinned": False, "source": "manual", "tags": [], "structured_data": {},
    })
    found = await repo.find_duplicate(
        "General Note", "Remember to submit the quarterly report Friday afternoon.",
        memory_type=MemoryType.NOTE.value,
    )
    assert found is None


# --- Phase 9: confidence lifecycle ----------------------------------------
@pytest.mark.asyncio
async def test_record_usage_increments_confidence(db_session: AsyncSession):
    repo = MemoryRepository(db_session)
    mem = await repo.create_memory({
        "title": "Favorite Food", "content": "Pizza", "memory_type": MemoryType.PREFERENCE.value,
        "category": "preferences", "importance": 3, "is_pinned": False, "source": "manual",
        "tags": [], "structured_data": {}, "confidence": 90,
    })
    await repo.record_usage([mem.id])
    refreshed = await repo.get_by_id(mem.id)
    assert refreshed.confidence == 92


@pytest.mark.asyncio
async def test_record_usage_confidence_caps_at_100(db_session: AsyncSession):
    repo = MemoryRepository(db_session)
    mem = await repo.create_memory({
        "title": "Favorite Food", "content": "Pizza", "memory_type": MemoryType.PREFERENCE.value,
        "category": "preferences", "importance": 3, "is_pinned": False, "source": "manual",
        "tags": [], "structured_data": {}, "confidence": 99,
    })
    await repo.record_usage([mem.id])
    refreshed = await repo.get_by_id(mem.id)
    assert refreshed.confidence == 100
