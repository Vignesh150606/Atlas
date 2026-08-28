import pytest
from datetime import datetime, timedelta
from app.utils.time import utc_now
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_and_get_reminder(client: AsyncClient):
    due = (utc_now() + timedelta(days=1)).isoformat()
    response = await client.post("/api/v1/reminders", json={"title": "Submit report", "due_at": due})
    assert response.status_code == 201
    reminder_id = response.json()["id"]

    get_response = await client.get(f"/api/v1/reminders/{reminder_id}")
    assert get_response.status_code == 200
    assert get_response.json()["title"] == "Submit report"


@pytest.mark.asyncio
async def test_create_reminder_from_text(client: AsyncClient):
    response = await client.post(
        "/api/v1/reminders/from-text", json={"text": "remind me to call the dentist tomorrow"}
    )
    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "call the dentist"
    assert body["due_at"] is not None


@pytest.mark.asyncio
async def test_create_reminder_from_text_rejects_unrelated_text(client: AsyncClient):
    response = await client.post("/api/v1/reminders/from-text", json={"text": "what's the weather"})
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_complete_and_cancel_reminder(client: AsyncClient):
    create = await client.post("/api/v1/reminders", json={"title": "One-off task"})
    reminder_id = create.json()["id"]

    complete = await client.post(f"/api/v1/reminders/{reminder_id}/complete")
    assert complete.status_code == 200
    assert complete.json()["status"] == "completed"


@pytest.mark.asyncio
async def test_reminder_not_found_returns_404(client: AsyncClient):
    response = await client.get("/api/v1/reminders/does-not-exist")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_and_complete_task(client: AsyncClient):
    create = await client.post("/api/v1/tasks", json={"title": "Finish essay"})
    assert create.status_code == 201
    task_id = create.json()["id"]

    complete = await client.post(f"/api/v1/tasks/{task_id}/complete")
    assert complete.status_code == 200
    assert complete.json()["status"] == "completed"


@pytest.mark.asyncio
async def test_prioritize_task(client: AsyncClient):
    create = await client.post("/api/v1/tasks", json={"title": "Important thing"})
    task_id = create.json()["id"]
    response = await client.post(f"/api/v1/tasks/{task_id}/prioritize", json={"priority": "high"})
    assert response.status_code == 200
    assert response.json()["priority"] == "high"


@pytest.mark.asyncio
async def test_list_tasks_filters_by_status(client: AsyncClient):
    create = await client.post("/api/v1/tasks", json={"title": "Pending item"})
    task_id = create.json()["id"]
    await client.post(f"/api/v1/tasks/{task_id}/complete")

    pending = await client.get("/api/v1/tasks", params={"status": "pending"})
    completed = await client.get("/api/v1/tasks", params={"status": "completed"})
    assert task_id not in [t["id"] for t in pending.json()]
    assert task_id in [t["id"] for t in completed.json()]


@pytest.mark.asyncio
async def test_create_and_list_routines(client: AsyncClient):
    create = await client.post(
        "/api/v1/routines", json={"name": "Morning Routine", "steps": ["Drink water", "Stretch"]}
    )
    assert create.status_code == 201
    routines = await client.get("/api/v1/routines")
    assert any(r["name"] == "Morning Routine" for r in routines.json())


@pytest.mark.asyncio
async def test_update_and_delete_routine(client: AsyncClient):
    create = await client.post("/api/v1/routines", json={"name": "Study Routine"})
    routine_id = create.json()["id"]

    update = await client.patch(f"/api/v1/routines/{routine_id}", json={"is_active": False})
    assert update.status_code == 200
    assert update.json()["is_active"] is False

    delete = await client.delete(f"/api/v1/routines/{routine_id}")
    assert delete.status_code == 200
    get_after = await client.get(f"/api/v1/routines/{routine_id}")
    assert get_after.status_code == 404


@pytest.mark.asyncio
async def test_daily_briefing_endpoint_returns_structured_sections(client: AsyncClient):
    await client.post("/api/v1/tasks", json={"title": "Something to do"})
    response = await client.get("/api/v1/briefing/daily")
    assert response.status_code == 200
    body = response.json()
    assert "narrative" in body
    assert any(t["title"] == "Something to do" for t in body["incomplete_tasks"])


@pytest.mark.asyncio
async def test_proactive_suggestions_endpoint(client: AsyncClient):
    due = (utc_now() - timedelta(hours=1)).isoformat()
    await client.post("/api/v1/reminders", json={"title": "Overdue thing", "due_at": due})
    response = await client.get("/api/v1/briefing/suggestions")
    assert response.status_code == 200
    types = {s["suggestion_type"] for s in response.json()["suggestions"]}
    assert "overdue_reminder" in types
