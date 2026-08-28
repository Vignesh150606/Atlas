import math
from datetime import datetime, timezone
from typing import Dict, List, Optional
from app.models.document import Document
from app.retrieval.semantic_match import relevance_score

# Documents don't have importance/pinned like memories do, so the weight
# distribution differs from retrieval/ranking.py's rank_memories: keyword
# relevance dominates (that's the primary signal for "is this document
# about what was asked"), with entity matches as a secondary structured
# signal and recency as a mild tiebreaker.
_WEIGHTS = {
    "recency": 0.20,
    "keyword_relevance": 0.45,
    "entity_match": 0.25,
    "type_match": 0.10,
}


def _recency_score(document: Document, now: datetime) -> float:
    reference = document.created_at
    if reference is None:
        return 0.0
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=timezone.utc)
    age_days = max((now - reference).total_seconds() / 86400.0, 0.0)
    return math.exp(-age_days / 30.0)


def _keyword_relevance_score(document: Document, keywords: List[str]) -> float:
    """Phase 9: delegates to the shared semantic-like scorer (see
    app/retrieval/semantic_match.py) - previously duplicated near-verbatim
    from app/retrieval/ranking.py's own private copy."""
    haystack = f"{document.title} {document.content}"
    return relevance_score(haystack, keywords)


def _entity_match_score(document: Document, entity_match_counts: Dict[str, int]) -> float:
    count = entity_match_counts.get(document.id, 0)
    if count <= 0:
        return 0.0
    return min(1.0, count / 3.0)  # 3+ matching entities is treated as a strong signal


def _type_match_score(document: Document, target_types: Optional[set]) -> float:
    if not target_types:
        return 0.5  # neutral when no specific type was inferred for this query
    return 1.0 if document.file_type in target_types else 0.0


def rank_documents(
    documents: List[Document],
    keywords: Optional[List[str]] = None,
    entity_match_counts: Optional[Dict[str, int]] = None,
    target_types: Optional[set] = None,
    now: Optional[datetime] = None,
) -> List[Document]:
    now = now or datetime.now(timezone.utc)
    keywords = keywords or []
    entity_match_counts = entity_match_counts or {}

    scored = []
    for document in documents:
        score = (
            _WEIGHTS["recency"] * _recency_score(document, now)
            + _WEIGHTS["keyword_relevance"] * _keyword_relevance_score(document, keywords)
            + _WEIGHTS["entity_match"] * _entity_match_score(document, entity_match_counts)
            + _WEIGHTS["type_match"] * _type_match_score(document, target_types)
        )
        scored.append((score, document))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [document for _, document in scored]
