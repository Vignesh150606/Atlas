import difflib
from typing import Optional, List, Dict, Any
from datetime import datetime
from app.utils.time import utc_now
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.repositories.base import BaseRepository
from app.models.memory import Memory, MemoryType

# Phase 9: near-duplicate content similarity threshold (difflib
# SequenceMatcher ratio, 0-1). Deliberately conservative/high - this is a
# false-positive-averse check ("is this basically a re-statement of an
# existing memory?"), not a loose "roughly similar topic" match. 100
# candidates is a small, bounded scan (see find_duplicate), not a full
# table scan, consistent with the candidate_pool_size caps used elsewhere
# in retrieval (e.g. RetrievalService).
_NEAR_DUPLICATE_SIMILARITY_THRESHOLD = 0.90
_NEAR_DUPLICATE_CANDIDATE_LIMIT = 100
# Phase 9: bounds for the confidence lifecycle field (0-100 int on Memory).
_MAX_CONFIDENCE = 100
_USAGE_CONFIDENCE_INCREMENT = 2  # small, weak-corroboration bump per genuine retrieval-and-use

class MemoryRepository(BaseRepository[Memory]):
    def __init__(self, db: AsyncSession):
        super().__init__(Memory, db)

    # Phase 12 (deployment hardening, docs/MASTER_PLAN.md #2.4): this file
    # used to also carry init_fts()/sync_fts_entry() building a SQLite
    # FTS5 virtual table (memories_fts). init_fts() was called only from
    # tests/test_memory_repository.py - never from application code (not
    # app.main's lifespan, not any service) - so the table never existed
    # in production, and sync_fts_entry()/search()'s FTS query both ran
    # inside a bare `except Exception: pass`, so every write silently no-
    # op'd and every search silently fell through to the LIKE path below
    # with no way to tell it was doing so. It was also raw SQLite-specific
    # SQL (`CREATE VIRTUAL TABLE ... USING fts5`), which would fail
    # permanently - and just as silently - on the Postgres deployment
    # target (see docs/DEPLOYMENT_PLAN.md #4). Deleted rather than fixed:
    # the LIKE path plus app/retrieval/ranking.py's semantic-like scoring
    # already covers this app's actual scale (single user, low thousands
    # of rows - see docs/ARCHITECTURE_TARGET.md #6.4), and a real FTS/
    # search upgrade should be a deliberate, tested addition, not a
    # silently-dead feature kept around because deleting it felt like a
    # bigger change than it is.

    async def create_memory(self, obj_in: Dict[str, Any]) -> Memory:
        return await self.create(obj_in)

    async def get_by_id(self, memory_id: str, include_deleted: bool = False) -> Optional[Memory]:
        query = select(Memory).filter(Memory.id == memory_id)
        if not include_deleted:
            query = query.filter(Memory.deleted_at.is_(None))
        result = await self.db.execute(query)
        return result.scalars().first()

    async def get_filtered(
        self,
        memory_type: Optional[str] = None,
        category: Optional[str] = None,
        tag: Optional[str] = None,
        importance: Optional[int] = None,
        is_pinned: Optional[bool] = None,
        source: Optional[str] = None,
        include_deleted: bool = False,
        include_expired: bool = False,
        skip: int = 0,
        limit: int = 100
    ) -> List[Memory]:
        query = select(Memory)
        if not include_deleted:
            query = query.filter(Memory.deleted_at.is_(None))
        if not include_expired:
            # Phase 10: Personal Context Engine - excludes temporary
            # context whose TTL has passed (see MemoryService.
            # create_temporary_context). expires_at is None for every
            # permanent memory (all of them, pre-Phase-10), so this is a
            # no-op for every existing caller/test until something
            # actually sets expires_at.
            query = query.filter(
                (Memory.expires_at.is_(None)) | (Memory.expires_at > utc_now())
            )

        if memory_type:
            query = query.filter(Memory.memory_type == memory_type)
        if category:
            query = query.filter(Memory.category == category)
        if importance is not None:
            query = query.filter(Memory.importance == importance)
        if is_pinned is not None:
            query = query.filter(Memory.is_pinned == is_pinned)
        if source:
            query = query.filter(Memory.source == source)

        query = query.order_by(Memory.created_at.desc()).offset(skip).limit(limit)
        result = await self.db.execute(query)
        memories = result.scalars().all()

        # In-memory tag filter if requested
        if tag:
            memories = [m for m in memories if isinstance(m.tags, list) and tag in m.tags]

        return memories

    async def search(self, query_str: str, memory_type: Optional[str] = None, limit: int = 50) -> List[Memory]:
        """Keyword search via SQL LIKE. See the comment above create_memory
        for why this is the only path now - a dead, silently-failing FTS5
        attempt used to run first."""
        query_str_clean = query_str.strip()
        if not query_str_clean:
            return await self.get_filtered(memory_type=memory_type, limit=limit)

        not_expired = (Memory.expires_at.is_(None)) | (Memory.expires_at > utc_now())

        like_pattern = f"%{query_str_clean}%"
        query = select(Memory).filter(
            Memory.deleted_at.is_(None),
            not_expired,
            (Memory.title.ilike(like_pattern) | Memory.content.ilike(like_pattern) | Memory.category.ilike(like_pattern))
        )
        if memory_type:
            query = query.filter(Memory.memory_type == memory_type)
        query = query.order_by(Memory.created_at.desc()).limit(limit)

        result = await self.db.execute(query)
        return result.scalars().all()

    async def soft_delete(self, memory_id: str) -> Optional[Memory]:
        memory = await self.get_by_id(memory_id, include_deleted=False)
        if memory:
            memory.deleted_at = utc_now()
            self.db.add(memory)
            await self.db.flush()
        return memory

    async def count_by_verification_state(self, verification_state: str) -> int:
        """Phase 12: replaces ProactiveSuggestionService's previous
        `len(await get_filtered(limit=1000))` scan - it fetched and
        deserialized up to 1000 full Memory rows just to count how many
        matched one field, every time the endpoint was polled (see
        docs/ARCHITECTURE_TARGET.md #9's bottleneck list). A COUNT query
        does the same job without materializing any rows."""
        query = (
            select(func.count())
            .select_from(Memory)
            .filter(Memory.deleted_at.is_(None), Memory.verification_state == verification_state)
        )
        result = await self.db.execute(query)
        return result.scalar_one()

    async def find_duplicate(
        self, title: str, content: str, memory_type: Optional[str] = None
    ) -> Optional[Memory]:
        """Exact title/content match first (unchanged Phase 1-8 behavior),
        then Phase 9: near-duplicate detection over a bounded candidate pool
        - catches paraphrased re-statements ("I like coffee" vs "I really
        like coffee a lot") that exact matching misses and would otherwise
        pile up as separate memories every time the same fact gets
        mentioned slightly differently.

        `memory_type`, when given, scopes the near-duplicate candidate pool
        to that type only (a TASK shouldn't be flagged as a near-duplicate
        of a similarly-worded NOTE) - optional and additive, every existing
        caller that doesn't pass it keeps the old (type-unscoped) exact-match
        behavior exactly, and near-duplicate scanning still runs, just over
        the most recent candidates of any type.
        """
        query = select(Memory).filter(
            Memory.deleted_at.is_(None),
            (Memory.title.ilike(title.strip())) | (Memory.content.ilike(content.strip()))
        )
        result = await self.db.execute(query)
        exact = result.scalars().first()
        if exact:
            return exact

        content_clean = content.strip().lower()
        if not content_clean:
            return None

        candidates = await self.get_filtered(memory_type=memory_type, limit=_NEAR_DUPLICATE_CANDIDATE_LIMIT)
        best_match: Optional[Memory] = None
        best_score = 0.0
        for candidate in candidates:
            score = difflib.SequenceMatcher(None, content_clean, (candidate.content or "").strip().lower()).ratio()
            if score > best_score:
                best_score = score
                best_match = candidate

        if best_match and best_score >= _NEAR_DUPLICATE_SIMILARITY_THRESHOLD:
            return best_match
        return None

    async def record_usage(self, memory_ids: List[str]) -> None:
        """Lifecycle update: called whenever memories are actually retrieved
        and injected into a prompt (not just fetched/listed). Bumps
        access_count and last_used so ranking (recency-of-use) and staleness
        detection have real data to work with.

        Phase 9: also nudges `confidence` up slightly (capped at 100) - a
        memory that keeps getting retrieved and actually used in
        conversation is weak but real corroboration that it's still
        accurate, distinct from `access_count`/`last_used` which only track
        *when*, not how much ATLAS should trust the content. This finishes
        what Phase 5 started: `confidence` has existed on the model since
        Phase 5 but nothing updated it until now.
        """
        if not memory_ids:
            return
        result = await self.db.execute(select(Memory).filter(Memory.id.in_(memory_ids)))
        now = utc_now()
        for memory in result.scalars().all():
            memory.access_count = (memory.access_count or 0) + 1
            memory.last_used = now
            memory.confidence = min(_MAX_CONFIDENCE, (memory.confidence or 0) + _USAGE_CONFIDENCE_INCREMENT)
            self.db.add(memory)
        await self.db.flush()
