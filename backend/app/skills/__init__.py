"""Importing this package registers every built-in skill (each module below
applies `@register_skill` at import time - see app/skills/registry.py).
Planner and ToolRouter both import from `app.skills` (not the individual
modules) specifically so this side effect always happens exactly once,
the same "import the package, not the leaf module, so registration
side-effects fire" pattern app/models/__init__.py already uses for
SQLAlchemy model registration.
"""
from app.skills.base import Skill, SkillMatch
from app.skills.registry import SkillRegistry, register_skill
from app.skills.time_skill import TimeSkill
from app.skills.weather_skill import WeatherSkill
from app.skills.search_skill import SearchSkill
from app.skills.notes_skill import NotesSkill
from app.skills.reminder_skill import ReminderSkill
from app.skills.calendar_skill import CalendarSkill
# Phase 10: Personal Assistant & Proactive Intelligence
from app.skills.task_skill import TaskSkill
from app.skills.routine_skill import RoutineSkill
from app.skills.briefing_skill import BriefingSkill

__all__ = [
    "Skill",
    "SkillMatch",
    "SkillRegistry",
    "register_skill",
    "TimeSkill",
    "WeatherSkill",
    "SearchSkill",
    "NotesSkill",
    "ReminderSkill",
    "CalendarSkill",
    "TaskSkill",
    "RoutineSkill",
    "BriefingSkill",
]
