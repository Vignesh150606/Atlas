"""Phase 9: TimeSkill - answers "what time is it" / "what's today's date"
style questions directly and deterministically, rather than leaving the LLM
to guess (a model has no reliable notion of "now" on its own).
"""
import re
from datetime import datetime
from typing import Optional
from app.skills.base import Skill, SkillMatch
from app.skills.registry import register_skill
from app.tools.base import ToolResult

_TIME_PATTERN = re.compile(
    r"\bwhat(?:'s| is) the time\b|\bwhat time is it\b|\bcurrent time\b|"
    r"\bwhat(?:'s| is) today'?s date\b|\bwhat day is it\b|\bwhat'?s the date\b|"
    r"\bwhat is the date\b|\btoday'?s date\b",
    re.IGNORECASE,
)
_DATE_ONLY_PATTERN = re.compile(r"\bdate\b|\bday is it\b", re.IGNORECASE)


@register_skill
class TimeSkill(Skill):
    name = "time"
    description = "Answers 'what time is it' / 'what's today's date' style questions using server time."

    def match(self, message: str) -> Optional[SkillMatch]:
        if _TIME_PATTERN.search(message):
            return SkillMatch(kwargs={"message": message}, confidence=0.9)
        return None

    async def run(self, message: str = "", **kwargs) -> ToolResult:
        now = datetime.now()
        # Honesty note: this is the backend server's local clock, not
        # necessarily the user's device timezone - the chat request schema
        # doesn't currently carry a client timezone, so we say so plainly
        # rather than implying certainty we don't have. A future phase
        # could add a `client_timezone` field to ChatRequest and thread it
        # through here.
        if _DATE_ONLY_PATTERN.search(message) and "time" not in message.lower():
            summary = f"Today is {now.strftime('%A, %B %d, %Y')} (server date)."
        else:
            summary = f"It's {now.strftime('%A, %B %d, %Y')} at {now.strftime('%I:%M %p')} (server time)."
        return ToolResult(tool_name=self.name, success=True, output=summary)
