"""Phase 9: NotesSkill.

Deliberately does NOT write a memory itself. MemoryExtractor's rule 4
(app/memory/memory_extractor.py) already recognizes this exact same
territory ("note:", "remember that ...") and ChatService already runs
MemoryExtractor over every message independently of tool routing (see
ChatService.process_message). If this skill also created a memory here,
the same user turn would have two separate, uncoordinated code paths both
trying to persist essentially the same content - a real duplicate-write
risk (only avoided by coincidence if ChatService's duplicate check happens
to see identical content first).

Instead, this skill's job is narrower and safe to run alongside the
extractor unconditionally: produce an explicit, user-visible confirmation
in the tool_results the LLM sees, so the model can say "Got it, noted"
with confidence instead of guessing whether the note was actually saved.
Persistence stays entirely MemoryExtractor's job, unchanged.
"""
import re
from typing import Optional
from app.skills.base import Skill, SkillMatch
from app.skills.registry import register_skill
from app.tools.base import ToolResult

# Mirrors MemoryExtractor rule 4's own trigger exactly (see
# app/memory/memory_extractor.py) plus a couple of additional phrasings
# ("make a note", "jot down", "take a note") that rule 4 doesn't itself
# gate on but IntentService already recognizes as memory-creation language
# (see app/intent/intent_service.py's explicit_memory_creation rule) -
# extractor rule 4's own condition (`note:` prefix OR `remember that`) is
# unaffected either way, so this only ever adds confirmation, never removes it.
_NOTE_PATTERN = re.compile(
    r"^note:|remember that\b|\bmake a note\b|\bjot down\b|\btake a note\b", re.IGNORECASE
)


@register_skill
class NotesSkill(Skill):
    name = "notes"
    description = "Confirms an explicit note/'remember that' request was captured (persistence stays with MemoryExtractor)."

    def match(self, message: str) -> Optional[SkillMatch]:
        if _NOTE_PATTERN.search(message):
            return SkillMatch(confidence=0.6)  # lower confidence: MemoryExtractor is the real source of truth
        return None

    async def run(self, **kwargs) -> ToolResult:
        return ToolResult(
            tool_name=self.name, success=True,
            output="Got it - I'll remember that.",
        )
