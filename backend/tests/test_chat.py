import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_chat_endpoint(client: AsyncClient):
    payload = {"message": "Hello"}
    response = await client.post("/api/v1/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["response"] == "ATLAS received: Hello"
    assert "conversation_id" in data
    assert data["conversation_id"] > 0
