"""Phase 10: BriefingSkill (mission brief section 4).

Deliberately thin: all the actual composition work is
`DailyBriefingService` (app/services/daily_briefing_service.py), reused
as-is - this skill's only job is recognizing an explicit request for a
briefing in chat and handing the structured result to the LLM as a
tool_result (see PromptBuilder) so it can phrase a natural-language
summary. `GET /api/v1/briefing/daily` (app/api/v1/endpoints/briefing.py)
is the same service for a client that wants the structured JSON directly
instead of chat prose - one service, two front doors, not two
implementations.

Deliberately narrow trigger phrasing (explicit "briefing"/"brief me"
asks only) - NOT bare greetings like "good morning", which are far too
ambiguous a signal to fire a multi-section data pull on (see
NotesSkill's docstring for the same "don't false-positive on casual
phrasing" reasoning applied elsewhere in this package).
"""
import re
from typing import Optional
from app.skills.base import Skill, SkillMatch
from app.skills.registry import register_skill
from app.tools.base import ToolResult
from app.services.daily_briefing_service import DailyBriefingService

_BRIEFING_PATTERN = re.compile(
    r"\b(?:daily briefing|my briefing|brief me)\b|\bwhat'?s my day (?:look like|looking like)\b|"
    r"\bgive me (?:a|my) (?:daily )?briefing\b|\bwhat'?s on my plate today\b",
    re.IGNORECASE,
)


@register_skill
class BriefingSkill(Skill):
    name = "briefing"
    description = "Composes a daily briefing (upcoming reminders, incomplete tasks, routines, important memories) from existing services."

    def match(self, message: str) -> Optional[SkillMatch]:
        if _BRIEFING_PATTERN.search(message):
            return SkillMatch(confidence=0.85)
        return None

    async def run(self, **kwargs) -> ToolResult:
        if self.db is None:
            return ToolResult(tool_name=self.name, success=False, output=None, error="No database session available.")

        briefing = await DailyBriefingService(self.db).build()
        output = {
            "narrative": briefing.narrative,
            "upcoming_reminders": [
                {"title": r.title, "due_at": r.due_at.isoformat() if r.due_at else None}
                for r in briefing.upcoming_reminders
            ],
            "incomplete_tasks": [{"title": t.title, "priority": t.priority} for t in briefing.incomplete_tasks],
            "routines_today": [r.name for r in briefing.routines_today],
            "important_memories": [m.title for m in briefing.important_memories],
        }
        return ToolResult(tool_name=self.name, success=True, output=output)
