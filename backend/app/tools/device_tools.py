"""Phase 8: Android Automation Foundation - device-action tools.

These tools are structurally different from every other Tool in this
package. A CalculatorTool or MemoryTool fully executes on the backend and
returns a real result. A device tool *cannot* do that - the backend is a
Python process with no access to the user's phone. What it can do is:

  1. Validate/normalize the request (e.g. is `action` one of the actions
     this module actually supports).
  2. Produce a directive: {"module": ..., "action": ..., "args": {...}}
     describing exactly what the Android app should do.
  3. Return that directive as ToolResult.device_action, plus a short
     human-readable `output` string so it still folds sensibly into the
     prompt context the same way every other tool's output does.

ChatService lifts the first successful device_action found in a turn's
tool_results onto ChatResponse.device_action. The Android app executes it
locally (AccessibilityService / NotificationListener / MediaSession /
PackageManager / ClipboardManager / Intents - see
android/app/src/main/java/com/atlas/automation/) and reports the outcome
back via POST /api/v1/chat/device-result, which is how the result re-enters
memory (see app/api/v1/endpoints/chat.py::report_device_result).

Deliberately one directive per turn: this app has no iterative agent loop
(see app/tools/router.py's docstring) and a device action needs the user
mid-loop, not decided by a tree the backend replans on its own - so
"open WhatsApp, then tap Search, then type Alice" is three conversational
turns, not three actions dispatched from one message. See
docs/Phase8_KnownLimitations.md for the reasoning.
"""

from typing import Any, Dict, Optional
from app.tools.base import Tool, ToolResult


class DeviceTool(Tool):
    """Shared helper for building a directive-shaped ToolResult."""

    module: str = "device"

    def _directive(
        self, action: str, args: Dict[str, Any], summary: str, requires_confirmation: bool = False
    ) -> ToolResult:
        return ToolResult(
            tool_name=self.name,
            success=True,
            output=summary,
            device_action={"module": self.module, "action": action, "args": args},
            requires_confirmation=requires_confirmation,
        )

    def _invalid(self, message: str) -> ToolResult:
        return ToolResult(tool_name=self.name, success=False, output=None, error=message)


class LaunchAppTool(DeviceTool):
    """Launches an installed app by (fuzzy) name. Maps to the Application
    Manager module's launch_app capability on Android."""

    name = "launch_app"
    module = "app_manager"
    description = "Launches an installed app by name, e.g. 'open WhatsApp'."

    async def run(self, app_name: str = "", **kwargs: Any) -> ToolResult:
        app_name = app_name.strip()
        if not app_name:
            return self._invalid("No app name was given to launch.")
        return self._directive(
            action="launch_app",
            args={"query": app_name},
            summary=f"Preparing to launch '{app_name}' on the user's device.",
        )


class AppSearchTool(DeviceTool):
    """Searches installed apps by name fragment, without launching one."""

    name = "search_app"
    module = "app_manager"
    description = "Searches installed apps matching a name fragment."

    async def run(self, query: str = "", **kwargs: Any) -> ToolResult:
        query = query.strip()
        if not query:
            return self._invalid("No search query was given.")
        return self._directive(
            action="search_app",
            args={"query": query},
            summary=f"Searching installed apps matching '{query}'.",
        )


class AccessibilityActionTool(DeviceTool):
    """Generic UI-automation actions backed by the Accessibility Service:
    click, long_click, scroll, type_text, back, home, recents,
    open_notifications, read_screen. `target` is a best-effort text/content
    description used to locate a control for click/long_click/type_text;
    it is optional for the global actions (back/home/recents/
    open_notifications/read_screen)."""

    name = "accessibility"
    module = "accessibility"
    description = "Reads the screen or performs a click/scroll/type/global-navigation action via the Accessibility Service."

    _GLOBAL_ACTIONS = {"back", "home", "recents", "open_notifications", "read_screen"}
    _TARGETED_ACTIONS = {"click", "long_click", "scroll", "type_text"}
    _VALID_ACTIONS = _GLOBAL_ACTIONS | _TARGETED_ACTIONS

    async def run(
        self,
        action: str = "",
        target: Optional[str] = None,
        text: Optional[str] = None,
        direction: str = "down",
        **kwargs: Any,
    ) -> ToolResult:
        action = action.strip().lower()
        if action not in self._VALID_ACTIONS:
            return self._invalid(
                f"Unsupported accessibility action '{action}'. Valid actions: {sorted(self._VALID_ACTIONS)}"
            )
        if action in self._TARGETED_ACTIONS and action != "scroll" and not target:
            return self._invalid(f"Action '{action}' requires a target (the control to act on).")
        if action == "type_text" and not text:
            return self._invalid("Action 'type_text' requires text to type.")

        args: Dict[str, Any] = {}
        if target:
            args["target"] = target
        if action == "type_text":
            args["text"] = text
        if action == "scroll":
            args["direction"] = direction if direction in ("up", "down") else "down"

        summary = {
            "click": f"Tapping '{target}'.",
            "long_click": f"Long-pressing '{target}'.",
            "scroll": f"Scrolling {args.get('direction', 'down')}.",
            "type_text": f"Typing '{text}' into '{target}'.",
            "back": "Pressing back.",
            "home": "Going to the home screen.",
            "recents": "Opening recent apps.",
            "open_notifications": "Opening the notification shade.",
            "read_screen": "Reading the current screen contents.",
        }[action]
        return self._directive(action=action, args=args, summary=summary)


