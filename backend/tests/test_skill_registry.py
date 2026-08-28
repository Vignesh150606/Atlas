import pytest
from app.skills import SkillRegistry
from app.skills.base import Skill, SkillMatch
from app.skills.registry import register_skill


def test_all_built_in_skills_are_registered():
    names = set(SkillRegistry.names())
    assert names == {
        "time", "weather", "search", "notes", "reminder", "calendar",
        # Phase 10: Personal Assistant & Proactive Intelligence
        "task", "routine", "briefing",
    }


def test_match_all_returns_empty_for_unrelated_message():
    assert SkillRegistry.match_all("What is the capital of France?") == []


def test_match_all_sorted_by_confidence_descending():
    # "Remember that I have to submit the report" matches both NotesSkill
    # (confidence 0.6) and, since it doesn't contain "remind me to", not
    # ReminderSkill - use a message that genuinely double-matches instead.
    matches = SkillRegistry.match_all("Remind me to submit the report by Friday")
    assert len(matches) >= 1
    confidences = [m.confidence for _, m in matches]
    assert confidences == sorted(confidences, reverse=True)


def test_get_returns_none_for_unknown_skill():
    assert SkillRegistry.get("not_a_real_skill") is None


def test_get_returns_instance_for_known_skill():
    skill = SkillRegistry.get("time")
    assert skill is not None
    assert skill.name == "time"


def test_instantiate_all_returns_db_bound_instances():
    sentinel = object()
    instances = SkillRegistry.instantiate_all(sentinel)
    assert set(instances.keys()) == set(SkillRegistry.names())
    assert instances["search"].db is sentinel


def test_all_skills_returns_db_less_instances_for_matching():
    for skill in SkillRegistry.all_skills():
        assert skill.db is None


def test_register_skill_rejects_duplicate_name():
    from app.skills.registry import _REGISTRY  # test-only: needed to clean up after this test

    @register_skill
    class _FirstDummySkill(Skill):
        name = "dummy_test_skill_9"

        def match(self, message):
            return None

        async def run(self, **kwargs):
            raise NotImplementedError

    try:
        with pytest.raises(ValueError):
            @register_skill
            class _SecondDummySkill(Skill):
                name = "dummy_test_skill_9"

                def match(self, message):
                    return None

                async def run(self, **kwargs):
                    raise NotImplementedError
    finally:
        # The global registry is process-wide state (see registry.py's
        # module docstring) - ToolRouter reads it fresh on every
        # instantiation, so a dummy name left behind here would leak into
        # every other test in the same pytest session (e.g.
        # test_router_available_tools_lists_all_registered_tools's exact-set
        # assertion). Must be removed, not just left for GC.
        _REGISTRY.pop("dummy_test_skill_9", None)


def test_register_skill_rejects_missing_name():
    with pytest.raises(ValueError):
        @register_skill
        class _NoNameSkill(Skill):
            def match(self, message):
                return None

            async def run(self, **kwargs):
                raise NotImplementedError
