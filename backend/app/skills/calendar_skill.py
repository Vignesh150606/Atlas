"""Phase 9: CalendarSkill.

Complements TimetableTool (app/tools/timetable_tool.py), which only reads
existing CLASS/TIMETABLE/EVENT memories - there was previously no
chat-driven way to add a new event at all. Persistence is handled by
MemoryExtractor's rule 6 (same `parse_event` used here); this skill only
builds the confirmation, for the same duplicate-write reasons documented in
app/skills/notes_skill.py.
"""
from typing import Optional
from app.skills.base import Skill, SkillMatch
from app.skills.registry import register_skill
from app.tools.base import ToolResult
from app.memory.memory_extractor import MemoryExtractor


@register_skill
class CalendarSkill(Skill):
    name = "calendar"
    description = "Confirms an explicit 'add an event' / 'put ... on my calendar' request (persistence stays with MemoryExtractor)."

    def match(self, message: str) -> Optional[SkillMatch]:
        parsed = MemoryExtractor.parse_event(message)
        if not parsed:
            return None
        return SkillMatch(kwargs={"event": parsed["event"], "date": parsed["date"]}, confidence=0.85)

    async def run(self, event: str = "", date: Optional[str] = None, **kwargs) -> ToolResult:
        if not event:
            return ToolResult(tool_name=self.name, success=False, output=None, error="No event text recognized.")
        summary = f"Got it - I've noted the event '{event}'"
        summary += f" on {date}." if date else "."
        return ToolResult(tool_name=self.name, success=True, output=summary)
