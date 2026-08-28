import pytest
from app.planner.planner import Planner
from app.intent.intent_service import IntentService
from app.models.memory import MemoryType


def _plan_for(message: str):
    intent_result = IntentService.classify(message)
    return Planner.build_plan(message, intent_result)


def test_class_question_plans_timetable_tool():
    plan = _plan_for("When is my next class?")
    tool_names = [c.tool for c in plan.tool_calls]
    assert "timetable" in tool_names
    assert plan.needs_memory_retrieval
    assert MemoryType.CLASS.value in plan.target_memory_types


def test_calculation_plans_calculator_tool():
    plan = _plan_for("What is 12 * 7?")
    tool_names = [c.tool for c in plan.tool_calls]
    assert "calculator" in tool_names
    calc_call = next(c for c in plan.tool_calls if c.tool == "calculator")
    # Must be the bare expression, not the whole sentence - CalculatorTool's
    # ast.parse(mode="eval") can't handle "What is ... ?" wrapped around it.
    assert calc_call.args["expression"] == "12 * 7"


def test_greeting_does_not_need_retrieval():
    plan = _plan_for("Hello there!")
    assert not plan.needs_memory_retrieval
    assert plan.tool_calls == []


def test_general_question_needs_retrieval_without_specific_tool():
    plan = _plan_for("What is the capital of France?")
    assert plan.needs_memory_retrieval
    assert plan.tool_calls == []  # no timetable/calculator keywords - pure retrieval


def test_plan_notes_are_populated_for_observability():
    plan = _plan_for("Remind me to submit the report")
    assert plan.notes
    assert "intent=" in plan.notes


def test_plan_carries_intent_result():
    plan = _plan_for("Do you remember my project?")
    assert plan.intent.intent.value == "memory_search"


def test_expression_extraction_handles_various_phrasings():
    from app.planner.planner import Planner
    assert Planner._extract_expression("What is 15 + 27?") == "15 + 27"
    assert Planner._extract_expression("Calculate 100 / 4 for me") == "100 / 4"
    assert Planner._extract_expression("2+2") == "2+2"
    assert Planner._extract_expression("No numbers here") is None
