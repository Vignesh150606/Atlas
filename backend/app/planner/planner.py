import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set, Tuple
from app.intent.intent_service import IntentType, IntentResult
from app.models.memory import MemoryType
from app.skills import SkillRegistry

# Which intents warrant retrieving memories into the prompt context at all.
# Deliberately excludes GENERAL_CHAT (greetings/thanks - no context needed)
# and COMMAND (routed to a tool directly rather than general retrieval).
_INTENTS_NEEDING_RETRIEVAL: Set[IntentType] = {
    IntentType.QUESTION,
    IntentType.INFORMATION_LOOKUP,
    IntentType.MEMORY_SEARCH,
    IntentType.MEMORY_UPDATE,
    IntentType.TASK,
    IntentType.PLANNING,
    IntentType.CONVERSATION,
}

_TIMETABLE_KEYWORDS = {"class", "timetable", "schedule", "lecture"}
_DOCUMENT_KEYWORDS = {"document", "documents", "file", "files", "pdf", "notes", "csv", "spreadsheet", "resume", "uploaded"}
_TIMELINE_KEYWORDS = {"timeline", "deadline", "deadlines", "due date", "what's due", "upcoming"}
_PROJECT_KEYWORDS = {"project", "projects"}
_SUMMARY_KEYWORDS = {"summarize", "summary of", "summary", "tl;dr", "tldr", "sum up"}

# --- Phase 8: Android Automation Foundation -------------------------------
# Deterministic keyword/regex routing to device tools, same philosophy as
# everything above: no LLM call, first matching rule wins, one directive per
# turn (see app/tools/device_tools.py for why it's one-per-turn). Checked in
# this order because several of these overlap on the word "open" - the more
# specific patterns (maps/contacts/url/notification-shade) must be tried
# before the generic app-launch fallback, or "open maps" would launch an app
# named "maps" instead of firing the maps intent.
#
# This is intentionally *not* exhaustive: fine-grained on-screen actions
# ("tap the blue Send button") need live screen content a keyword planner
# can't see, so accessibility click/long_click/type_text are only reachable
# today from an explicit follow-up once the app has read the screen for the
# LLM - not from a single freeform phrase. See docs/Phase8_KnownLimitations.md.
_MEDIA_PATTERNS: List[Tuple[str, re.Pattern]] = [
    ("play", re.compile(r"\b(play|resume)\b.*\b(music|song|playback|audio|track)\b|^(play|resume)$", re.IGNORECASE)),
    ("pause", re.compile(r"^pause$|\bpause\b.*\b(music|song|playback|audio|track)\b", re.IGNORECASE)),
    ("next", re.compile(r"\b(next|skip)\b.*\b(song|track)\b|^(next|skip)$", re.IGNORECASE)),
    ("previous", re.compile(r"\b(previous|last)\b.*\b(song|track)\b|\bgo back a (song|track)\b", re.IGNORECASE)),
    ("volume_up", re.compile(r"\bvolume up\b|\bturn.*volume up\b|\b(louder|increase the volume)\b", re.IGNORECASE)),
    ("volume_down", re.compile(r"\bvolume down\b|\bturn.*volume down\b|\b(quieter|lower the volume|decrease the volume)\b", re.IGNORECASE)),
    ("now_playing", re.compile(r"\bwhat'?s playing\b|\bwhat song is this\b|\bnow playing\b", re.IGNORECASE)),
]

_NOTIFICATION_PATTERN = re.compile(
    r"\b(check|read|show me|what are|any new|summarize|clear)\b.*\bnotifications?\b", re.IGNORECASE
)

_CLIPBOARD_WRITE_PATTERN = re.compile(r"\bcopy\s+(.+?)\s+to (the )?clipboard\b", re.IGNORECASE)
_CLIPBOARD_READ_PATTERN = re.compile(r"\bwhat'?s (on|in) my clipboard\b|\bread (the |my )?clipboard\b", re.IGNORECASE)

_DIAL_PATTERN = re.compile(r"\b(call|dial)\s+(.+)", re.IGNORECASE)
_MAPS_PATTERN = re.compile(r"\b(navigate to|directions to|open maps to|show me directions to)\s+(.+)", re.IGNORECASE)
_CONTACTS_PATTERN = re.compile(r"\bopen (my )?contacts\b", re.IGNORECASE)
_URL_PATTERN = re.compile(r"\bopen\s+(https?://\S+|www\.\S+|\S+\.(?:com|org|net|io|dev)(?:/\S*)?)", re.IGNORECASE)
_EMAIL_PATTERN = re.compile(r"\b(?:email|e-mail)\s+(.+)", re.IGNORECASE)

