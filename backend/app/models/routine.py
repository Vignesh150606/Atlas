"""Phase 10: Routine model (mission brief section 5).

Deliberately the simplest of the three new models: a Routine is pure
user-authored configuration (a name, a rough time-of-day, which days it
applies, and an ordered list of step descriptions) - there is no
inference engine here and none is planned. The mission brief is explicit
("Do NOT automatically infer sensitive or consequential routines...
Routine creation should be explainable... Allow the user to explicitly
create, modify and delete routines") - so unlike Reminder/Task, nothing
in this codebase ever creates or edits a Routine except a direct user
action (API call or the narrow, explicit `RoutineSkill` chat phrasing -
see app/skills/routine_skill.py). ATLAS reads routines (e.g. Daily
Briefing surfaces "your evening routine" if one is scheduled for around
now) but never writes one on its own initiative.
"""
import uuid
from sqlalchemy import Column, String, Boolean, JSON
from app.models.base import TimestampModel


class Routine(TimestampModel):
    __tablename__ = "routines"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    # Ordered, free-text step descriptions ("Drink water", "Review
    # timetable", ...) - deliberately not a separate child table; routines
    # are short, personal checklists, not a project-management structure
    # (see mission brief: "Avoid turning the task system into an
    # unnecessarily complex project-management platform" - the same
    # "keep it personal" principle applies here).
    steps = Column(JSON, nullable=False, default=list)
    # "HH:MM" 24-hour local time-of-day this routine is roughly anchored
    # to, or None if it's not time-anchored (e.g. a routine the user
    # triggers manually rather than one ATLAS would ever proactively
    # mention "around now").
    time_of_day = Column(String, nullable=True)
    # ISO weekday ints (0=Monday..6=Sunday) this routine applies on; empty
    # list means "every day".
    days_of_week = Column(JSON, nullable=False, default=list)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
