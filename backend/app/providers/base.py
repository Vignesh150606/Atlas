from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, TypedDict


class ProviderMessage(TypedDict):
    """A single turn in a conversation, in the shape every provider adapts internally.

    role is one of "user" / "assistant". System-level instructions are passed
    separately via `system_prompt` rather than embedded in this list, since
    that's how the major provider APIs (Anthropic, OpenAI, Gemini) actually
    model it - keeping it structured here avoids collapsing everything into
    one giant string.
    """
    role: str
    content: str


class ProviderError(Exception):
    """Raised when a provider fails to produce a response (network error,
    non-2xx response, malformed response body, etc). Callers should catch
    this specifically rather than a bare Exception.
    """
    pass


class LLMProvider(ABC):
    """Base interface every LLM provider must implement.

    Providers are intentionally "dumb": they take an already-assembled
    system prompt + message list (built by PromptBuilder) and return text.
    They do not know about memories, conversations, or retrieval - that
    separation is what makes providers swappable via configuration alone.
    """

    @abstractmethod
    async def generate_response(
        self,
        messages: List[ProviderMessage],
        system_prompt: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        """Generate a response from the LLM given structured conversation turns.

        Args:
            messages: ordered list of {"role": "user"|"assistant", "content": str}.
                The last entry is expected to be the current user turn.
            system_prompt: fully composed system-level instructions (persona,
                developer instructions, retrieved memory context). Optional
                because some providers (or the Mock provider) may not need it.
        Raises:
            ProviderError: on any failure to obtain a response.
        """
        raise NotImplementedError

    @abstractmethod
    async def get_embedding(self, text: str) -> List[float]:
        """Generate an embedding for the given text.

        Not currently called anywhere in the app - ATLAS uses structured,
        rule-based retrieval rather than vector search (see Roadmap.md).
        Kept on the interface as a placeholder so providers that do support
        embeddings don't need an interface change when vector search lands.
        """
        raise NotImplementedError

    @property
    def name(self) -> str:
        """Human-readable provider name, used in logs and API responses."""
        return self.__class__.__name__.replace("Provider", "").lower()
