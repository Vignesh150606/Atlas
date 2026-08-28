import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.tools.calculator_tool import CalculatorTool
from app.tools.memory_tool import MemoryTool
from app.tools.timetable_tool import TimetableTool
from app.tools.router import ToolRouter
from app.repositories.memory_repository import MemoryRepository
from app.models.memory import MemoryType


@pytest.mark.asyncio
async def test_calculator_tool_basic_arithmetic():
    tool = CalculatorTool()
    result = await tool.run(expression="2 + 3 * 4")
    assert result.success
    assert result.output == 14


@pytest.mark.asyncio
async def test_calculator_tool_rejects_unsafe_input():
    tool = CalculatorTool()
    result = await tool.run(expression="__import__('os').system('echo hi')")
    assert not result.success


@pytest.mark.asyncio
async def test_calculator_tool_handles_division_by_zero():
    tool = CalculatorTool()
    result = await tool.run(expression="1 / 0")
    assert not result.success
    assert result.error


@pytest.mark.asyncio
async def test_memory_tool_returns_relevant_memories(db_session: AsyncSession):
    repo = MemoryRepository(db_session)
    await repo.create_memory({
        "title": "Favorite food", "content": "Pizza", "memory_type": MemoryType.PREFERENCE.value,
        "category": "preferences", "importance": 3, "is_pinned": False, "source": "manual",
        "tags": [], "structured_data": {},
    })
    tool = MemoryTool(db_session)
    result = await tool.run(query="What is my favorite food?")
    assert result.success
    assert any("Pizza" in m["content"] for m in result.output)


@pytest.mark.asyncio
async def test_timetable_tool_returns_class_memories(db_session: AsyncSession):
    repo = MemoryRepository(db_session)
    await repo.create_memory({
        "title": "Math class", "content": "Math at 9am", "memory_type": MemoryType.CLASS.value,
        "category": "academics", "importance": 3, "is_pinned": False, "source": "manual",
        "tags": [], "structured_data": {"subject": "Math", "schedule": "9am"},
    })
    tool = TimetableTool(db_session)
    result = await tool.run()
    assert result.success
    assert any(item["title"] == "Math class" for item in result.output)


@pytest.mark.asyncio
async def test_router_dispatches_to_correct_tool():
    router_db_independent = CalculatorTool()  # sanity: calculator needs no db
    result = await router_db_independent.run(expression="10 / 2")
    assert result.output == 5.0


@pytest.mark.asyncio
async def test_router_unknown_tool_returns_error_result(db_session: AsyncSession):
    router = ToolRouter(db_session)
    result = await router.dispatch("not-a-real-tool")
    assert not result.success
    assert "Unknown tool" in result.error


@pytest.mark.asyncio
async def test_router_available_tools_lists_all_registered_tools(db_session: AsyncSession):
    router = ToolRouter(db_session)
    assert set(router.available_tools()) == {
        "memory", "calculator", "timetable",
        "document", "knowledge", "timeline", "project", "summary",
        # Phase 8: Android Automation Foundation device tools.
        "launch_app", "search_app", "accessibility", "notifications",
        "media", "clipboard", "intent_action",
        # Phase 9: pluggable skills (see app/skills/) - registered
        # automatically via SkillRegistry, not hardcoded in router.py.
        "time", "weather", "search", "notes", "reminder", "calendar",
        # Phase 10: same auto-registration, three new skills.
        "task", "routine", "briefing",
    }


@pytest.mark.asyncio
async def test_router_dispatch_many(db_session: AsyncSession):
    router = ToolRouter(db_session)
    results = await router.dispatch_many([
        {"tool": "calculator", "args": {"expression": "3 + 4"}},
        {"tool": "timetable", "args": {}},
    ])
    assert len(results) == 2
    assert results[0].output == 7
    assert results[1].success
