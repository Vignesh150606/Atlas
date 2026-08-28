import json
import pytest
import httpx
from app.providers.claude import ClaudeProvider
from app.providers.openai import OpenAIProvider
from app.providers.gemini import GeminiProvider
from app.providers.ollama import OllamaProvider
from app.providers.base import ProviderError


def _patch_client(monkeypatch, target_module: str, handler):
    """Monkeypatch httpx.AsyncClient used inside a provider module with one
    wired to a MockTransport, so no real network call is made.
    """

    class _PatchedAsyncClient(httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = httpx.MockTransport(handler)
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(f"{target_module}.httpx.AsyncClient", _PatchedAsyncClient)


@pytest.mark.asyncio
async def test_claude_provider_generate_response(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://api.anthropic.com/v1/messages"
        assert request.headers["x-api-key"] == "test-key"
        assert request.headers["anthropic-version"] == "2023-06-01"
        body = json.loads(request.content)
        assert body["messages"][-1]["content"] == "Hi"
        assert body["system"] == "sys"
        return httpx.Response(200, json={"content": [{"type": "text", "text": "Hello there"}]})

    _patch_client(monkeypatch, "app.providers.claude", handler)
    provider = ClaudeProvider(api_key="test-key", model="claude-sonnet-5")
    result = await provider.generate_response([{"role": "user", "content": "Hi"}], system_prompt="sys")
    assert result == "Hello there"


@pytest.mark.asyncio
async def test_claude_provider_missing_key_raises():
    provider = ClaudeProvider(api_key=None, model="claude-sonnet-5")
    with pytest.raises(ProviderError):
        await provider.generate_response([{"role": "user", "content": "Hi"}])


@pytest.mark.asyncio
async def test_claude_provider_http_error_raises_provider_error(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "unauthorized"})

    _patch_client(monkeypatch, "app.providers.claude", handler)
    provider = ClaudeProvider(api_key="bad-key")
    with pytest.raises(ProviderError):
        await provider.generate_response([{"role": "user", "content": "Hi"}])


@pytest.mark.asyncio
async def test_openai_provider_generate_response(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://api.openai.com/v1/chat/completions"
        assert request.headers["Authorization"] == "Bearer test-key"
        body = json.loads(request.content)
        assert body["messages"][0] == {"role": "system", "content": "sys"}
        assert body["messages"][-1] == {"role": "user", "content": "Hi"}
        return httpx.Response(
            200, json={"choices": [{"message": {"role": "assistant", "content": "Hello"}}]}
        )

    _patch_client(monkeypatch, "app.providers.openai", handler)
    provider = OpenAIProvider(api_key="test-key", model="gpt-4o-mini")
    result = await provider.generate_response([{"role": "user", "content": "Hi"}], system_prompt="sys")
    assert result == "Hello"


@pytest.mark.asyncio
async def test_gemini_provider_generate_response(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert "generateContent" in str(request.url)
        assert request.headers["x-goog-api-key"] == "test-key"
        body = json.loads(request.content)
        assert body["contents"][-1]["role"] == "user"
        return httpx.Response(
            200,
            json={"candidates": [{"content": {"parts": [{"text": "Hi from Gemini"}]}}]},
        )

    _patch_client(monkeypatch, "app.providers.gemini", handler)
    provider = GeminiProvider(api_key="test-key", model="gemini-2.0-flash")
    result = await provider.generate_response([{"role": "user", "content": "Hi"}])
    assert result == "Hi from Gemini"


@pytest.mark.asyncio
async def test_ollama_provider_generate_response(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "http://localhost:11434/api/chat"
        body = json.loads(request.content)
        assert body["model"] == "llama3.1"
        assert body["stream"] is False
        return httpx.Response(200, json={"message": {"role": "assistant", "content": "Hi from Ollama"}})

    _patch_client(monkeypatch, "app.providers.ollama", handler)
    provider = OllamaProvider(base_url="http://localhost:11434", model="llama3.1")
    result = await provider.generate_response([{"role": "user", "content": "Hi"}])
    assert result == "Hi from Ollama"


@pytest.mark.asyncio
async def test_ollama_provider_connection_error_raises_friendly_message(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    _patch_client(monkeypatch, "app.providers.ollama", handler)
    provider = OllamaProvider(base_url="http://localhost:11434", model="llama3.1")
    with pytest.raises(ProviderError, match="ollama serve"):
        await provider.generate_response([{"role": "user", "content": "Hi"}])
