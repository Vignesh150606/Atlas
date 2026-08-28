from typing import List, Optional
from app.providers.base import LLMProvider, ProviderMessage


class MockProvider(LLMProvider):
    """Deterministic provider for local dev and tests - no network calls.

    Echoes back the last user message along with a short note about what
    context it was given, so it's actually useful for verifying that the
    retrieval layer and prompt builder are wiring things through correctly
    (as opposed to just returning a static string).
    """

    async def generate_response(
        self,
        messages: List[ProviderMessage],
        system_prompt: Optional[str] = None,
        **kwargs,
    ) -> str:
        last_user = next(
            (m["content"] for m in reversed(messages) if m["role"] == "user"),
            "",
        )
        context_notes = []
        if system_prompt and "Relevant memories" in system_prompt:
            context_notes.append("used retrieved memory context")
        if system_prompt and "Tool results" in system_prompt:
            context_notes.append("used tool results")
        if system_prompt and "Conversation intelligence notes" in system_prompt:
            context_notes.append("used conversation intelligence hints")
        context_note = f" [{'; '.join(context_notes)}]" if context_notes else ""
        return f"ATLAS received: {last_user}{context_note}"

    async def get_embedding(self, text: str) -> List[float]:
        return [0.0] * 1536
