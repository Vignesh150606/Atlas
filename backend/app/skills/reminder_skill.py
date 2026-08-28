"""Phase 9/10: ReminderSkill.

"Remind me to X" is a real gap ATLAS didn't originally handle at all (see
app/memory/memory_extractor.py's rule 5 docstring for the pre-Phase-9
history): IntentService correctly classified it as IntentType.TASK but
nothing acted on it - no tool call, no persisted memory, no follow-through.

Phase 9 closed the "no follow-through" gap with a confirmation-only
skill (MemoryExtractor's rule 5 handled the only actual persistence, a
generic Memory row). Phase 10 (mission brief section 2: "Implement a
real reminder architecture") adds the missing piece: when this skill runs
with a real db session (i.e. dispatched through ToolRouter in normal
chat use - see SkillRegistry.instantiate_all), it now ALSO creates an
actual, schedulable `Reminder` row via `ReminderService` - not a
duplicate of what MemoryExtractor rule 5 does. MemoryExtractor rule 5 is
deliberately left completely unchanged and still runs independently on
every message (a passive "the user said this" record); this skill's new
write is a different resource for a different purpose (an active,
completable, listable, briefing/proactive-suggestion-eligible object) -
see app/models/reminder.py's docstring for the full reasoning on why
this is not the duplicate-write problem the Phase 9 confirmation-only
pattern (see app/skills/notes_skill.py) was designed to avoid.

Backward-compatible by construction, not by special-casing: `self.db` is
already documented (app/skills/base.py) as optionally None (`match()` is
always called db-less; unit tests may also call `run()` db-less directly
- see tests/test_skills.py). When db is None, this skill falls back to
exactly its Phase 9 confirmation-only behavior. Every Phase 9 test for
this skill keeps passing unchanged; new tests (also in test_skills.py)
cover the db-bound persistence path directly.
"""
import re
from typing import Optional
from app.skills.base import Skill, SkillMatch
from app.skills.registry import register_skill
from app.tools.base import ToolResult
from app.memory.memory_extractor import MemoryExtractor
from app.services.reminder_service import ReminderService

_REMINDER_PATTERN = re.compile(r"\bremind me to\b", re.IGNORECASE)


@register_skill
class ReminderSkill(Skill):
    name = "reminder"
    description = "Confirms and (when a db session is available) persists a real, schedulable Reminder from a 'remind me to ...' request."

    def match(self, message: str) -> Optional[SkillMatch]:
        if not _REMINDER_PATTERN.search(message):
            return None
        parsed = MemoryExtractor.parse_reminder(message)
        if not parsed:
            return None
        return SkillMatch(kwargs={"task": parsed["task"], "due_date": parsed["due_date"]}, confidence=0.85)

    async def run(
        self, task: str = "", due_date: Optional[str] = None, conversation_id: Optional[str] = None, **kwargs
    ) -> ToolResult:
        if not task:
            return ToolResult(tool_name=self.name, success=False, output=None, error="No task text recognized.")

        due_at = None
        if self.db is not None:
            # Phase 10: real persistence. Re-derives the same "remind me
            # to <task> [at/by/on <when>]" split via create_from_text
            # (which itself calls MemoryExtractor.parse_reminder again) -
            # a second call to the same pure regex, not a second
            # implementation of it, so this can never disagree with the
            # `task`/`due_date` this method was matched with.
            full_text = f"remind me to {task}" + (f" by {due_date}" if due_date else "")
            reminder = await ReminderService(self.db).create_from_text(
                full_text, conversation_id=conversation_id
            )
            if reminder is not None:
                due_at = reminder.due_at

        summary = f"Got it - I'll remember that you need to {task}"
        if due_at:
            summary += f", due {due_at.strftime('%A, %b %d at %I:%M %p').replace(' 0', ' ')}."
        elif due_date:
            summary += f", due {due_date}."
        else:
            summary += "."
        return ToolResult(tool_name=self.name, success=True, output=summary)
