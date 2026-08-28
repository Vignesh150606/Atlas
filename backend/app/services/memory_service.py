from datetime import datetime, timedelta
from app.utils.time import utc_now
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.memory_repository import MemoryRepository
from app.schemas.memory import MemoryCreate, MemoryUpdate, MemoryFilterParams
from app.models.memory import Memory, MemoryType

# Phase 10: Personal Context Engine. "Temporary context" (mission brief
# section 1: "distinguish permanent preferences... [from] temporary
# context... prevent temporary information from becoming permanent
# memory accidentally") lives in the same `memories` table as everything
# else (no second memory system - see the architectural rule in the
# mission brief section 16) but is tagged and TTL'd so it behaves
# differently: excluded from retrieval once expired (see
# MemoryRepository.get_filtered/search), never pinned, never counted as
# a "real" fact.
TEMPORARY_CONTEXT_CATEGORY = "temporary_context"
DEFAULT_TEMPORARY_CONTEXT_TTL_MINUTES = 240  # 4 hours - a work/study-session-scale default, not a whole day

class MemoryService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repository = MemoryRepository(db)

    async def create_memory(self, memory_in: MemoryCreate, allow_duplicate: bool = False) -> Memory:
        """Create memory with validation and optional duplicate checking."""
        if not memory_in.title.strip() or not memory_in.content.strip():
            raise ValueError("Memory title and content cannot be empty.")

        if not allow_duplicate:
            existing = await self.repository.find_duplicate(memory_in.title, memory_in.content)
            if existing:
                return existing

        data = memory_in.model_dump()
        data["memory_type"] = memory_in.memory_type.value
        return await self.repository.create_memory(data)

    async def get_memory(self, memory_id: str) -> Optional[Memory]:
        return await self.repository.get_by_id(memory_id)

    async def update_memory(self, memory_id: str, memory_in: MemoryUpdate) -> Optional[Memory]:
        memory = await self.repository.get_by_id(memory_id)
        if not memory:
            return None

        update_data = memory_in.model_dump(exclude_unset=True)
        if "memory_type" in update_data and update_data["memory_type"] is not None:
            update_data["memory_type"] = update_data["memory_type"].value

        updated = await self.repository.update(memory, update_data)
        await self.repository.sync_fts_entry(updated)
        return updated

    async def delete_memory(self, memory_id: str) -> Optional[Memory]:
        return await self.repository.soft_delete(memory_id)

    async def list_memories(self, filters: MemoryFilterParams) -> List[Memory]:
        type_str = filters.memory_type.value if filters.memory_type else None
        return await self.repository.get_filtered(
            memory_type=type_str,
            category=filters.category,
            tag=filters.tag,
            importance=filters.importance,
            is_pinned=filters.is_pinned,
            source=filters.source,
            skip=filters.skip,
            limit=filters.limit
        )

    async def search_memories(self, query: str, memory_type: Optional[str] = None, limit: int = 50) -> List[Memory]:
        return await self.repository.search(query_str=query, memory_type=memory_type, limit=limit)

    async def get_recent_memories(self, limit: int = 10) -> List[Memory]:
        return await self.repository.get_filtered(limit=limit)

    async def get_important_memories(self, min_importance: int = 4, limit: int = 20) -> List[Memory]:
        memories = await self.repository.get_filtered(limit=100)
        return [m for m in memories if m.importance >= min_importance][:limit]

    async def get_pinned_memories(self) -> List[Memory]:
        return await self.repository.get_filtered(is_pinned=True)

    async def create_temporary_context(
        self,
        title: str,
        content: str,
        ttl_minutes: int = DEFAULT_TEMPORARY_CONTEXT_TTL_MINUTES,
        tags: Optional[List[str]] = None,
    ) -> Memory:
        """Phase 10: the one write path for short-lived context (e.g. 'the
        user is currently working on X' inferred for this session only) -
        deliberately separate from `create_memory`, not an optional flag
        on it, so every call site is an explicit, readable decision about
        which kind of memory it's creating. Never deduplicated against
        existing memories (`allow_duplicate=True`): temporary context is
        cheap, self-expiring, and checking it against the whole memory
        table for near-duplicates would be wasted work for something that
        disappears in hours anyway.
        """
        memory_in = MemoryCreate(
            title=title,
            content=content,
            memory_type=MemoryType.NOTE,
            category=TEMPORARY_CONTEXT_CATEGORY,
            importance=2,
            source="temporary_context",
            tags=(tags or []) + ["temporary_context"],
        )
        data = memory_in.model_dump()
        data["memory_type"] = memory_in.memory_type.value
        data["expires_at"] = utc_now() + timedelta(minutes=ttl_minutes)
        return await self.repository.create_memory(data)
