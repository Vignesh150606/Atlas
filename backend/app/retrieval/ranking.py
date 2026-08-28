import math
from datetime import datetime, timezone
from typing import List, Optional, Set
from app.models.memory import Memory
from app.retrieval.semantic_match import relevance_score

# Weights are intentionally simple and documented rather than tuned/learned -
# this is deterministic scoring, not a model. Each factor contributes a
# 0-1 normalized component, then a fixed weight combines them.
_WEIGHTS = {
    "recency": 0.20,
    "importance": 0.25,
    "pinned": 0.15,
    "type_match": 0.20,
    "keyword_relevance": 0.15,
    "conversation_context": 0.05,
}


def _recency_score(memory: Memory, now: datetime) -> float:
    """More recently created/used memories score higher. Uses last_used if
    the memory has been retrieved before, otherwise falls back to created_at.
    Decays smoothly over ~30 days rather than a hard cliff.
    """
    reference = memory.last_used or memory.created_at
    if reference is None:
        return 0.0
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=timezone.utc)
    age_days = max((now - reference).total_seconds() / 86400.0, 0.0)
    return math.exp(-age_days / 30.0)  # ~0.37 at 30 days, ~0.05 at 90 days


def _importance_score(memory: Memory) -> float:
    return max(0.0, min(1.0, (memory.importance or 0) / 5.0))


def _pinned_score(memory: Memory) -> float:
    return 1.0 if memory.is_pinned else 0.0


def _type_match_score(memory: Memory, target_types: Optional[Set[str]]) -> float:
    if not target_types:
        return 0.5  # neutral when no specific type was inferred for this query
    return 1.0 if memory.memory_type in target_types else 0.0


def _keyword_relevance_score(memory: Memory, keywords: List[str]) -> float:
    """Phase 9: delegates to the shared semantic-like scorer (see
    app/retrieval/semantic_match.py) instead of a private substring count -
    exact matches still score identically to Phase 8's behavior; near-misses
    (stem matches like "class" vs "classroom") now earn partial credit
    instead of zero."""
    haystack = f"{memory.title} {memory.content}"
    return relevance_score(haystack, keywords)


def _conversation_context_score(memory: Memory, recent_memory_ids: Set[str]) -> float:
    """Small boost if this memory (or its type) has come up earlier in the
    current conversation - a cheap proxy for topical continuity without
    needing embeddings.
    """
    return 1.0 if memory.id in recent_memory_ids else 0.0


def rank_memories(
    memories: List[Memory],
    keywords: Optional[List[str]] = None,
    target_types: Optional[Set[str]] = None,
    recent_memory_ids: Optional[Set[str]] = None,
    now: Optional[datetime] = None,
) -> List[Memory]:
    """Score and sort memories by recency, importance, pinned status, memory
    type match, keyword relevance, and conversation context - a deterministic
    weighted sum, not a learned ranker or embedding similarity.
    """
    now = now or datetime.now(timezone.utc)
    keywords = keywords or []
    recent_memory_ids = recent_memory_ids or set()

    scored = []
    for memory in memories:
        score = (
            _WEIGHTS["recency"] * _recency_score(memory, now)
            + _WEIGHTS["importance"] * _importance_score(memory)
            + _WEIGHTS["pinned"] * _pinned_score(memory)
            + _WEIGHTS["type_match"] * _type_match_score(memory, target_types)
            + _WEIGHTS["keyword_relevance"] * _keyword_relevance_score(memory, keywords)
            + _WEIGHTS["conversation_context"] * _conversation_context_score(memory, recent_memory_ids)
        )
        scored.append((score, memory))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [memory for _, memory in scored]
