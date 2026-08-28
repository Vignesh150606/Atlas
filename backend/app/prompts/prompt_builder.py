from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional, TYPE_CHECKING
from app.models.memory import Memory
from app.providers.base import ProviderMessage

if TYPE_CHECKING:
    from app.planner.planner import ExecutionPlan
    from app.tools.base import ToolResult
    from app.models.document import Document

ATLAS_SYSTEM_PROMPT = (
    "You are ATLAS, a personal AI assistant. You have access to memories the "
    "user has previously shared or that were extracted from earlier "
    "conversations. Use them when they're relevant to the current question. "
    "If nothing relevant was retrieved, just answer normally - don't mention "
    "that memory retrieval happened."
)

ATLAS_DEVELOPER_PROMPT = (
    "Be concise and direct. Never fabricate a memory that wasn't provided to "
    "you below. If the user asks about something you have no memory of, say "
    "so plainly rather than guessing."
)


@dataclass
class PromptContext:
    """The fully-assembled, ready-to-send context for a provider call.

    Kept as a dataclass (not a formatted string) so callers - and tests -
    can inspect exactly what went into a generation without re-parsing text.
    """
    system_prompt: str
    messages: List[ProviderMessage] = field(default_factory=list)

    def memory_section_included(self) -> bool:
        return "Relevant memories" in self.system_prompt

    def documents_section_included(self) -> bool:
        return "Relevant imported documents" in self.system_prompt

    def tool_section_included(self) -> bool:
        return "Tool results" in self.system_prompt

    def conversation_hints_included(self) -> bool:
        return "Conversation intelligence notes" in self.system_prompt


class PromptBuilder:
    """Composes System Prompt + Developer Prompt + Date/Time + Provider +
    Planner Output + Tool Results + Retrieved Memory + User Profile +
    Conversation History + Current User Message into a PromptContext.

    Each piece stays a distinct, named section - nothing is spliced into the
    user's own message. All the Phase 5 additions (provider_name, plan,
    tool_results, user_profile_memories, now) are optional keyword args with
    safe defaults, so existing callers built against the Phase 3 signature
    keep working unchanged.
    """

    @staticmethod
    def _format_memories(memories: List[Memory]) -> str:
        if not memories:
            return ""
        lines = [f"- ({m.memory_type}) {m.title}: {m.content}" for m in memories]
        return "Relevant memories about the user:\n" + "\n".join(lines)

    @staticmethod
    def _format_documents(documents: List["Document"]) -> str:
        """Phase 6: imported documents relevant to this turn. Content is
        truncated per-document - documents can be far larger than a memory,
        and this is prompt context, not a document viewer."""
        if not documents:
            return ""
        lines = []
        for d in documents:
            snippet = (d.content or "")[:500].strip()
            lines.append(f"- ({d.file_type}) {d.title}: {snippet}")
        return "Relevant imported documents:\n" + "\n".join(lines)

    @staticmethod
    def _format_user_profile(profile_memories: List[Memory]) -> str:
        """ATLAS has no dedicated user-profile entity (single-user app, no
        onboarding flow) - this derives a lightweight profile summary from
        pinned memories instead of pretending a real profile system exists.
        """
        if not profile_memories:
            return ""
        lines = [f"- {m.content}" for m in profile_memories]
        return "What ATLAS knows about the user (pinned facts):\n" + "\n".join(lines)

    @staticmethod
    def _format_datetime(now: datetime) -> str:
        return f"Current date/time: {now.strftime('%A, %B %d, %Y %H:%M UTC')}"

    @staticmethod
    def _format_provider(provider_name: str) -> str:
        return f"Active provider: {provider_name}"

    @staticmethod
    def _format_plan(plan: "ExecutionPlan") -> str:
        # Deliberately terse - this is a routing hint for the LLM, not a
        # chain-of-thought transcript. The planner's own reasoning process
        # never gets narrated here.
        if not plan.needs_memory_retrieval and not plan.tool_calls:
            return ""
        return f"Context focus: {plan.notes}"

    @staticmethod
    def _format_tool_results(tool_results: List["ToolResult"]) -> str:
        if not tool_results:
            return ""
        lines = []
        for r in tool_results:
            if r.success:
                lines.append(f"- {r.tool_name}: {r.output}")
            else:
                lines.append(f"- {r.tool_name}: (failed - {r.error})")
        return "Tool results:\n" + "\n".join(lines)

    @staticmethod
    def _format_conversation_hints(hints: List[str]) -> str:
        """Phase 9: surfaces ConversationIntelligenceService's follow-up and
        ambiguity signals (see app/services/conversation_intelligence.py)
        as short, explicit instructions - distinct from the tool
        results/memory sections above, which are *data*; these are
        *guidance* about how to use it (e.g. "ask a clarifying question
        instead of guessing")."""
        if not hints:
            return ""
        return "Conversation intelligence notes:\n" + "\n".join(f"- {h}" for h in hints)

    @staticmethod
    def build(
        history: List[ProviderMessage],
        current_message: str,
        retrieved_memories: Optional[List[Memory]] = None,
        retrieved_documents: Optional[List["Document"]] = None,
        system_prompt: str = ATLAS_SYSTEM_PROMPT,
        developer_prompt: str = ATLAS_DEVELOPER_PROMPT,
        provider_name: Optional[str] = None,
        plan: Optional["ExecutionPlan"] = None,
        tool_results: Optional[List["ToolResult"]] = None,
        user_profile_memories: Optional[List[Memory]] = None,
        conversation_summary: Optional[str] = None,
        conversation_hints: Optional[List[str]] = None,
        now: Optional[datetime] = None,
    ) -> PromptContext:
        sections = [system_prompt, developer_prompt]

        now = now or datetime.now(timezone.utc)
        sections.append(PromptBuilder._format_datetime(now))

        if provider_name:
            sections.append(PromptBuilder._format_provider(provider_name))

        if conversation_summary:
            sections.append(conversation_summary)

        hints_section = PromptBuilder._format_conversation_hints(conversation_hints or [])
        if hints_section:
            sections.append(hints_section)

        if plan:
            plan_section = PromptBuilder._format_plan(plan)
            if plan_section:
                sections.append(plan_section)

        tool_section = PromptBuilder._format_tool_results(tool_results or [])
        if tool_section:
            sections.append(tool_section)

        memory_section = PromptBuilder._format_memories(retrieved_memories or [])
        if memory_section:
            sections.append(memory_section)

        documents_section = PromptBuilder._format_documents(retrieved_documents or [])
        if documents_section:
            sections.append(documents_section)

        profile_section = PromptBuilder._format_user_profile(user_profile_memories or [])
        if profile_section:
            sections.append(profile_section)

        merged_system_prompt = "\n\n".join(sections)

        messages: List[ProviderMessage] = list(history)
        messages.append({"role": "user", "content": current_message})

        return PromptContext(system_prompt=merged_system_prompt, messages=messages)
