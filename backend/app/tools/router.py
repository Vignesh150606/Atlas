from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, TYPE_CHECKING
from sqlalchemy.ext.asyncio import AsyncSession
from app.tools.base import Tool, ToolResult
from app.tools.memory_tool import MemoryTool
from app.tools.calculator_tool import CalculatorTool
from app.tools.timetable_tool import TimetableTool
from app.tools.document_tool import DocumentTool
from app.tools.knowledge_tool import KnowledgeTool
from app.tools.timeline_tool import TimelineTool
from app.tools.project_tool import ProjectTool
from app.tools.summary_tool import SummaryTool
from app.tools.device_tools import (
    LaunchAppTool,
    AppSearchTool,
    AccessibilityActionTool,
    NotificationTool,
    MediaControlTool,
    ClipboardTool,
    IntentActionTool,
)
from app.skills import SkillRegistry

if TYPE_CHECKING:  # avoids a runtime import cycle risk - router is imported
    # very early (by ChatService alongside Planner); this keeps the type
    # hint on dispatch_plan accurate for IDEs/mypy without adding a real
    # module-load-time dependency on app.planner.
    from app.planner.planner import PlannedToolCall

# Phase 9: opt-in fallback routing - if the primary tool's ToolResult comes
# back success=False, the router also tries the mapped fallback tool with
# the *same args* dict-filtered to what the fallback actually accepts being
# irrelevant here (fallback tools below all accept **kwargs passthrough via
# `query`, matching the primary's own signature) and both results are kept
# in the ExecutionReport. Only used by `dispatch_plan`, never
# `dispatch_many` - every existing caller of dispatch_many keeps its exact
# original behavior.
#
# "summary" -> "knowledge": SummaryTool (app/tools/summary_tool.py) needs a
# document it can point extractive_summary() at; when its own keyword/query
# lookup finds nothing, a broader KnowledgeTool document search is a
# genuinely more helpful fallback than just reporting failure - "I couldn't
# summarize anything specific, but here's what I did find" beats silence.
_FALLBACK_FOR: Dict[str, str] = {
    "summary": "knowledge",
}


@dataclass
class ExecutionStep:
    tool: str
    success: bool
    output: Any
    error: str = ""
    requires_confirmation: bool = False
    used_fallback: bool = False  # True if this step's tool was substituted in after the primary failed
    substituted_args: Optional[Dict[str, Any]] = None  # non-None if depends_on substitution changed this call's args


@dataclass
class ExecutionReport:
    """Phase 9: structured record of one Planner-produced plan's execution -
    what Tool Router "execution reports" (Phase 9 brief) means concretely.
    `results` (plain ToolResult list) stays exactly what dispatch_many
    already returned, so ChatService's existing prompt-building code needs
    no changes; `steps` is the added structure for anything that wants more
    than the raw ToolResult list (e.g. richer logs, a future debug view).
    """
    steps: List[ExecutionStep] = field(default_factory=list)
    results: List[ToolResult] = field(default_factory=list)

    @property
    def success_count(self) -> int:
        return sum(1 for s in self.steps if s.success)

    @property
    def failure_count(self) -> int:
        return sum(1 for s in self.steps if not s.success)


