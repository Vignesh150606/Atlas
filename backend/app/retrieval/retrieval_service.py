import re
from typing import List, Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.memory_repository import MemoryRepository
from app.models.memory import Memory, MemoryType
from app.core.config import settings
from app.retrieval.ranking import rank_memories

# Maps keyword patterns in the user's message to the memory type(s) that are
# almost certainly what they're asking about. This is the "structured
# retrieval" the mission calls for in place of vector/embedding search:
# deterministic rules over the message text, then a real repository query -
# no similarity scoring involved.
_INTENT_RULES: List[Dict] = [
    {
        "pattern": re.compile(r"\b(class|timetable|schedule|lecture)\b", re.IGNORECASE),
        "memory_types": [MemoryType.CLASS.value, MemoryType.TIMETABLE.value, MemoryType.EVENT.value],
    },
    {
        "pattern": re.compile(r"\b(task|todo|to-do|deadline|due)\b", re.IGNORECASE),
        "memory_types": [MemoryType.TASK.value],
    },
    {
        "pattern": re.compile(r"\b(project|building|working on)\b", re.IGNORECASE),
        "memory_types": [MemoryType.PROJECT.value],
    },
    {
        "pattern": re.compile(r"\b(favorite|prefer|like|love|hate|dislike)\b", re.IGNORECASE),
        "memory_types": [MemoryType.PREFERENCE.value],
    },
    {
        "pattern": re.compile(r"\b(goal|trying to|want to achieve)\b", re.IGNORECASE),
        "memory_types": [MemoryType.GOAL.value],
    },
    {
        "pattern": re.compile(r"\b(contact|phone|email address|reach)\b", re.IGNORECASE),
        "memory_types": [MemoryType.CONTACT.value],
    },
]

_STOPWORDS = {
    "what", "is", "my", "the", "a", "an", "to", "of", "in", "on", "for",
    "do", "does", "did", "i", "you", "your", "it", "this", "that", "are",
    "was", "were", "when", "where", "who", "how", "please", "tell", "me",
    "and", "or", "about", "next", "current", "have", "has", "with",
}


def extract_keywords(message: str, max_keywords: int = 8) -> List[str]:
    """Pull out significant words, stripped of stopwords. Shared by retrieval
    (fallback search + ranking's keyword_relevance factor) and the planner.
    """
    tokens = re.findall(r"[A-Za-z0-9']+", message.lower())
    keywords = [t for t in tokens if t not in _STOPWORDS and len(t) > 2]
    return keywords[:max_keywords]


class RetrievalService:
    """Structured (non-vector) memory retrieval with deterministic ranking.

    Candidate gathering, in order (cast a wide net - ranking narrows it):
    1. Match the user's message against known intent patterns to find
       specific memory type(s) (e.g. "class" -> CLASS/TIMETABLE memories).
    2. Extract significant keywords from the message and search for each via
       the repository's FTS/LIKE search (a full sentence rarely matches
       anything verbatim, so this searches word-by-word instead).
    3. Always include the highest-importance pinned memories as baseline
       candidates - these are things the user explicitly wants remembered.

    All candidates are then scored and sorted by rank_memories() (recency,
    importance, pinned, type match, keyword relevance, conversation context)
    before being trimmed to `limit`. This deliberately does not do embedding
    similarity - see Roadmap.md; vector search is an explicit future phase.

    Memories that make it into the final result have their usage recorded
    (access_count / last_used) - see Memory Lifecycle.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repository = MemoryRepository(db)

    def _matched_types(self, message: str) -> List[str]:
        matched: List[str] = []
        for rule in _INTENT_RULES:
            if rule["pattern"].search(message):
                for t in rule["memory_types"]:
                    if t not in matched:
                        matched.append(t)
        return matched

    async def retrieve(
        self,
        message: str,
        limit: Optional[int] = None,
        history_text: str = "",
        record_usage: bool = True,
    ) -> List[Memory]:
        limit = limit or settings.MAX_RETRIEVED_MEMORIES
        candidate_pool_size = max(limit * 4, 20)  # cast wider than `limit` so ranking has something to rank

        candidates: List[Memory] = []
        seen_ids = set()

        def _add(memories: List[Memory]):
            for m in memories:
                if m.id not in seen_ids:
                    seen_ids.add(m.id)
                    candidates.append(m)

        matched_types = self._matched_types(message)
        for memory_type in matched_types:
            type_matches = await self.repository.get_filtered(memory_type=memory_type, limit=candidate_pool_size)
            _add(type_matches)

        keywords = extract_keywords(message)
        for keyword in keywords:
            if len(candidates) >= candidate_pool_size:
                break
            keyword_matches = await self.repository.search(query_str=keyword, limit=candidate_pool_size)
            _add(keyword_matches)

        pinned = await self.repository.get_filtered(is_pinned=True, limit=candidate_pool_size)
        _add(pinned)

        # Conversation context: keywords from recent history give a small
        # boost to memories that are topically continuous with the ongoing
        # conversation, without needing embeddings.
        history_keywords = extract_keywords(history_text) if history_text else []
        context_boosted_ids = set()
        if history_keywords:
            haystack_ids = {m.id for m in candidates}
            for m in candidates:
                blob = f"{m.title} {m.content}".lower()
                if any(kw in blob for kw in history_keywords):
                    context_boosted_ids.add(m.id)
            context_boosted_ids &= haystack_ids

        ranked = rank_memories(
            candidates,
            keywords=keywords,
            target_types=set(matched_types) if matched_types else None,
            recent_memory_ids=context_boosted_ids,
        )
        final = ranked[:limit]

        if record_usage and final:
            await self.repository.record_usage([m.id for m in final])

        return final
