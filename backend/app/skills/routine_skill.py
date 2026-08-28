"""Phase 10: RoutineSkill (mission brief section 5).

Deliberately narrow, matching the model's own "explicit only, never
inferred" constraint (see app/models/routine.py's docstring): this skill
only ever creates a Routine in direct response to an unambiguous
"create a routine called X..." phrasing with explicit steps, and only
ever reads (list/show) otherwise. It never guesses a routine into
existence from a vaguer message ("I usually stretch after waking up"
does NOT match anything here) - that would cross into the automatic-
inference the mission brief explicitly prohibits.
"""
import re
from typing import Optional
from app.skills.base import Skill, SkillMatch
from app.skills.registry import register_skill
from app.tools.base import ToolResult
from app.services.routine_service import RoutineService
from app.schemas.routine import RoutineCreate

_CREATE_WITH_STEPS_PATTERN = re.compile(
    r"\bcreate a routine(?: called| named)?\s+([^\.\!\?:]+?)\s+with steps?[:\s]+([^\.\!\?]+)",
    re.IGNORECASE,
)
_CREATE_NO_STEPS_PATTERN = re.compile(
    r"\bcreate a routine(?: called| named)?\s+([^\.\!\?:]+)$", re.IGNORECASE
)
_SHOW_ONE_PATTERN = re.compile(
    r"\bwhat'?s my ([a-z ]+?) routine\b|\bshow (?:me )?my ([a-z ]+?) routine\b", re.IGNORECASE
)
_LIST_ALL_PATTERN = re.compile(
    r"\b(?:list|show)(?: me)? my routines\b|\bwhat routines do i have\b", re.IGNORECASE
)


@register_skill
class RoutineSkill(Skill):
    name = "routine"
    description = "Lists routines and creates a new routine from an explicit 'create a routine called X with steps: ...' request."

    def match(self, message: str) -> Optional[SkillMatch]:
        if _LIST_ALL_PATTERN.search(message):
            return SkillMatch(kwargs={"action": "list"}, confidence=0.8)

        match = _SHOW_ONE_PATTERN.search(message)
        if match:
            name_fragment = (match.group(1) or match.group(2)).strip()
            return SkillMatch(kwargs={"action": "show", "name": name_fragment}, confidence=0.75)

        match = _CREATE_WITH_STEPS_PATTERN.search(message)
        if match:
            name = match.group(1).strip()
            steps = [s.strip() for s in re.split(r",|\band\b", match.group(2)) if s.strip()]
            return SkillMatch(kwargs={"action": "create", "name": name, "steps": steps}, confidence=0.85)

        match = _CREATE_NO_STEPS_PATTERN.search(message)
        if match:
            return SkillMatch(kwargs={"action": "create", "name": match.group(1).strip(), "steps": []}, confidence=0.7)

        return None

    async def run(self, action: str = "", name: str = "", steps=None, **kwargs) -> ToolResult:
        if self.db is None:
            return ToolResult(tool_name=self.name, success=False, output=None, error="No database session available.")

        service = RoutineService(self.db)

        if action == "list":
            routines = await service.list(is_active=True)
            if not routines:
                return ToolResult(tool_name=self.name, success=True, output="You have no routines set up yet.")
            lines = [f"- {r.name} ({len(r.steps)} step(s))" for r in routines]
            return ToolResult(tool_name=self.name, success=True, output="Your routines:\n" + "\n".join(lines))

        if action == "show":
            routine = await service.search_by_name_fragment(name)
            if not routine:
                return ToolResult(
                    tool_name=self.name, success=False, output=None,
                    error=f"No routine matching '{name}' was found.",
                )
            steps_text = "; ".join(routine.steps) if routine.steps else "(no steps recorded)"
            return ToolResult(tool_name=self.name, success=True, output=f"{routine.name}: {steps_text}")

        if action == "create":
            if not name.strip():
                return ToolResult(tool_name=self.name, success=False, output=None, error="No routine name recognized.")
            routine = await service.create(RoutineCreate(name=name.strip(), steps=steps or []))
            step_count = len(routine.steps)
            return ToolResult(
                tool_name=self.name, success=True,
                output=f"Created routine \"{routine.name}\" with {step_count} step(s).",
            )

        return ToolResult(tool_name=self.name, success=False, output=None, error=f"Unknown routine action '{action}'.")