class NotificationTool(DeviceTool):
    """Observes/summarizes/groups notifications via the Notification
    Listener Service."""

    name = "notifications"
    module = "notifications"
    description = "Lists, summarizes, or groups the device's current notifications."

    _VALID_ACTIONS = {"list", "summarize", "group"}

    async def run(
        self, action: str = "summarize", app_filter: Optional[str] = None, **kwargs: Any
    ) -> ToolResult:
        action = (action or "summarize").strip().lower()
        if action not in self._VALID_ACTIONS:
            return self._invalid(f"Unsupported notification action '{action}'.")
        args: Dict[str, Any] = {}
        if app_filter:
            args["app_filter"] = app_filter
        summary = f"Checking the user's notifications ({action})."
        return self._directive(action=action, args=args, summary=summary)


class MediaControlTool(DeviceTool):
    """Controls the active media session (play/pause/next/previous/volume/
    now-playing) via the Media Session Controller."""

    name = "media"
    module = "media_session"
    description = "Controls media playback: play, pause, next, previous, volume, now_playing."

    _VALID_ACTIONS = {"play", "pause", "next", "previous", "volume_up", "volume_down", "now_playing"}

    async def run(self, action: str = "", **kwargs: Any) -> ToolResult:
        action = action.strip().lower()
        if action not in self._VALID_ACTIONS:
            return self._invalid(
                f"Unsupported media action '{action}'. Valid actions: {sorted(self._VALID_ACTIONS)}"
            )
        summary = {
            "play": "Resuming playback.",
            "pause": "Pausing playback.",
            "next": "Skipping to the next track.",
            "previous": "Going back to the previous track.",
            "volume_up": "Turning the volume up.",
            "volume_down": "Turning the volume down.",
            "now_playing": "Checking what's currently playing.",
        }[action]
        return self._directive(action=action, args={}, summary=summary)


class ClipboardTool(DeviceTool):
    """Reads or writes the device clipboard."""

    name = "clipboard"
    module = "clipboard"
    description = "Reads the current clipboard contents or writes new text to the clipboard."

    _VALID_ACTIONS = {"read", "write"}

    async def run(self, action: str = "read", text: Optional[str] = None, **kwargs: Any) -> ToolResult:
        action = (action or "read").strip().lower()
        if action not in self._VALID_ACTIONS:
            return self._invalid(f"Unsupported clipboard action '{action}'.")
        if action == "write" and not text:
            return self._invalid("Action 'write' requires text to copy.")

        args: Dict[str, Any] = {"text": text} if action == "write" else {}
        summary = f"Copying text to the clipboard." if action == "write" else "Reading the clipboard."
        # Phase 9 / Security: writing silently replaces whatever the user
        # currently has on their clipboard, which can be a real (if minor)
        # data-loss surprise - reading is non-destructive and needs no
        # confirmation.
        return self._directive(action=action, args=args, summary=summary, requires_confirmation=(action == "write"))


class IntentActionTool(DeviceTool):
    """Standard implicit-Intent actions: open a URL, dial a number, open
    contacts, share text, open maps, compose an email."""

    name = "intent_action"
    module = "intent"
    description = "Fires a standard Android intent: open_url, dial, contacts, share, maps, email."

    _VALID_ACTIONS = {"open_url", "dial", "contacts", "share", "maps", "email"}
    _REQUIRED_ARG = {
        "open_url": "url",
        "dial": "number",
        "share": "text",
        "maps": "query",
        "email": "to",
    }  # "contacts" needs no argument

    async def run(
        self,
        action: str = "",
        url: Optional[str] = None,
        number: Optional[str] = None,
        text: Optional[str] = None,
        query: Optional[str] = None,
        to: Optional[str] = None,
        subject: Optional[str] = None,
        body: Optional[str] = None,
        **kwargs: Any,
    ) -> ToolResult:
        action = action.strip().lower()
        if action not in self._VALID_ACTIONS:
            return self._invalid(
                f"Unsupported intent action '{action}'. Valid actions: {sorted(self._VALID_ACTIONS)}"
            )

        raw_args = {"url": url, "number": number, "text": text, "query": query, "to": to, "subject": subject, "body": body}
        required = self._REQUIRED_ARG.get(action)
        if required and not raw_args.get(required):
            return self._invalid(f"Action '{action}' requires '{required}'.")

        args = {k: v for k, v in raw_args.items() if v}
        summary = {
            "open_url": f"Opening {url}.",
            "dial": f"Dialing {number}.",
            "contacts": "Opening Contacts.",
            "share": "Opening the share sheet.",
            "maps": f"Opening Maps for '{query}'.",
            "email": f"Composing an email to {to}.",
        }[action]
        # Phase 9 / Security: "dial" still deliberately stops short of
        # ACTION_CALL (see docs/Phase8_KnownLimitations.md #5) but a misheard
        # transcription pre-filling the wrong number is still worth an
        # explicit confirmation cue before the dialer even opens; every other
        # intent here (opening a URL, contacts, maps, share, composing an
        # email) is non-destructive and reversible with no side effect until
        # the user takes a further action of their own.
        return self._directive(action=action, args=args, summary=summary, requires_confirmation=(action == "dial"))


# Every device-tool name, for ChatService to recognize which tool_results
# carry a device_action worth lifting onto ChatResponse (and for tests /
# documentation to enumerate the full Android Automation surface in one
# place without re-deriving it from ToolRouter's private dict).
DEVICE_TOOL_NAMES = {
    LaunchAppTool.name,
    AppSearchTool.name,
    AccessibilityActionTool.name,
    NotificationTool.name,
    MediaControlTool.name,
    ClipboardTool.name,
    IntentActionTool.name,
}
