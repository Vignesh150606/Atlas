from pydantic import BaseModel, Field
from typing import Optional, List, Any, Dict
from datetime import datetime
from app.utils.time import utc_now
from app.schemas.reminder import ReminderResponse
from app.schemas.task import TaskResponse
from app.schemas.routine import RoutineResponse


class BriefingMemoryItem(BaseModel):
    """Deliberately a small, flattened projection of Memory - the daily
    briefing is a scannable summary, not a full memory export (use
    GET /api/v1/memory for that)."""
    id: str
    title: str
    category: str
    importance: int


class DailyBriefingResponse(BaseModel):
    generated_at: datetime = Field(default_factory=utc_now)
    upcoming_reminders: List[ReminderResponse] = Field(default_factory=list)
    incomplete_tasks: List[TaskResponse] = Field(default_factory=list)
    routines_today: List[RoutineResponse] = Field(default_factory=list)
    important_memories: List[BriefingMemoryItem] = Field(default_factory=list)
    stale_memory_count: int = 0
    narrative: str = Field(
        default="", description="Short, deterministic plain-text summary of the sections above (no LLM call)."
    )


class ProactiveSuggestion(BaseModel):
    """One deterministic, rule-based suggestion (mission brief section 6:
    'produce suggestions/notifications only' - never an instruction to
    execute anything). `suggestion_type` is a small closed set so a
    client can render/group without string-matching `message`."""
    suggestion_type: str = Field(
        ..., description="overdue_reminder | due_soon_reminder | stale_task | routine_time | stale_memories"
    )
    message: str
    related_id: Optional[str] = None
    related_type: Optional[str] = None  # "reminder" | "task" | "routine" | "memory"


class ProactiveSuggestionsResponse(BaseModel):
    generated_at: datetime = Field(default_factory=utc_now)
    suggestions: List[ProactiveSuggestion] = Field(default_factory=list)
