import pytest
from app.providers.mock import MockProvider
from app.providers.factory import ProviderFactory

@pytest.mark.asyncio
async def test_mock_provider():
    provider = MockProvider()
    response = await provider.generate_response([{"role": "user", "content": "Test prompt"}])
    assert response == "ATLAS received: Test prompt"

@pytest.mark.asyncio
async def test_mock_provider_notes_memory_context():
    provider = MockProvider()
    response = await provider.generate_response(
        [{"role": "user", "content": "When is my class?"}],
        system_prompt="You are ATLAS.\n\nRelevant memories about the user:\n- (class) Math: Math at 9am",
    )
    assert "[used retrieved memory context]" in response

def test_provider_factory():
    provider = ProviderFactory.get_provider("mock")
    assert isinstance(provider, MockProvider)

def test_provider_factory_unknown_provider_raises():
    with pytest.raises(ValueError):
        ProviderFactory.get_provider("not-a-real-provider")

def test_provider_factory_available_providers():
    available = ProviderFactory.available_providers()
    assert set(available) == {"mock", "openai", "claude", "gemini", "ollama"}
