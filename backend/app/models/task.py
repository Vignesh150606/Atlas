"""Phase 10: real Task domain model.

Distinct from `Reminder` (app/models/reminder.py): a Reminder is anchored
to a specific point in time it fires at; a Task is an item of work that
may or may not have a due date and is tracked by *status*, not by firing.
Also distinct from Memory(memory_type=TASK) (Phase 1-9's "I have to X by
Y" / "Todo: X" extraction, `MemoryExtractor` rule 3, unchanged in Phase
10) - that path remains a passive record of task-shaped things mentioned
in chat; this is the real, listable/completable/prioritizable task
management the Phase 10 mission brief asks for (section 3), reachable via
`TaskSkill` (chat) and `app/api/v1/endpoints/tasks.py` (direct API, e.g.
a future Android Tasks screen).
"""
import uuid
from enum import Enum
from sqlalchemy import Column, String, Text, DateTime
from app.models.base import TimestampModel


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TaskPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Task(TimestampModel):
    __tablename__ = "tasks"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String, nullable=False, default=TaskStatus.PENDING.value, index=True)
    priority = Column(String, nullable=False, default=TaskPriority.MEDIUM.value, index=True)
    due_at = Column(DateTime, nullable=True, index=True)
    completed_at = Column(DateTime, nullable=True)
    source = Column(String, nullable=False, default="chat", index=True)  # "chat" or "api"
    conversation_id = Column(String, nullable=True, index=True)