_BACK_PATTERN = re.compile(r"^(go back|press back|back button)$", re.IGNORECASE)
_HOME_PATTERN = re.compile(r"^(go home|go to the home screen|press home)$", re.IGNORECASE)
_RECENTS_PATTERN = re.compile(r"\b(recent apps|show recents|app switcher)\b", re.IGNORECASE)
_NOTIF_SHADE_PATTERN = re.compile(r"\bopen (the )?notification (shade|panel|drawer)\b", re.IGNORECASE)
_READ_SCREEN_PATTERN = re.compile(r"\bwhat'?s on (my )?screen\b|\bread (my |the )?screen\b|\bwhat does the screen say\b", re.IGNORECASE)

_APP_LAUNCH_PATTERN = re.compile(r"^(?:open|launch|start)\s+(.+)$", re.IGNORECASE)

# Phase 9: a message that's clearly a reminder-about-a-future-action
# ("remind me to call John tomorrow") must not be swallowed by the device
# dial/email/launch patterns above, which would otherwise fire on the
# embedded verb ("call") and treat it as "dial this number right now" - a
# real, latent bug that predates Phase 9 (device-call detection has always
# run first and returned early) but only became visible once ReminderSkill
# gave "remind me to ..." messages a genuine, testable alternate path (see
# app/skills/reminder_skill.py). Deliberately checked before any device
# pattern, not folded into one of them, since it should suppress *all* of
# them (call, email, open, navigate), not just dial.
_REMINDER_GUARD_PATTERN = re.compile(r"\bremind me to\b", re.IGNORECASE)


@dataclass
class PlannedToolCall:
    tool: str
    args: Dict
    # Phase 9: optional dependency-chaining hook (see ToolRouter.dispatch_plan
    # in app/tools/router.py). When set to another call's tool name, that
    # call is guaranteed to run first, and any string arg value equal to the
    # literal placeholder "{{depends_on.output}}" is substituted with the
    # referenced call's ToolResult.output before dispatch. Ready
    # infrastructure - see docs/Phase9_KnownLimitations.md for the current
    # honest status: no _build_* rule below emits this yet, exercised
    # directly by tests/test_tool_router_chaining.py instead.
    depends_on: Optional[str] = None


@dataclass
class ExecutionPlan:
    intent: IntentResult
    needs_memory_retrieval: bool
    needs_knowledge_retrieval: bool = False  # Phase 6: whether imported-document retrieval should run
    tool_calls: List[PlannedToolCall] = field(default_factory=list)
    target_memory_types: Optional[Set[str]] = None
    notes: str = ""  # short, human-readable explanation of the plan - for observability/logs only


