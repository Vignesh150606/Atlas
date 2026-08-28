import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_greeting_does_not_trigger_memory_retrieval(client: AsyncClient):
    response = await client.post("/api/v1/chat", json={"message": "Hello!"})
    assert response.status_code == 200
    data = response.json()
    assert "used retrieved memory context" not in data["response"]


@pytest.mark.asyncio
async def test_class_mention_then_question_uses_memory_and_tool(client: AsyncClient):
    first = await client.post("/api/v1/chat", json={"message": "I have a Math class at 9am on Mondays"})
    assert first.status_code == 200
    conversation_id = first.json()["conversation_id"]

    second = await client.post(
        "/api/v1/chat",
        json={"message": "When is my next class?", "conversation_id": conversation_id},
    )
    assert second.status_code == 200
    data = second.json()
    # Should have used both the timetable tool AND retrieved memory context.
    assert "used tool results" in data["response"]
    assert "used retrieved memory context" in data["response"]


@pytest.mark.asyncio
async def test_calculation_triggers_calculator_tool(client: AsyncClient):
    response = await client.post("/api/v1/chat", json={"message": "What is 15 + 27?"})
    assert response.status_code == 200
    assert "used tool results" in response.json()["response"]


@pytest.mark.asyncio
async def test_memory_extracted_gains_lifecycle_fields_after_retrieval(client: AsyncClient):
    first = await client.post("/api/v1/chat", json={"message": "My favorite food is sushi"})
    conversation_id = first.json()["conversation_id"]

    await client.post(
        "/api/v1/chat",
        json={"message": "What is my favorite food?", "conversation_id": conversation_id},
    )

    memories = (await client.get("/api/v1/memory")).json()
    sushi_memory = next(m for m in memories if "sushi" in m["content"].lower())
    assert sushi_memory["access_count"] >= 1
    assert sushi_memory["last_used"] is not None


@pytest.mark.asyncio
async def test_unrelated_second_message_does_not_falsely_report_tool_usage(client: AsyncClient):
    first = await client.post("/api/v1/chat", json={"message": "I have a Math class at 9am"})
    conversation_id = first.json()["conversation_id"]

    second = await client.post(
        "/api/v1/chat", json={"message": "Thanks!", "conversation_id": conversation_id}
    )
    assert "used tool results" not in second.json()["response"]


# --- Phase 9: conversation intelligence integration --------------------------
@pytest.mark.asyncio
async def test_incomplete_reminder_triggers_ambiguity_hint(client: AsyncClient):
    response = await client.post("/api/v1/chat", json={"message": "Remind me to"})
    assert response.status_code == 200
    assert "used conversation intelligence hints" in response.json()["response"]


@pytest.mark.asyncio
async def test_complete_reminder_does_not_trigger_ambiguity_hint(client: AsyncClient):
    response = await client.post(
        "/api/v1/chat", json={"message": "Remind me to submit the report by Friday"}
    )
    assert response.status_code == 200
    # The reminder skill's own confirmation still fires (tool results), but
    # there's nothing ambiguous about this one - no conversation intelligence
    # hint should be added on top of it.
    assert "used tool results" in response.json()["response"]


@pytest.mark.asyncio
async def test_follow_up_message_after_class_context_triggers_hint(client: AsyncClient):
    first = await client.post("/api/v1/chat", json={"message": "I have a Math class at 9am on Mondays"})
    conversation_id = first.json()["conversation_id"]

    second = await client.post(
        "/api/v1/chat",
        json={"message": "What about Tuesdays?", "conversation_id": conversation_id},
    )
    assert "used conversation intelligence hints" in second.json()["response"]
