import difflib
from typing import Optional, List, Dict, Any
from datetime import datetime
from app.utils.time import utc_now
from sqlalchemy import text
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

    async def init_fts(self) -> None:
        """Initialize SQLite FTS5 table for full-text search if not exists."""
        try:
            await self.db.execute(text("""
                CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
                    id UNINDEXED,
                    title,
                    content,
                    category,
                    tags
                );
            """))
            await self.db.flush()
        except Exception:
            # FTS5 might already exist or SQLite fallback
            pass

    async def sync_fts_entry(self, memory: Memory) -> None:
        """Sync or update FTS index entry."""
        try:
            tags_str = " ".join(memory.tags) if isinstance(memory.tags, list) else str(memory.tags or "")
            await self.db.execute(
                text("DELETE FROM memories_fts WHERE id = :id"),
                {"id": memory.id}
            )
            if memory.deleted_at is None:
                await self.db.execute(
                    text("""
                        INSERT INTO memories_fts(id, title, content, category, tags)
                        VALUES (:id, :title, :content, :category, :tags)
                    """),
                    {
                        "id": memory.id,
                        "title": memory.title,
                        "content": memory.content,
                        "category": memory.category,
                        "tags": tags_str
                    }
                )
            await self.db.flush()
        except Exception:
            pass

    async def create_memory(self, obj_in: Dict[str, Any]) -> Memory:
        memory = await self.create(obj_in)
        await self.sync_fts_entry(memory)
        return memory

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
        """Perform keyword and FTS search."""
        query_str_clean = query_str.strip()
        if not query_str_clean:
            return await self.get_filtered(memory_type=memory_type, limit=limit)

        # First attempt FTS search if available
        matched_ids = []
        try:
            fts_res = await self.db.execute(
                text("SELECT id FROM memories_fts WHERE memories_fts MATCH :query LIMIT :limit"),
                {"query": f"{query_str_clean}*", "limit": limit}
            )
            matched_ids = [row[0] for row in fts_res.fetchall()]
        except Exception:
            matched_ids = []

        not_expired = (Memory.expires_at.is_(None)) | (Memory.expires_at > utc_now())

        if matched_ids:
            query = select(Memory).filter(Memory.id.in_(matched_ids), Memory.deleted_at.is_(None), not_expired)
            if memory_type:
                query = query.filter(Memory.memory_type == memory_type)
            result = await self.db.execute(query)
            return result.scalars().all()

        # Fallback to SQL LIKE keyword search
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
            await self.sync_fts_entry(memory)
        return memory

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
