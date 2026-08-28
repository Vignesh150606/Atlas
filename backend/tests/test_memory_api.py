import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_memory_api_endpoints(client: AsyncClient):
    # 1. Create
    payload = {
        "title": "Meeting Note",
        "content": "Discuss ATLAS Phase 2 architecture.",
        "memory_type": "note",
        "category": "work",
        "importance": 4,
        "tags": ["meeting", "atlas"]
    }
    create_res = await client.post("/api/v1/memory", json=payload)
    assert create_res.status_code == 201
    mem_data = create_res.json()
    mem_id = mem_data["id"]
    assert mem_data["title"] == "Meeting Note"

    # 2. Get by ID
    get_res = await client.get(f"/api/v1/memory/{mem_id}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == mem_id

    # 3. List
    list_res = await client.get("/api/v1/memory?memory_type=note")
    assert list_res.status_code == 200
    assert len(list_res.json()) >= 1

    # 4. Search
    search_res = await client.get("/api/v1/memory/search?q=ATLAS")
    assert search_res.status_code == 200
    assert len(search_res.json()) >= 1

    # 5. Patch
    patch_res = await client.patch(f"/api/v1/memory/{mem_id}", json={"importance": 5})
    assert patch_res.status_code == 200
    assert patch_res.json()["importance"] == 5

    # 6. Delete
    del_res = await client.delete(f"/api/v1/memory/{mem_id}")
    assert del_res.status_code == 200
    assert del_res.json()["deleted_at"] is not None
