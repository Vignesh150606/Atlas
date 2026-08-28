from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class ToolResult:
    tool_name: str
    success: bool
    output: Any
    error: str = ""
    # Phase 8: set only by device-automation tools (see app/tools/device_tools.py).
    # The backend has no physical access to the user's phone, so a device tool
    # doesn't "execute" anything itself - it validates the request and produces
    # a directive describing what the Android app should do
    # ({"module": ..., "action": ..., "args": {...}}). ChatService lifts this
    # onto ChatResponse.device_action; every other tool leaves this as None and
    # is unaffected. Kept optional/additive so existing tools need no changes.
    device_action: Optional[Dict[str, Any]] = None
    # Phase 9: set by a tool (device or otherwise) when the action it
    # describes has a real-world or data-loss consequence the user should
    # explicitly confirm before it happens (e.g. dialing a number, replacing
    # clipboard contents) - see app/tools/device_tools.py for which actions
    # set this and why. Deliberately a field on ToolResult, not folded into
    # the `device_action` dict itself, so existing exact-dict-equality tests
    # against `device_action` (see tests/test_device_tools.py) are unaffected
    # by this addition. Default False: purely additive, every pre-existing
    # tool is unaffected. The backend cannot enforce confirmation by itself
    # (no UI) - this is a signal for the consuming client to act on.
    requires_confirmation: bool = False


class Tool(ABC):
    """Base interface for a callable ATLAS capability.

    Tools are deterministic, single-purpose, and do not call the LLM - they
    are dispatched *before* the provider call (by the Planner/ToolRouter) so
    their output can be folded into the prompt context. This is explicitly
    not an agent loop: there's no iterative tool-call-then-reconsider cycle,
    just a one-shot dispatch based on the Planner's execution plan.
    """

    name: str = "tool"
    description: str = ""

    @abstractmethod
    async def run(self, **kwargs: Any) -> ToolResult:
        raise NotImplementedError
