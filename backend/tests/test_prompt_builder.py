import pytest
from app.prompts.prompt_builder import PromptBuilder, ATLAS_SYSTEM_PROMPT
from app.models.memory import Memory, MemoryType


def _make_memory(title="Math class", content="Math at 9am", memory_type=MemoryType.CLASS.value):
    m = Memory(title=title, content=content, memory_type=memory_type)
    return m


def test_build_with_no_history_or_memory():
    ctx = PromptBuilder.build(history=[], current_message="Hello")
    assert ctx.messages == [{"role": "user", "content": "Hello"}]
    assert ATLAS_SYSTEM_PROMPT in ctx.system_prompt
    assert not ctx.memory_section_included()


def test_build_appends_current_message_after_history():
    history = [
        {"role": "user", "content": "Hi"},
        {"role": "assistant", "content": "Hello!"},
    ]
    ctx = PromptBuilder.build(history=history, current_message="How are you?")
    assert ctx.messages[-1] == {"role": "user", "content": "How are you?"}
    assert ctx.messages[:2] == history


def test_build_includes_retrieved_memory_section():
    mem = _make_memory()
    ctx = PromptBuilder.build(history=[], current_message="When is my class?", retrieved_memories=[mem])
    assert ctx.memory_section_included()
    assert "Math class" in ctx.system_prompt
    assert "Math at 9am" in ctx.system_prompt


def test_build_omits_memory_section_when_none_retrieved():
    ctx = PromptBuilder.build(history=[], current_message="Hi", retrieved_memories=[])
    assert not ctx.memory_section_included()


def test_build_always_includes_current_datetime():
    from datetime import datetime, timezone
    fixed_now = datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc)
    ctx = PromptBuilder.build(history=[], current_message="Hi", now=fixed_now)
    assert "Current date/time" in ctx.system_prompt
    assert "2026" in ctx.system_prompt


def test_build_includes_provider_name_when_given():
    ctx = PromptBuilder.build(history=[], current_message="Hi", provider_name="claude")
    assert "Active provider: claude" in ctx.system_prompt


def test_build_omits_provider_section_when_not_given():
    ctx = PromptBuilder.build(history=[], current_message="Hi")
    assert "Active provider" not in ctx.system_prompt


def test_build_includes_tool_results():
    from app.tools.base import ToolResult
    results = [ToolResult(tool_name="calculator", success=True, output=42)]
    ctx = PromptBuilder.build(history=[], current_message="What is 6*7?", tool_results=results)
    assert ctx.tool_section_included()
    assert "42" in ctx.system_prompt


def test_build_includes_failed_tool_result_with_error():
    from app.tools.base import ToolResult
    results = [ToolResult(tool_name="calculator", success=False, output=None, error="bad expression")]
    ctx = PromptBuilder.build(history=[], current_message="What is x*7?", tool_results=results)
    assert "failed" in ctx.system_prompt
    assert "bad expression" in ctx.system_prompt


def test_build_includes_planner_notes_when_plan_needs_action():
    from app.planner.planner import ExecutionPlan
    from app.intent.intent_service import IntentResult, IntentType
    plan = ExecutionPlan(
        intent=IntentResult(IntentType.QUESTION, confidence=0.5),
        needs_memory_retrieval=True,
        notes="intent=question; needs memory retrieval",
    )
    ctx = PromptBuilder.build(history=[], current_message="What's my project?", plan=plan)
    assert "Context focus" in ctx.system_prompt


def test_build_includes_user_profile_section():
    profile_mem = _make_memory(title="Name", content="The user's name is Alex")
    ctx = PromptBuilder.build(history=[], current_message="Hi", user_profile_memories=[profile_mem])
    assert "What ATLAS knows about the user" in ctx.system_prompt
    assert "Alex" in ctx.system_prompt


# --- Phase 9: conversation intelligence hints -------------------------------
def test_build_includes_conversation_hints_section():
    ctx = PromptBuilder.build(
        history=[], current_message="What about Friday?",
        conversation_hints=["This message appears to follow up on the recent discussion of: math, class."],
    )
    assert ctx.conversation_hints_included()
    assert "math, class" in ctx.system_prompt


def test_build_omits_conversation_hints_section_when_empty():
    ctx = PromptBuilder.build(history=[], current_message="Hello")
    assert not ctx.conversation_hints_included()


def test_build_includes_multiple_conversation_hints():
    ctx = PromptBuilder.build(
        history=[], current_message="Remind me to",
        conversation_hints=["hint one", "hint two"],
    )
    assert "hint one" in ctx.system_prompt
    assert "hint two" in ctx.system_prompt
