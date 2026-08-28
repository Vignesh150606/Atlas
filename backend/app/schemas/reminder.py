from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from app.models.reminder import ReminderStatus, RecurrenceType


class ReminderCreate(BaseModel):
    """Direct/API creation (e.g. a future Android 'Add Reminder' screen
    with a real date/time picker) - due_at is already resolved, no text
    parsing involved. See ReminderCreateFromText for the chat path."""
    title: str = Field(..., min_length=1)
    due_at: Optional[datetime] = None
    timezone: str = Field(default="UTC")
    recurrence: RecurrenceType = Field(default=RecurrenceType.NONE)
    recurrence_days: List[int] = Field(default_factory=list)
    notes: Optional[str] = None


class ReminderCreateFromText(BaseModel):
    """Chat/free-text creation - reuses the same parsing ReminderSkill
    uses (app/services/reminder_service.py::create_from_text), exposed
    here so the API and chat paths can never silently disagree about how
    a phrase like 'tomorrow at 7pm' is interpreted."""
    text: str = Field(..., min_length=1, description="e.g. 'submit the report tomorrow at 7pm'")
    reference_time: Optional[datetime] = None
    timezone: str = Field(default="UTC")
    conversation_id: Optional[str] = None


class ReminderUpdate(BaseModel):
    title: Optional[str] = None
    due_at: Optional[datetime] = None
    recurrence: Optional[RecurrenceType] = None
    recurrence_days: Optional[List[int]] = None
    status: Optional[ReminderStatus] = None
    notes: Optional[str] = None


class ReminderResponse(BaseModel):
    id: str
    title: str
    due_at: Optional[datetime] = None
    raw_when_text: Optional[str] = None
    timezone: str
    recurrence: str
    recurrence_days: List[int] = Field(default_factory=list)
    status: str
    completed_at: Optional[datetime] = None
    source: str
    conversation_id: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
