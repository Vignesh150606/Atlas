from typing import Optional
from app.core.config import settings
from app.providers.base import LLMProvider
from app.providers.mock import MockProvider
from app.providers.openai import OpenAIProvider
from app.providers.claude import ClaudeProvider
from app.providers.gemini import GeminiProvider
from app.providers.ollama import OllamaProvider

_PROVIDER_REGISTRY = {
    "mock": MockProvider,
    "openai": OpenAIProvider,
    "claude": ClaudeProvider,
    "gemini": GeminiProvider,
    "ollama": OllamaProvider,
}


class ProviderFactory:
    """Builds an LLMProvider from a name. Switching the active provider is a
    pure configuration change (DEFAULT_LLM_PROVIDER env var, or ?provider=
    on the chat endpoint) - no code changes required.
    """

    @staticmethod
    def get_provider(provider_name: Optional[str] = None) -> LLMProvider:
        name = (provider_name or settings.DEFAULT_LLM_PROVIDER).lower()
        provider_cls = _PROVIDER_REGISTRY.get(name)
        if provider_cls is None:
            valid = ", ".join(sorted(_PROVIDER_REGISTRY))
            raise ValueError(f"Unknown LLM provider '{name}'. Valid options: {valid}")
        return provider_cls()

    @staticmethod
    def available_providers() -> list:
        return sorted(_PROVIDER_REGISTRY)


provider_factory = ProviderFactory()
