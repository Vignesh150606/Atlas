from typing import List, Optional
import httpx
from app.providers.base import LLMProvider, ProviderMessage, ProviderError
from app.core.config import settings

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"


class ClaudeProvider(LLMProvider):
    """Anthropic Messages API provider.

    Docs: https://docs.claude.com/en/api/messages
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or settings.CLAUDE_API_KEY
        self.model = model or settings.CLAUDE_MODEL

    async def generate_response(
        self,
        messages: List[ProviderMessage],
        system_prompt: Optional[str] = None,
        **kwargs,
    ) -> str:
        if not self.api_key:
            raise ProviderError("CLAUDE_API_KEY is not configured.")

        payload = {
            "model": self.model,
            "max_tokens": kwargs.get("max_tokens", 1024),
            "messages": [{"role": m["role"], "content": m["content"]} for m in messages],
        }
        if system_prompt:
            payload["system"] = system_prompt

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "content-type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(ANTHROPIC_API_URL, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as e:
            raise ProviderError(f"Claude API error {e.response.status_code}: {e.response.text}") from e
        except httpx.HTTPError as e:
            raise ProviderError(f"Claude API request failed: {e}") from e

        try:
            text_blocks = [block["text"] for block in data["content"] if block.get("type") == "text"]
            return "".join(text_blocks)
        except (KeyError, TypeError) as e:
            raise ProviderError(f"Unexpected Claude API response shape: {data}") from e

    async def get_embedding(self, text: str) -> List[float]:
        raise ProviderError("ClaudeProvider does not support embeddings.")
