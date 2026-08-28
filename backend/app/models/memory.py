import uuid
from enum import Enum
from datetime import datetime
from sqlalchemy import Column, String, Text, Integer, Boolean, DateTime, JSON
from app.models.base import TimestampModel

class MemoryType(str, Enum):
    FACT = "fact"
    PREFERENCE = "preference"
    TASK = "task"
    EVENT = "event"
    CLASS = "class"
    TIMETABLE = "timetable"
    NOTE = "note"
    PROJECT = "project"
    DOCUMENT = "document"
    CONVERSATION = "conversation"
    CONTACT = "contact"
    GOAL = "goal"

class VerificationState(str, Enum):
    """Tracks how much ATLAS should trust a memory. Not user-facing yet (no
    confirm/reject endpoint exists) - this is the foundation the lifecycle
    logic (auto-updated on each use) writes to, ready for a future UI.
    """
    UNVERIFIED = "unverified"   # default: extracted or created, never confirmed
    CONFIRMED = "confirmed"     # user has explicitly confirmed this is correct
    STALE = "stale"             # flagged as possibly outdated (e.g. superseded)

class Memory(TimestampModel):
    __tablename__ = "memories"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    title = Column(String, nullable=False, index=True)
    content = Column(Text, nullable=False)
    memory_type = Column(String, nullable=False, default=MemoryType.FACT.value, index=True)
    category = Column(String, nullable=False, default="general", index=True)
    importance = Column(Integer, nullable=False, default=3, index=True)
    is_pinned = Column(Boolean, nullable=False, default=False, index=True)
    source = Column(String, nullable=False, default="manual", index=True)
    tags = Column(JSON, nullable=False, default=list)
    structured_data = Column(JSON, nullable=False, default=dict)
    deleted_at = Column(DateTime, nullable=True, index=True)

    # --- Lifecycle fields (Phase 5) ---
    confidence = Column(Integer, nullable=False, default=100)  # 0-100; rule-based extraction starts high
    last_used = Column(DateTime, nullable=True, index=True)  # set when retrieved and actually injected into a prompt
    access_count = Column(Integer, nullable=False, default=0)
    verification_state = Column(String, nullable=False, default=VerificationState.UNVERIFIED.value)

    # --- Phase 10: Personal Context Engine ---
    # Nullable, and None for every memory created before Phase 10 and for
    # every *permanent* memory since (preferences, facts, pinned items).
    # Set only via MemoryService.create_temporary_context() for genuinely
    # short-lived context ("the user is currently doing X") that should
    # stop being retrievable once it's no longer relevant, instead of
    # quietly living forever in the same table as a real preference - see
    # that method's docstring and docs/Phase10_ArchitectureUpdate.md for
    # the full "prevent temporary information from becoming permanent
    # memory accidentally" reasoning (mission brief section 1). Expired
    # rows are excluded at read time (MemoryRepository.get_filtered) and
    # hard-deleted by the periodic maintenance script (see
    # MemoryLifecycleService.expire_temporary_context) - not a special
    # memory_type, so every existing type-based rule (retrieval,
    # ranking, extraction) is unaffected by this column's existence.
    expires_at = Column(DateTime, nullable=True, index=True)
