"""Phase 9 maintenance script: flag stale memories.

Deliberately a standalone script, not wired into any request path (see
app/services/memory_lifecycle_service.py's module docstring for why) - run
it periodically (e.g. a daily cron job / scheduled task) against the same
database the FastAPI app uses.

Usage:
    cd backend
    python scripts/refresh_memory_lifecycle.py
    python scripts/refresh_memory_lifecycle.py --stale-after-days 60 --confidence-threshold 40
    python scripts/refresh_memory_lifecycle.py --skip-expiry       # staleness only
    python scripts/refresh_memory_lifecycle.py --skip-staleness    # expiry only

Phase 10: also runs `expire_temporary_context` (hard-deletes expired
temporary-context memories - see that method's docstring) by default.
Deliberately kept as ONE script covering both memory-lifecycle
maintenance operations rather than a second standalone script - both are
"periodic, not on the request path" maintenance over the same `memories`
table, so they belong together (see mission brief section 16's
architectural rule against parallel implementations).
"""
import argparse
import asyncio
import sys
from pathlib import Path

# Allow running as `python scripts/refresh_memory_lifecycle.py` from the
# `backend/` directory without needing the package pre-installed.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database.session import AsyncSessionLocal  # noqa: E402
from app.services.memory_lifecycle_service import (  # noqa: E402
    MemoryLifecycleService,
    DEFAULT_STALE_AFTER_DAYS,
    DEFAULT_STALE_CONFIDENCE_THRESHOLD,
)


async def main(stale_after_days: int, confidence_threshold: int, skip_staleness: bool, skip_expiry: bool) -> None:
    async with AsyncSessionLocal() as db:
        service = MemoryLifecycleService(db)

        if not skip_staleness:
            report = await service.flag_stale_memories(
                stale_after_days=stale_after_days,
                confidence_threshold=confidence_threshold,
            )
            await db.commit()
            print(f"Scanned {report.scanned} memories.")
            print(f"Newly flagged stale: {len(report.flagged_stale)}")
            if report.flagged_stale:
                for memory_id in report.flagged_stale:
                    print(f"  - {memory_id}")
            print(f"Already stale (unchanged): {report.already_stale}")
            print(f"Pinned (skipped): {report.pinned_skipped}")

        if not skip_expiry:
            expiry_report = await service.expire_temporary_context()
            await db.commit()
            print(f"Scanned {expiry_report.scanned} memories for expiry.")
            print(f"Expired temporary-context memories deleted: {len(expiry_report.deleted)}")
            if expiry_report.deleted:
                for memory_id in expiry_report.deleted:
                    print(f"  - {memory_id}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ATLAS memory lifecycle maintenance: staleness flagging + temporary-context expiry.")
    parser.add_argument("--stale-after-days", type=int, default=DEFAULT_STALE_AFTER_DAYS)
    parser.add_argument("--confidence-threshold", type=int, default=DEFAULT_STALE_CONFIDENCE_THRESHOLD)
    parser.add_argument("--skip-staleness", action="store_true", help="Skip staleness flagging, only run temporary-context expiry.")
    parser.add_argument("--skip-expiry", action="store_true", help="Skip temporary-context expiry, only run staleness flagging.")
    args = parser.parse_args()
    asyncio.run(main(args.stale_after_days, args.confidence_threshold, args.skip_staleness, args.skip_expiry))
