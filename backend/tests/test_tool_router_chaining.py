import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.tools.router import ToolRouter
from app.planner.planner import PlannedToolCall


@pytest.mark.asyncio
async def test_dispatch_plan_results_match_dispatch_many(db_session: AsyncSession):
    """dispatch_plan's `.results` must be drop-in equivalent to what
    dispatch_many returns for a plain (no depends_on, no failure) plan -
    existing prompt-building code that consumes a ToolResult list keeps
    working unchanged if ever switched over."""
    router = ToolRouter(db_session)
    calls = [PlannedToolCall(tool="calculator", args={"expression": "3 + 4"})]
    report = await router.dispatch_plan(calls)
    many_results = await router.dispatch_many([{"tool": "calculator", "args": {"expression": "3 + 4"}}])
    assert report.results[0].output == many_results[0].output
    assert report.results[0].success == many_results[0].success


@pytest.mark.asyncio
async def test_dispatch_plan_reports_success_and_failure_counts(db_session: AsyncSession):
    router = ToolRouter(db_session)
    calls = [
        PlannedToolCall(tool="calculator", args={"expression": "2 + 2"}),
        PlannedToolCall(tool="calculator", args={"expression": "not an expression"}),
    ]
    report = await router.dispatch_plan(calls)
    assert report.success_count == 1
    assert report.failure_count == 1
    assert len(report.steps) == 2


@pytest.mark.asyncio
async def test_dispatch_plan_substitutes_depends_on_placeholder(db_session: AsyncSession):
    """A later call whose arg is exactly the placeholder
    "{{depends_on.output}}" gets that arg replaced with the referenced
    earlier call's output before dispatch."""
    router = ToolRouter(db_session)
    calls = [
        PlannedToolCall(tool="calculator", args={"expression": "10 + 5"}),
        PlannedToolCall(
            tool="calculator",
            args={"expression": "{{depends_on.output}} * 2"},
            depends_on="calculator",
        ),
    ]
    report = await router.dispatch_plan(calls)
    # First call: 10 + 5 = 15. Second call's expression should have been
    # substituted to "15 * 2" before dispatch (CalculatorTool stringifies
    # the numeric output into the expression).
    assert report.steps[0].output == 15
    assert report.steps[1].substituted_args is not None
    assert report.steps[1].success
    assert report.steps[1].output == 30


@pytest.mark.asyncio
async def test_dispatch_plan_no_substitution_when_no_placeholder_present(db_session: AsyncSession):
    """depends_on alone (without the literal placeholder in any arg) must
    not silently alter args - substitution only happens for an exact
    placeholder match."""
    router = ToolRouter(db_session)
    calls = [
        PlannedToolCall(tool="calculator", args={"expression": "1 + 1"}),
        PlannedToolCall(tool="calculator", args={"expression": "5 + 5"}, depends_on="calculator"),
    ]
    report = await router.dispatch_plan(calls)
    assert report.steps[1].substituted_args is None
    assert report.steps[1].output == 10


@pytest.mark.asyncio
async def test_dispatch_plan_falls_back_when_primary_tool_fails(db_session: AsyncSession):
    """summary -> knowledge fallback (see app/tools/router.py's
    _FALLBACK_FOR): when SummaryTool finds no matching document, the
    router also tries KnowledgeTool with the same query."""
    router = ToolRouter(db_session)
    calls = [PlannedToolCall(tool="summary", args={"query": "a topic with no matching document at all xyz123"})]
    report = await router.dispatch_plan(calls)

    assert report.steps[0].tool == "summary"
    assert report.steps[0].success is False
    assert len(report.steps) == 2
    assert report.steps[1].tool == "knowledge"
    assert report.steps[1].used_fallback is True


@pytest.mark.asyncio
async def test_dispatch_plan_no_fallback_fired_when_primary_succeeds(db_session: AsyncSession):
    router = ToolRouter(db_session)
    calls = [PlannedToolCall(tool="calculator", args={"expression": "1 + 1"})]
    report = await router.dispatch_plan(calls)
    assert len(report.steps) == 1  # calculator has no configured fallback anyway, and it succeeded
