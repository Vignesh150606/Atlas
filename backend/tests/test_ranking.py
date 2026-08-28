from datetime import datetime, timedelta, timezone
import pytest
from app.retrieval.ranking import rank_memories
from app.models.memory import Memory, MemoryType


def _mem(**overrides):
    defaults = dict(
        id="id",
        title="title",
        content="content",
        memory_type=MemoryType.FACT.value,
        importance=3,
        is_pinned=False,
        created_at=datetime.now(timezone.utc),
        last_used=None,
    )
    defaults.update(overrides)
    m = Memory()
    for k, v in defaults.items():
        setattr(m, k, v)
    return m


def test_pinned_memory_ranks_above_unpinned_of_equal_importance():
    now = datetime.now(timezone.utc)
    pinned = _mem(id="1", is_pinned=True, importance=3, created_at=now)
    unpinned = _mem(id="2", is_pinned=False, importance=3, created_at=now)
    ranked = rank_memories([unpinned, pinned], now=now)
    assert ranked[0].id == "1"


def test_higher_importance_ranks_above_lower():
    now = datetime.now(timezone.utc)
    high = _mem(id="1", importance=5, created_at=now)
    low = _mem(id="2", importance=1, created_at=now)
    ranked = rank_memories([low, high], now=now)
    assert ranked[0].id == "1"


def test_more_recent_ranks_above_older():
    now = datetime.now(timezone.utc)
    recent = _mem(id="1", created_at=now)
    old = _mem(id="2", created_at=now - timedelta(days=60))
    ranked = rank_memories([old, recent], now=now)
    assert ranked[0].id == "1"


def test_type_match_boosts_matching_memory():
    now = datetime.now(timezone.utc)
    matching = _mem(id="1", memory_type=MemoryType.CLASS.value, importance=2, created_at=now)
    non_matching = _mem(id="2", memory_type=MemoryType.PREFERENCE.value, importance=2, created_at=now)
    ranked = rank_memories(
        [non_matching, matching], target_types={MemoryType.CLASS.value}, now=now
    )
    assert ranked[0].id == "1"


def test_keyword_relevance_boosts_matching_content():
    now = datetime.now(timezone.utc)
    relevant = _mem(id="1", title="Math class", content="Math at 9am", importance=2, created_at=now)
    irrelevant = _mem(id="2", title="Unrelated", content="Nothing to do with it", importance=2, created_at=now)
    ranked = rank_memories([irrelevant, relevant], keywords=["math"], now=now)
    assert ranked[0].id == "1"


def test_conversation_context_boosts_recently_referenced_memory():
    now = datetime.now(timezone.utc)
    referenced = _mem(id="1", importance=2, created_at=now)
    not_referenced = _mem(id="2", importance=2, created_at=now)
    ranked = rank_memories(
        [not_referenced, referenced], recent_memory_ids={"1"}, now=now
    )
    assert ranked[0].id == "1"


def test_last_used_overrides_created_at_for_recency():
    now = datetime.now(timezone.utc)
    stale_creation_but_recently_used = _mem(
        id="1", created_at=now - timedelta(days=90), last_used=now
    )
    fresh_creation_never_used = _mem(id="2", created_at=now - timedelta(days=1), last_used=None)
    ranked = rank_memories(
        [fresh_creation_never_used, stale_creation_but_recently_used], now=now
    )
    assert ranked[0].id == "1"
