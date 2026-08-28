import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    content = response.json()
    assert content["status"] == "healthy"
    assert content["version"] == "1.0"
    assert content["database"] == "connected"