class ToolRouter:
    """Dispatches to registered tools by name. Every future ATLAS capability
    that needs bespoke Planner routing (device automation, deep data-layer
    tools like KnowledgeTool) registers here directly as a Tool subclass;
    this is the single place that knows the full set of available tools.
    Simpler capabilities that only need "does this message apply to me" +
    "do the thing" should be a Skill instead (see app/skills/) - those
    self-register via SkillRegistry and are pulled in automatically below,
    without this file changing.

    This is a one-shot dispatcher, not an agent loop: the Planner decides
    up front which tools to call and with what arguments, the router calls
    them once each, and their outputs feed into prompt construction. There
    is no iterative re-planning based on tool output in this phase.
    """

    def __init__(self, db: AsyncSession):
        self._tools: Dict[str, Tool] = {
            "memory": MemoryTool(db),
            "calculator": CalculatorTool(),
            "timetable": TimetableTool(db),
            "document": DocumentTool(db),
            "knowledge": KnowledgeTool(db),
            "timeline": TimelineTool(db),
            "project": ProjectTool(db),
            "summary": SummaryTool(db),
            # Phase 8: Android Automation Foundation - device-action tools.
            # These don't touch the db (they can't reach the phone either);
            # see app/tools/device_tools.py for why they take a db-less ctor.
            "launch_app": LaunchAppTool(),
            "search_app": AppSearchTool(),
            "accessibility": AccessibilityActionTool(),
            "notifications": NotificationTool(),
            "media": MediaControlTool(),
            "clipboard": ClipboardTool(),
            "intent_action": IntentActionTool(),
        }
        # Phase 9: every registered Skill (see app/skills/) is dispatchable
        # exactly like any other tool - same dict, same dispatch/dispatch_many
        # path below, zero special-casing. New skills appear here
        # automatically the moment they're registered; this line doesn't
        # change when a new skill is added.
        self._tools.update(SkillRegistry.instantiate_all(db))

    def available_tools(self) -> List[str]:
        return sorted(self._tools)

    async def dispatch(self, tool_name: str, **kwargs) -> ToolResult:
        tool = self._tools.get(tool_name)
        if tool is None:
            return ToolResult(
                tool_name=tool_name,
                success=False,
                output=None,
                error=f"Unknown tool '{tool_name}'. Available: {', '.join(self.available_tools())}",
            )
        return await tool.run(**kwargs)

    async def dispatch_many(self, calls: List[Dict]) -> List[ToolResult]:
        """calls: [{"tool": "memory", "args": {"query": "..."}}, ...]
        Unchanged since Phase 1 - no chaining, no fallback, no dependency
        substitution. Every existing caller (ChatService, 200+ tests) can
        keep using this exactly as before; `dispatch_plan` below is the new,
        additive entry point for anything that wants those Phase 9
        behaviors.
        """
        results = []
        for call in calls:
            tool_name = call.get("tool")
            args = call.get("args", {})
            results.append(await self.dispatch(tool_name, **args))
        return results

    async def dispatch_plan(self, plan_calls: List["PlannedToolCall"]) -> ExecutionReport:
        """Phase 9: the chained/fallback/reporting-aware sibling of
        `dispatch_many`. Takes Planner PlannedToolCall objects directly
        (not plain dicts) so it can see `depends_on`.

        Three behaviors on top of dispatch_many, all additive:
        1. Dependency substitution: if a call's `depends_on` names an
           earlier call's tool, any string arg *containing* the literal
           placeholder "{{depends_on.output}}" has that placeholder text
           replaced with str(that earlier call's ToolResult.output) before
           dispatch - e.g. expression="{{depends_on.output}} * 2" becomes
           "15 * 2" if the depended-on call's output was 15. Calls are
           otherwise executed in list order - this is still a single
           deterministic pass, not a re-planning loop (see ToolRouter's
           class docstring): substitution only ever uses a result that was
           already computed earlier in the *same* list, so there's no
           cycle risk (a call cannot depend on a call after it).
        2. Fallback: if a call fails and its tool has an entry in
           `_FALLBACK_FOR`, the fallback tool is also tried (same args) and
           both results are recorded.
        3. The whole thing is captured as an ExecutionReport - `.results`
           is exactly what `dispatch_many` would have returned (drop-in
           compatible with existing prompt-building code), `.steps` is the
           added structure.
        """
        report = ExecutionReport()
        completed_by_tool: Dict[str, ToolResult] = {}

        for call in plan_calls:
            args = dict(call.args)
            substituted = None
            if call.depends_on and call.depends_on in completed_by_tool:
                dep_output = completed_by_tool[call.depends_on].output
                placeholder = "{{depends_on.output}}"
                replaced_keys = [
                    k for k, v in args.items() if isinstance(v, str) and placeholder in v
                ]
                if replaced_keys:
                    for key in replaced_keys:
                        args[key] = args[key].replace(placeholder, str(dep_output))
                    substituted = dict(args)

            result = await self.dispatch(call.tool, **args)
            completed_by_tool[call.tool] = result
            report.results.append(result)
            report.steps.append(ExecutionStep(
                tool=call.tool, success=result.success, output=result.output,
                error=result.error, requires_confirmation=result.requires_confirmation,
                substituted_args=substituted,
            ))

            if not result.success and call.tool in _FALLBACK_FOR:
                fallback_tool = _FALLBACK_FOR[call.tool]
                fallback_result = await self.dispatch(fallback_tool, **args)
                completed_by_tool[fallback_tool] = fallback_result
                report.results.append(fallback_result)
                report.steps.append(ExecutionStep(
                    tool=fallback_tool, success=fallback_result.success, output=fallback_result.output,
                    error=fallback_result.error, requires_confirmation=fallback_result.requires_confirmation,
                    used_fallback=True,
                ))

        return report
