from typing import List, Optional
import httpx
from app.providers.base import LLMProvider, ProviderMessage, ProviderError
from app.core.config import settings

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


class GeminiProvider(LLMProvider):
    """Google Gemini (Generative Language API) provider."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.model = model or settings.GEMINI_MODEL

    async def generate_response(
        self,
        messages: List[ProviderMessage],
        system_prompt: Optional[str] = None,
        **kwargs,
    ) -> str:
        if not self.api_key:
            raise ProviderError("GEMINI_API_KEY is not configured.")

        # Gemini uses "model" instead of "assistant" as the role name.
        contents = [
            {
                "role": "model" if m["role"] == "assistant" else "user",
                "parts": [{"text": m["content"]}],
            }
            for m in messages
        ]

        payload: dict = {"contents": contents}
        if system_prompt:
            payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}

        url = f"{GEMINI_API_BASE}/{self.model}:generateContent"

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers={"Content-Type": "application/json", "x-goog-api-key": self.api_key},
                )
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as e:
            raise ProviderError(f"Gemini API error {e.response.status_code}: {e.response.text}") from e
        except httpx.HTTPError as e:
            raise ProviderError(f"Gemini API request failed: {e}") from e

        try:
            parts = data["candidates"][0]["content"]["parts"]
            return "".join(p.get("text", "") for p in parts)
        except (KeyError, IndexError, TypeError) as e:
            raise ProviderError(f"Unexpected Gemini API response shape: {data}") from e

    async def get_embedding(self, text: str) -> List[float]:
        raise ProviderError("GeminiProvider embeddings not implemented.")
