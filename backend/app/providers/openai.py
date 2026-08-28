from typing import List, Optional
import httpx
from app.providers.base import LLMProvider, ProviderMessage, ProviderError
from app.core.config import settings

OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
OPENAI_EMBEDDINGS_URL = "https://api.openai.com/v1/embeddings"


class OpenAIProvider(LLMProvider):
    """OpenAI Chat Completions API provider."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or settings.OPENAI_API_KEY
        self.model = model or settings.OPENAI_MODEL

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def generate_response(
        self,
        messages: List[ProviderMessage],
        system_prompt: Optional[str] = None,
        **kwargs,
    ) -> str:
        if not self.api_key:
            raise ProviderError("OPENAI_API_KEY is not configured.")

        chat_messages = []
        if system_prompt:
            chat_messages.append({"role": "system", "content": system_prompt})
        chat_messages.extend({"role": m["role"], "content": m["content"]} for m in messages)

        payload = {
            "model": self.model,
            "messages": chat_messages,
            "max_tokens": kwargs.get("max_tokens", 1024),
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(OPENAI_API_URL, json=payload, headers=self._headers())
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as e:
            raise ProviderError(f"OpenAI API error {e.response.status_code}: {e.response.text}") from e
        except httpx.HTTPError as e:
            raise ProviderError(f"OpenAI API request failed: {e}") from e

        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as e:
            raise ProviderError(f"Unexpected OpenAI API response shape: {data}") from e

    async def get_embedding(self, text: str) -> List[float]:
        if not self.api_key:
            raise ProviderError("OPENAI_API_KEY is not configured.")

        payload = {"model": "text-embedding-3-small", "input": text}
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(OPENAI_EMBEDDINGS_URL, json=payload, headers=self._headers())
                response.raise_for_status()
                data = response.json()
            return data["data"][0]["embedding"]
        except httpx.HTTPError as e:
            raise ProviderError(f"OpenAI embeddings request failed: {e}") from e
        except (KeyError, IndexError, TypeError) as e:
            raise ProviderError(f"Unexpected OpenAI embeddings response shape: {data}") from e
