"""Phase 9: skill registry.

The other half of "new skills without modifying the planner" (see
app/skills/base.py's docstring for the first half). Skills register
themselves here via `@register_skill` at import time; Planner and
ToolRouter each ask the registry for "everything that matches this
message" / "everything that exists", respectively - neither one needs to
know how many skills exist or what they're called.
"""
from typing import Any, Dict, List, Optional, Tuple, Type
from app.skills.base import Skill, SkillMatch

_REGISTRY: Dict[str, Type[Skill]] = {}


def register_skill(skill_cls: Type[Skill]) -> Type[Skill]:
    """Class decorator: `@register_skill` above a Skill subclass registers
    it by `.name`. Raises on a duplicate name at import time (a
    programming error - two skills should never claim the same tool name)
    rather than silently letting one shadow the other.
    """
    instance = skill_cls()
    if not instance.name or instance.name == "tool":
        raise ValueError(f"{skill_cls.__name__} must set a real `name`")
    if instance.name in _REGISTRY and _REGISTRY[instance.name] is not skill_cls:
        raise ValueError(
            f"Skill name '{instance.name}' is already registered to "
            f"{_REGISTRY[instance.name].__name__}; skill names must be unique."
        )
    _REGISTRY[instance.name] = skill_cls
    return skill_cls


class SkillRegistry:
    """Read-side of the registry - what Planner and ToolRouter actually use."""

    @staticmethod
    def all_skills() -> List[Skill]:
        """A fresh, db-less instance of every registered skill - for
        `match()` only (see Planner._build_skill_tool_calls). Never use
        these instances' `run()` - they have no db. Use
        `instantiate_all(db)` for that."""
        return [cls() for cls in _REGISTRY.values()]

    @staticmethod
    def instantiate_all(db: Any) -> Dict[str, Skill]:
        """Fresh, db-bound instances keyed by name - what ToolRouter
        registers into its dispatch table so `run()` can actually read/write
        memories for the skills that need to."""
        return {name: cls(db) for name, cls in _REGISTRY.items()}

    @staticmethod
    def names() -> List[str]:
        return list(_REGISTRY.keys())

    @staticmethod
    def match_all(message: str) -> List[Tuple[Skill, SkillMatch]]:
        """Every registered skill that claims this message, highest
        confidence first. Planner decides how many of these to actually
        turn into tool calls (see Planner._build_skill_tool_calls) -
        this method itself makes no judgment about which "wins".
        """
        matches: List[Tuple[Skill, SkillMatch]] = []
        for skill in SkillRegistry.all_skills():
            result = skill.match(message)
            if result is not None:
                matches.append((skill, result))
        matches.sort(key=lambda pair: pair[1].confidence, reverse=True)
        return matches

    @staticmethod
    def get(name: str) -> Optional[Skill]:
        skill_cls = _REGISTRY.get(name)
        return skill_cls() if skill_cls else None
