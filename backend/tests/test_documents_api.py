import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_document_upload_list_get_delete(client: AsyncClient):
    files = {"file": ("notes.txt", b"Notes about the Atlas project and Python skills.", "text/plain")}
    data = {"title": "My Notes", "tags": "school,atlas"}

    upload_res = await client.post("/api/v1/documents", files=files, data=data)
    assert upload_res.status_code == 201
    doc = upload_res.json()
    doc_id = doc["id"]
    assert doc["title"] == "My Notes"
    assert doc["file_type"] == "txt"
    assert doc["tags"] == ["school", "atlas"]

    get_res = await client.get(f"/api/v1/documents/{doc_id}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == doc_id

    list_res = await client.get("/api/v1/documents")
    assert list_res.status_code == 200
    assert any(d["id"] == doc_id for d in list_res.json())

    search_res = await client.get("/api/v1/documents/search?q=Atlas")
    assert search_res.status_code == 200
    assert any(d["id"] == doc_id for d in search_res.json())

    entities_res = await client.get(f"/api/v1/documents/{doc_id}/entities")
    assert entities_res.status_code == 200
    assert any(e["name"] == "Python" for e in entities_res.json())

    delete_res = await client.delete(f"/api/v1/documents/{doc_id}")
    assert delete_res.status_code == 200
    assert delete_res.json()["deleted_at"] is not None

    get_after_delete = await client.get(f"/api/v1/documents/{doc_id}")
    assert get_after_delete.status_code == 404


@pytest.mark.asyncio
async def test_document_upload_rejects_unsupported_type(client: AsyncClient):
    files = {"file": ("resume.docx", b"binary-ish content", "application/octet-stream")}
    res = await client.post("/api/v1/documents", files=files)
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_knowledge_endpoints(client: AsyncClient):
    files = {"file": ("plan.md", b"# Plan\n\nProject: Atlas\n\nDue 2026-11-01.\n", "text/markdown")}
    upload_res = await client.post("/api/v1/documents", files=files)
    assert upload_res.status_code == 201

    entities_res = await client.get("/api/v1/knowledge/entities?entity_type=project")
    assert entities_res.status_code == 200
    assert any(e["name"] == "Atlas" for e in entities_res.json())

    search_res = await client.get("/api/v1/knowledge/search?q=Atlas")
    assert search_res.status_code == 200
    body = search_res.json()
    assert "documents" in body and "entities" in body

    timeline_res = await client.get("/api/v1/knowledge/timeline")
    assert timeline_res.status_code == 200
    timeline = timeline_res.json()
    assert any(item["date"] == "2026-11-01" for item in timeline["dated"])


@pytest.mark.asyncio
async def test_reuploading_identical_file_does_not_create_a_duplicate(client: AsyncClient):
    files = {"file": ("same.txt", b"Identical content twice.", "text/plain")}

    first = await client.post("/api/v1/documents", files=files)
    second = await client.post("/api/v1/documents", files=files)

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
