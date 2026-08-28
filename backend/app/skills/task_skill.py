"""Phase 10: TaskSkill (mission brief section 3).

Unlike ReminderSkill, this is genuinely new territory - no pre-existing
write path this could duplicate (MemoryExtractor rule 3's "I have to X
by Y" / "Todo: X" is a passive Memory(TASK) record, not a
listable/completable Task - see app/models/task.py's docstring). So this
skill both matches *and* persists directly via TaskService, unconditionally
(no db-is-None confirmation-only fallback like ReminderSkill needs,
because there's no pre-existing chat-facing task capability its
confirmation could stand in for when db is unavailable - see the class
docstring below and its tests for the one small accommodation this still
needs for db-less unit testing of match() alone).

Four actions, one skill (kept together rather than as four skills since
they share the same trigger vocabulary and args shape - see `_ACTION_
PATTERNS`): create, complete, cancel, list. `complete`/`cancel` look the
task up by title text (the user was never shown an id) via
TaskService.find_incomplete_by_title - see that method's docstring for
the tie-break rule when a title fragment matches more than one task.
"""
import re
from typing import Optional
from app.skills.base import Skill, SkillMatch
from app.skills.registry import register_skill
from app.tools.base import ToolResult
from app.services.task_service import TaskService
from app.schemas.task import TaskCreate

_CREATE_PATTERNS = [
    re.compile(r"\b(?:create|add)(?: a)? task(?:\s*(?:to|for|:))\s*([^\.\!\?]+)", re.IGNORECASE),
    re.compile(r"\badd ([^\.\!\?]+?) (?:to|as) (?:my|the) task(?:s| list)\b", re.IGNORECASE),
]
_COMPLETE_PATTERNS = [
    re.compile(r"\b(?:complete|finish)(?: the)? task(?:\s*:)?\s*([^\.\!\?]+)", re.IGNORECASE),
    re.compile(r"\bmark task\s*([^\.\!\?]+?) as (?:done|complete|completed|finished)\b", re.IGNORECASE),
]
_CANCEL_PATTERNS = [
    re.compile(r"\bcancel(?: the)? task(?:\s*:)?\s*([^\.\!\?]+)", re.IGNORECASE),
]
_LIST_PATTERN = re.compile(
    r"\b(?:list|show)(?: me)? my tasks\b|\bwhat are my tasks\b|\bwhat'?s (?:on )?my task list\b",
    re.IGNORECASE,
)


def _first_match(patterns, message: str) -> Optional[str]:
    for pattern in patterns:
        match = pattern.search(message)
        if match:
            return match.group(1).strip()
    return None


@register_skill
class TaskSkill(Skill):
    name = "task"
    description = "Create, complete, cancel, and list personal tasks from chat."

    def match(self, message: str) -> Optional[SkillMatch]:
        if _LIST_PATTERN.search(message):
            return SkillMatch(kwargs={"action": "list"}, confidence=0.8)

        title = _first_match(_COMPLETE_PATTERNS, message)
        if title:
            return SkillMatch(kwargs={"action": "complete", "title": title}, confidence=0.85)

        title = _first_match(_CANCEL_PATTERNS, message)
        if title:
            return SkillMatch(kwargs={"action": "cancel", "title": title}, confidence=0.85)

        title = _first_match(_CREATE_PATTERNS, message)
        if title:
            return SkillMatch(kwargs={"action": "create", "title": title}, confidence=0.8)

        return None

    async def run(self, action: str = "", title: str = "", **kwargs) -> ToolResult:
        if self.db is None:
            # match() must work db-less (see app/skills/base.py); run()
            # in production always has a db (SkillRegistry.instantiate_all
            # via ToolRouter). Unit tests exercising match() directly
            # never call run() without also providing a db_session - see
            # tests/test_skills.py.
            return ToolResult(tool_name=self.name, success=False, output=None, error="No database session available.")

        service = TaskService(self.db)

        if action == "list":
            tasks = await service.list_incomplete(limit=20)
            if not tasks:
                return ToolResult(tool_name=self.name, success=True, output="You have no incomplete tasks.")
            lines = [f"- {t.title} ({t.priority})" for t in tasks]
            return ToolResult(
                tool_name=self.name, success=True,
                output=f"You have {len(tasks)} incomplete task(s):\n" + "\n".join(lines),
            )

        if action == "create":
            if not title.strip():
                return ToolResult(tool_name=self.name, success=False, output=None, error="No task title recognized.")
            task = await service.create(TaskCreate(title=title.strip()), source="chat")
            return ToolResult(tool_name=self.name, success=True, output=f"Task created: \"{task.title}\".")

        if action in ("complete", "cancel"):
            if not title.strip():
                return ToolResult(tool_name=self.name, success=False, output=None, error="No task title recognized.")
            existing = await service.find_incomplete_by_title(title.strip())
            if not existing:
                return ToolResult(
                    tool_name=self.name, success=False, output=None,
                    error=f"No incomplete task matching '{title.strip()}' was found.",
                )
            if action == "complete":
                await service.complete(existing.id)
                return ToolResult(tool_name=self.name, success=True, output=f"Marked task \"{existing.title}\" as complete.")
            await service.cancel(existing.id)
            return ToolResult(tool_name=self.name, success=True, output=f"Cancelled task \"{existing.title}\".")

        return ToolResult(tool_name=self.name, success=False, output=None, error=f"Unknown task action '{action}'.")
