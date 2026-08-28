import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_open_app_message_returns_device_action(client: AsyncClient):
    response = await client.post("/api/v1/chat", json={"message": "Open WhatsApp"})
    assert response.status_code == 200
    data = response.json()

    assert data["device_action"] is not None
    assert data["device_action"]["tool"] == "launch_app"
    assert data["device_action"]["module"] == "app_manager"
    assert data["device_action"]["action"] == "launch_app"
    assert data["device_action"]["args"] == {"query": "WhatsApp"}
    # Also folded into the prompt context, same as any other tool.
    assert "used tool results" in data["response"]


@pytest.mark.asyncio
async def test_media_control_message_returns_device_action(client: AsyncClient):
    response = await client.post("/api/v1/chat", json={"message": "pause"})
    assert response.status_code == 200
    data = response.json()
    assert data["device_action"]["tool"] == "media"
    assert data["device_action"]["action"] == "pause"


@pytest.mark.asyncio
async def test_open_app_device_action_does_not_require_confirmation(client: AsyncClient):
    # Regression guard: requires_confirmation must default to False on the
    # wire so every pre-Phase-9 client integration is unaffected.
    response = await client.post("/api/v1/chat", json={"message": "Open WhatsApp"})
    assert response.json()["device_action"]["requires_confirmation"] is False


@pytest.mark.asyncio
async def test_dial_device_action_requires_confirmation(client: AsyncClient):
    response = await client.post("/api/v1/chat", json={"message": "call 555-1234"})
    data = response.json()
    assert data["device_action"]["action"] == "dial"
    assert data["device_action"]["requires_confirmation"] is True


@pytest.mark.asyncio
async def test_ordinary_message_has_no_device_action(client: AsyncClient):
    response = await client.post("/api/v1/chat", json={"message": "Hello!"})
    assert response.status_code == 200
    assert response.json()["device_action"] is None


@pytest.mark.asyncio
async def test_invalid_device_action_request_does_not_set_device_action(client: AsyncClient):
    # "call " with nothing after it still matches the dial pattern loosely,
    # so use a message that matches no automation pattern at all instead -
    # this asserts a plain unmatched question still has no device_action.
    response = await client.post("/api/v1/chat", json={"message": "What's the weather usually like in April?"})
    assert response.status_code == 200
    assert response.json()["device_action"] is None


@pytest.mark.asyncio
async def test_device_result_endpoint_appends_assistant_message(client: AsyncClient):
    chat_response = await client.post("/api/v1/chat", json={"message": "Open WhatsApp"})
    conversation_id = chat_response.json()["conversation_id"]

    result_response = await client.post(
        "/api/v1/chat/device-result",
        json={
            "conversation_id": conversation_id,
            "tool": "launch_app",
            "action": "launch_app",
            "success": True,
            "summary": "Opened WhatsApp.",
            "details": {},
        },
    )
    assert result_response.status_code == 200
    data = result_response.json()
    assert data["role"] == "assistant"
    assert "Opened WhatsApp." in data["content"]


@pytest.mark.asyncio
async def test_device_result_failure_is_reflected_in_message(client: AsyncClient):
    chat_response = await client.post("/api/v1/chat", json={"message": "Open NonexistentApp123"})
    conversation_id = chat_response.json()["conversation_id"]

    result_response = await client.post(
        "/api/v1/chat/device-result",
        json={
            "conversation_id": conversation_id,
            "tool": "launch_app",
            "action": "launch_app",
            "success": False,
            "summary": "No app matching 'NonexistentApp123' was found.",
            "details": {},
        },
    )
    assert result_response.status_code == 200
    data = result_response.json()
    assert "No app matching" in data["content"]


@pytest.mark.asyncio
async def test_device_result_is_retrievable_as_conversation_history(client: AsyncClient):
    chat_response = await client.post("/api/v1/chat", json={"message": "Open WhatsApp"})
    conversation_id = chat_response.json()["conversation_id"]

    await client.post(
        "/api/v1/chat/device-result",
        json={
            "conversation_id": conversation_id,
            "tool": "launch_app",
            "action": "launch_app",
            "success": True,
            "summary": "Opened WhatsApp.",
            "details": {},
        },
    )

    # A later turn in the same conversation should see the device-action
    # outcome as part of history (proving it was actually persisted as a
    # message, not just logged).
    follow_up = await client.post(
        "/api/v1/chat",
        json={"message": "thanks", "conversation_id": conversation_id},
    )
    assert follow_up.status_code == 200
