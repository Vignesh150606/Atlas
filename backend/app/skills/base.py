"""Phase 9: pluggable Skill system.

Before Phase 9, this module held a `BaseSkill` scaffold (sync
`execute(params) -> Dict`, function-calling-schema shaped) that nothing in
the codebase ever imported or implemented - dead code left over from early
planning (confirmed by grep: zero references anywhere else in app/). This
rewrite replaces it with a real, wired abstraction, rather than adding a
second, competing "skill" concept alongside the dead one.

The core architectural goal (from the Phase 9 brief): "the architecture
should allow new skills without modifying the planner." Concretely, that
means two things had to be true simultaneously:

1. A Skill must slot into the *existing*, already-tested Tool/ToolRouter
   pipeline with zero special-casing - so it's IS-A `Tool` (see
   app/tools/base.py), not a parallel type ToolRouter/ChatService would
   need new branching to understand. Same `ToolResult`, same `run()`
   contract, same dispatch path every other tool already goes through.

2. Each Skill must own its own trigger detection (`match()`), so
   Planner.build_plan needs exactly ONE generic hook added, ever - see
   `Planner._build_skill_tool_calls` in app/planner/planner.py. Every skill
   added after that hook exists (Time, Notes, Reminder, Calendar, Search,
   Weather - see the sibling files in this package) requires touching
   planner.py not at all. This is verified directly: none of those five
   skill files are imported by planner.py, only by
   app/skills/registry.py, which planner.py imports once.

Calculator, and the existing device-automation tools (launch_app, dial,
etc.), deliberately stay exactly as they were before Phase 9 - they already
had working, tested Planner routing, and retrofitting them onto this new
base for architectural purity alone would risk the 200+ tests already
covering that routing for no behavioral gain. New capability goes through
the new pluggable path; nothing pre-existing was disturbed to make that
true.
"""
from abc import abstractmethod
from typing import Any, Dict, Optional
from app.tools.base import Tool, ToolResult


class SkillMatch:
    """What a Skill's `match()` returns when it recognizes a message: the
    keyword arguments `run()` should be called with, plus a confidence the
    Planner can use if more than one skill matches the same message (higher
    confidence wins - see Planner._build_skill_tool_calls)."""

    __slots__ = ("kwargs", "confidence")

    def __init__(self, kwargs: Optional[Dict[str, Any]] = None, confidence: float = 0.7):
        self.kwargs = kwargs or {}
        self.confidence = confidence

    def __repr__(self) -> str:  # pragma: no cover - debugging aid only
        return f"SkillMatch(kwargs={self.kwargs!r}, confidence={self.confidence})"


class Skill(Tool):
    """Base class for a pluggable ATLAS skill.

    A Skill IS a Tool (inherits run()/ToolResult/device-directive helpers
    unchanged) that additionally knows, on its own, whether a given message
    is meant for it - via `match()`. That's the one new piece of surface
    area; everything downstream of `run()` already existed and is already
    tested by app/tests/test_tools.py and friends.

    `db` is optional and defaults to None: `match()` is called against a
    plain `cls()` instance (no db - see SkillRegistry.all_skills, used by
    the Planner, which itself never receives a db session) and must never
    touch it; `run()` is called against a db-bound instance (see
    SkillRegistry.instantiate_all, used by ToolRouter) for skills that
    actually need to read or write memories. Skills that need no db (Time,
    Weather) simply never reference `self.db`.

    To add a new skill:
        1. Subclass Skill, implement `name`, `match()`, and `run()`.
        2. Add `@register_skill` (see app/skills/registry.py).
        3. Import the new module from app/skills/__init__.py so the
           decorator actually runs and registers it.
    Planner and ToolRouter need no changes for steps 1-3 to work.
    """

    def __init__(self, db: Optional[Any] = None):
        self.db = db

    @abstractmethod
    def match(self, message: str) -> Optional[SkillMatch]:
        """Return a SkillMatch if this skill applies to `message`, else
        None. Must be a pure, fast, deterministic check (regex/keyword) -
        this runs against every message for every registered skill, so it
        should never do I/O or anything slow, and must work with `self.db`
        being None.
        """
        raise NotImplementedError

    async def run(self, **kwargs: Any) -> ToolResult:  # pragma: no cover - overridden by subclasses
        raise NotImplementedError