class Planner:
    """Deterministic reasoning planner: decides *what information is needed*
    before the provider is called. Produces a structured ExecutionPlan, not
    a chain-of-thought narrative - the LLM never sees the planner's internal
    reasoning, only the results (retrieved memories, tool outputs) it gathers.

    Example: "When is my next class?" -> intent=QUESTION, needs timetable
    keyword detected -> plan calls the timetable tool and biases retrieval
    toward CLASS/TIMETABLE/EVENT memories, before the provider is ever called.
    """

    @staticmethod
    def _looks_like_calculation(message: str) -> bool:
        has_digit = any(c.isdigit() for c in message)
        has_operator = any(c in "+-*/%^" for c in message) or "calculate" in message.lower() or "compute" in message.lower()
        return has_digit and has_operator

    @staticmethod
    def _extract_expression(message: str) -> Optional[str]:
        """Pull just the arithmetic substring out of a natural-language
        message, e.g. "What is 15 + 27?" -> "15 + 27". CalculatorTool uses
        ast.parse in 'eval' mode, which can't handle surrounding words - it
        needs the bare expression, not the whole sentence.
        """
        candidates = re.findall(r"[\d][\d\s.\+\-\*/%()]*[\d)]|\d", message)
        if not candidates:
            return None
        return max(candidates, key=len).strip()

    @staticmethod
    def _wants_timetable(message: str) -> bool:
        lowered = message.lower()
        return any(kw in lowered for kw in _TIMETABLE_KEYWORDS)

    @staticmethod
    def _wants_documents(message: str) -> bool:
        lowered = message.lower()
        return any(kw in lowered for kw in _DOCUMENT_KEYWORDS)

    @staticmethod
    def _wants_timeline(message: str) -> bool:
        lowered = message.lower()
        return any(kw in lowered for kw in _TIMELINE_KEYWORDS)

    @staticmethod
    def _wants_project(message: str) -> bool:
        lowered = message.lower()
        return any(kw in lowered for kw in _PROJECT_KEYWORDS)

    @staticmethod
    def _wants_summary(message: str) -> bool:
        lowered = message.lower()
        return any(kw in lowered for kw in _SUMMARY_KEYWORDS)

    @staticmethod
    def _extract_after_keyword(message: str, keywords: Set[str]) -> Optional[str]:
        """Best-effort: text following the first matched keyword, used as a
        focused query (e.g. "summarize the onboarding doc" -> "the
        onboarding doc"). Falls back to the whole message when nothing
        follows the keyword, since a short "summarize this" still needs
        *some* query to search with."""
        lowered = message.lower()
        for kw in keywords:
            idx = lowered.find(kw)
            if idx != -1:
                after = message[idx + len(kw):].strip(" :\"'?.!")
                if after:
                    return after
        return None

    @classmethod
    def _build_device_tool_call(cls, message: str) -> Optional[PlannedToolCall]:
        """Returns at most one device-action tool call - see the module-level
        comment above for the ordering rationale. Returns None if nothing
        matched, same fallback philosophy as IntentService: don't guess."""
        text = message.strip()
        if not text:
            return None
        if _REMINDER_GUARD_PATTERN.search(text):
            return None

        # Notification-shade / contacts / maps / URL / email must all be
        # tried before the generic app-launch fallback (they share "open").
        if _NOTIF_SHADE_PATTERN.search(text):
            return PlannedToolCall(tool="accessibility", args={"action": "open_notifications"})
        if _CONTACTS_PATTERN.search(text):
            return PlannedToolCall(tool="intent_action", args={"action": "contacts"})
        match = _MAPS_PATTERN.search(text)
        if match:
            return PlannedToolCall(tool="intent_action", args={"action": "maps", "query": match.group(2).strip(" .!?")})
        match = _URL_PATTERN.search(text)
        if match:
            return PlannedToolCall(tool="intent_action", args={"action": "open_url", "url": match.group(1).strip(" .!?")})
        match = _EMAIL_PATTERN.search(text)
        if match:
            return PlannedToolCall(tool="intent_action", args={"action": "email", "to": match.group(1).strip(" .!?")})
        match = _DIAL_PATTERN.search(text)
        if match:
            return PlannedToolCall(tool="intent_action", args={"action": "dial", "number": match.group(2).strip(" .!?")})

        if _READ_SCREEN_PATTERN.search(text):
            return PlannedToolCall(tool="accessibility", args={"action": "read_screen"})
        if _BACK_PATTERN.match(text):
            return PlannedToolCall(tool="accessibility", args={"action": "back"})
        if _HOME_PATTERN.match(text):
            return PlannedToolCall(tool="accessibility", args={"action": "home"})
        if _RECENTS_PATTERN.search(text):
            return PlannedToolCall(tool="accessibility", args={"action": "recents"})

        for action, pattern in _MEDIA_PATTERNS:
            if pattern.search(text):
                return PlannedToolCall(tool="media", args={"action": action})

        if _NOTIFICATION_PATTERN.search(text):
            return PlannedToolCall(tool="notifications", args={"action": "summarize"})

        match = _CLIPBOARD_WRITE_PATTERN.search(text)
        if match:
            return PlannedToolCall(tool="clipboard", args={"action": "write", "text": match.group(1).strip()})
        if _CLIPBOARD_READ_PATTERN.search(text):
            return PlannedToolCall(tool="clipboard", args={"action": "read"})

        # Generic app launch - tried last since it's the broadest pattern.
        match = _APP_LAUNCH_PATTERN.match(text)
        if match:
            app_name = match.group(1).strip(" .!?")
            if app_name:
                return PlannedToolCall(tool="launch_app", args={"app_name": app_name})

        return None

    @classmethod
    def _build_skill_tool_calls(cls, message: str, client_timezone: Optional[str] = None) -> List[PlannedToolCall]:
        """Phase 9: the ONE generic hook for the entire pluggable skill
        system (see app/skills/base.py and app/skills/registry.py). Every
        skill owns its own trigger detection via `.match()`; this method
        just asks the registry which ones matched and turns each into a
        PlannedToolCall - it does not know or care how many skills exist.

        Adding a new skill (a new file in app/skills/, decorated with
        @register_skill, imported from app/skills/__init__.py) requires NO
        change here or anywhere else in this file - that's the whole point.
        Every match is included (not just the top one): this is what makes
        "remind me to call John and what time is it" a genuine two-call
        multi-step plan instead of an arbitrary pick between them.

        Phase 12 (ARCH-TZ): `client_timezone` is merged into every skill
        call's kwargs generically here - one addition, not per-skill - so
        ReminderSkill/CalendarSkill can resolve "tomorrow"/"8am" against
        the user's actual local time (see app/skills/reminder_skill.py and
        app/services/reminder_service.py). Every Skill.run() accepts
        **kwargs, so skills that don't care about it simply ignore it.
        """
        calls = []
        for skill, skill_match in SkillRegistry.match_all(message):
            args = dict(skill_match.kwargs)
            if client_timezone:
                args["timezone"] = client_timezone
            calls.append(PlannedToolCall(tool=skill.name, args=args))
        return calls

    @classmethod
    def build_plan(
        cls, message: str, intent_result: IntentResult, client_timezone: Optional[str] = None
    ) -> ExecutionPlan:
        tool_calls: List[PlannedToolCall] = []
        target_types: Optional[Set[str]] = None
        notes_parts: List[str] = [f"intent={intent_result.intent.value}"]
        wants_documents = cls._wants_documents(message)

        # --- Phase 8: Android Automation Foundation ---
        # Checked first and returns early-ish (still falls through to memory/
        # knowledge gating below): a device action is a standalone command,
        # so there's no case where it should also match e.g. the timetable
        # or document tools below.
        device_call = cls._build_device_tool_call(message)
        if device_call:
            tool_calls.append(device_call)
            notes_parts.append(f"device action: {device_call.tool}")
            return ExecutionPlan(
                intent=intent_result,
                needs_memory_retrieval=False,
                needs_knowledge_retrieval=False,
                tool_calls=tool_calls,
                target_memory_types=None,
                notes="; ".join(notes_parts),
            )

        if cls._wants_timetable(message):
            tool_calls.append(PlannedToolCall(tool="timetable", args={}))
            target_types = {MemoryType.CLASS.value, MemoryType.TIMETABLE.value, MemoryType.EVENT.value}
            notes_parts.append("needs timetable")

        if cls._looks_like_calculation(message):
            expression = cls._extract_expression(message)
            if expression:
                tool_calls.append(PlannedToolCall(tool="calculator", args={"expression": expression}))
                notes_parts.append("needs calculation")

        # --- Phase 9: pluggable skills (computed early so the generic
        # document-keyword fallback below can defer to a more specific
        # skill match rather than firing redundantly alongside it) ---
        skill_calls = cls._build_skill_tool_calls(message, client_timezone=client_timezone)
        skill_tool_names = {c.tool for c in skill_calls}

        # --- Phase 6: Personal Knowledge System routing ---
        if cls._wants_summary(message):
            topic = cls._extract_after_keyword(message, _SUMMARY_KEYWORDS) or message
            tool_calls.append(PlannedToolCall(tool="summary", args={"query": topic}))
            notes_parts.append("needs summary")
        elif cls._wants_timeline(message):
            tool_calls.append(PlannedToolCall(tool="timeline", args={}))
            notes_parts.append("needs timeline")
        elif cls._wants_project(message):
            project_query = cls._extract_after_keyword(message, _PROJECT_KEYWORDS) or message
            tool_calls.append(PlannedToolCall(tool="project", args={"query": project_query}))
            notes_parts.append("needs project lookup")
        elif wants_documents and "search" not in skill_tool_names:
            # SearchSkill (a deliberate "search for X" / "look up X" ask -
            # see app/skills/search_skill.py) already covers documents too,
            # so when it matches, firing this generic document-keyword
            # fallback as well would just be a second, cruder search over
            # the same data for no benefit.
            tool_calls.append(PlannedToolCall(tool="knowledge", args={"query": message}))
            notes_parts.append("needs document/knowledge search")

        if skill_calls:
            tool_calls.extend(skill_calls)
            notes_parts.append(f"skills matched: {', '.join(c.tool for c in skill_calls)}")

        needs_memory = intent_result.intent in _INTENTS_NEEDING_RETRIEVAL or bool(target_types)
        if needs_memory:
            notes_parts.append("needs memory retrieval")
        else:
            notes_parts.append("no retrieval needed")

        needs_knowledge = intent_result.intent in _INTENTS_NEEDING_RETRIEVAL or wants_documents
        if needs_knowledge:
            notes_parts.append("needs knowledge retrieval")

        return ExecutionPlan(
            intent=intent_result,
            needs_memory_retrieval=needs_memory,
            needs_knowledge_retrieval=needs_knowledge,
            tool_calls=tool_calls,
            target_memory_types=target_types,
            notes="; ".join(notes_parts),
        )
