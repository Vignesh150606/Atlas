"""Phase 9: memory lifecycle maintenance - staleness flagging.

Memory has carried `confidence`, `last_used`, `access_count`, and
`verification_state` fields since Phase 5, but nothing besides
MemoryRepository.record_usage (recency/access-count bookkeeping, and now
also a small Phase 9 confidence bump - see that method's docstring) ever
wrote to `verification_state`. This service is the other half: identifying
memories that have gone stale - old, rarely (or never) re-confirmed, and
low-confidence - and flagging them, so ranking and future UI can eventually
treat them differently from a fresh, frequently-used memory.

Deliberately NOT run on every chat turn: scanning every memory's staleness
on the hot path of every request would add real latency for a signal that
only needs to be recomputed occasionally (staleness changes over days, not
seconds). This is a maintenance operation - see
backend/scripts/refresh_memory_lifecycle.py for a runnable entry point, the
same "explicit maintenance step, not baked into the request path" pattern
already used for e.g. FTS index sync in MemoryRepository.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.memory_repository import MemoryRepository
from app.models.memory import Memory, VerificationState

# Deliberately simple, documented thresholds (not tuned/learned) - matches
# the rest of this codebase's "deterministic, explainable heuristics over
# a model" philosophy (see app/retrieval/ranking.py's weight comment).
DEFAULT_STALE_AFTER_DAYS = 90
DEFAULT_STALE_CONFIDENCE_THRESHOLD = 50


@dataclass
class StalenessReport:
    scanned: int
    flagged_stale: List[str]  # memory ids newly transitioned to STALE
    already_stale: int
    pinned_skipped: int  # pinned memories are never auto-flagged stale


@dataclass
class ExpiryReport:
    scanned: int
    deleted: List[str]  # memory ids hard-deleted for having a past expires_at


class MemoryLifecycleService:
    """Maintenance operations over Memory.confidence /
    Memory.verification_state - separate from MemoryRepository's
    per-request `record_usage` bookkeeping, since these run on a schedule,
    not per chat turn.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repository = MemoryRepository(db)

    async def flag_stale_memories(
        self,
        stale_after_days: int = DEFAULT_STALE_AFTER_DAYS,
        confidence_threshold: int = DEFAULT_STALE_CONFIDENCE_THRESHOLD,
    ) -> StalenessReport:
        """A memory is flagged STALE when *both* hold:
        - it hasn't been used (retrieved into a real prompt - see
          record_usage) in `stale_after_days`, using last_used if the
          memory has ever been used, created_at otherwise; and
        - its confidence is at or below `confidence_threshold`.

        Requiring both avoids over-flagging: a memory can be old but still
        high-confidence (a stable fact like a birthday), or recent but
        already low-confidence (contradicted soon after being extracted) -
        neither alone is a reliable staleness signal on its own.

        Pinned memories are never auto-flagged: pinning is an explicit user
        signal that overrides automatic lifecycle heuristics (consistent
        with `is_pinned` already being weighted heavily in ranking - see
        app/retrieval/ranking.py's `_pinned_score`).

        CONFIRMED memories are also left alone - the user already vouched
        for them, and an automatic heuristic re-flagging something a human
        explicitly confirmed would be a worse experience than doing nothing.

        Already-STALE memories are counted but not re-processed (idempotent
        - running this twice in a row doesn't change anything the second
        time).
        """
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=stale_after_days)

        candidates = await self.repository.get_filtered(limit=10_000)
        flagged: List[str] = []
        already_stale = 0
        pinned_skipped = 0

        for memory in candidates:
            if memory.verification_state == VerificationState.STALE.value:
                already_stale += 1
                continue
            if memory.is_pinned:
                pinned_skipped += 1
                continue
            if memory.verification_state == VerificationState.CONFIRMED.value:
                continue

            reference = memory.last_used or memory.created_at
            if reference is None:
                continue
            if reference.tzinfo is None:
                reference = reference.replace(tzinfo=timezone.utc)

            is_old = reference < cutoff
            is_low_confidence = (memory.confidence or 0) <= confidence_threshold
            if is_old and is_low_confidence:
                memory.verification_state = VerificationState.STALE.value
                self.db.add(memory)
                flagged.append(memory.id)

        if flagged:
            await self.db.flush()

        return StalenessReport(
            scanned=len(candidates),
            flagged_stale=flagged,
            already_stale=already_stale,
            pinned_skipped=pinned_skipped,
        )

    async def expire_temporary_context(self) -> ExpiryReport:
        """Phase 10: the other half of the Personal Context Engine's
        "prevent temporary information from becoming permanent memory
        accidentally" requirement. `MemoryRepository.get_filtered`/
        `search` already exclude expired rows from every read path (soft
        expiry, immediate), but the rows themselves would otherwise sit
        in the table forever - this is the periodic hard-delete, same
        "explicit maintenance step, not baked into the request path"
        pattern as `flag_stale_memories` above, run from the same
        `scripts/refresh_memory_lifecycle.py` entry point.

        Hard delete (not soft_delete-then-leave-forever): temporary
        context is, by construction, not worth keeping around even in a
        soft-deleted/recoverable state - it was never a real fact to
        preserve a history of, just short-lived working context.
        """
        now = datetime.now(timezone.utc)
        candidates = await self.repository.get_filtered(include_expired=True, limit=10_000)
        deleted: List[str] = []
        for memory in candidates:
            if memory.expires_at is None:
                continue
            expires_at = memory.expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at <= now:
                await self.db.delete(memory)
                deleted.append(memory.id)
        if deleted:
            await self.db.flush()
        return ExpiryReport(scanned=len(candidates), deleted=deleted)
