from typing import List, Optional
import httpx
from app.providers.base import LLMProvider, ProviderMessage, ProviderError
from app.core.config import settings


class OllamaProvider(LLMProvider):
    """Local Ollama provider - no API key required, runs against a local
    or self-hosted Ollama server.
    """

    def __init__(self, base_url: Optional[str] = None, model: Optional[str] = None):
        self.base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self.model = model or settings.OLLAMA_MODEL

    async def generate_response(
        self,
        messages: List[ProviderMessage],
        system_prompt: Optional[str] = None,
        **kwargs,
    ) -> str:
        chat_messages = []
        if system_prompt:
            chat_messages.append({"role": "system", "content": system_prompt})
        chat_messages.extend({"role": m["role"], "content": m["content"]} for m in messages)

        payload = {"model": self.model, "messages": chat_messages, "stream": False}

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(f"{self.base_url}/api/chat", json=payload)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as e:
            raise ProviderError(f"Ollama error {e.response.status_code}: {e.response.text}") from e
        except httpx.HTTPError as e:
            raise ProviderError(
                f"Could not reach Ollama at {self.base_url}: {e}. Is `ollama serve` running?"
            ) from e

        try:
            return data["message"]["content"]
        except (KeyError, TypeError) as e:
            raise ProviderError(f"Unexpected Ollama response shape: {data}") from e

    async def get_embedding(self, text: str) -> List[float]:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/api/embeddings",
                    json={"model": self.model, "prompt": text},
                )
                response.raise_for_status()
                data = response.json()
            return data["embedding"]
        except httpx.HTTPError as e:
            raise ProviderError(f"Ollama embeddings request failed: {e}") from e
