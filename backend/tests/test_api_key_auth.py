import pytest
from httpx import AsyncClient
from app.core.config import settings


@pytest.fixture
def configured_api_key():
    """Temporarily sets settings.API_KEY for a test, restoring the
    previous value afterward - settings is a process-wide singleton
    (app.core.config.settings), so tests must not leak this across
    each other.
    """
    original = settings.API_KEY
    settings.API_KEY = "test-shared-key-123"
    yield settings.API_KEY
    settings.API_KEY = original


@pytest.mark.asyncio
async def test_unset_api_key_leaves_routes_open(client: AsyncClient):
    # Default (pre-Phase-11-compatible) behavior: no API_KEY configured
    # means no auth is enforced anywhere, including on a previously-open
    # deployment that hasn't opted in yet.
    assert settings.API_KEY is None
    response = await client.get("/api/v1/reminders")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_configured_api_key_rejects_missing_header(client: AsyncClient, configured_api_key):
    response = await client.get("/api/v1/reminders")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_configured_api_key_rejects_wrong_key(client: AsyncClient, configured_api_key):
    response = await client.get("/api/v1/reminders", headers={"X-API-Key": "wrong-key"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_configured_api_key_accepts_correct_key(client: AsyncClient, configured_api_key):
    response = await client.get("/api/v1/reminders", headers={"X-API-Key": configured_api_key})
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_health_stays_public_even_with_api_key_configured(client: AsyncClient, configured_api_key):
    # /health is deliberately excluded from auth (see app/api/v1/router.py)
    # so a client can tell "server unreachable" apart from "server
    # reachable, key missing/wrong" before it necessarily has a key.
    response = await client.get("/api/v1/health")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_configured_api_key_covers_every_phase10_resource_group(client: AsyncClient, configured_api_key):
    # Spot-check across resource groups, not just /reminders, since the
    # dependency is wired per-router in app/api/v1/router.py rather than
    # once globally - a single missed include_router() call would only
    # show up here, not in the /reminders-only tests above.
    for path in ("/api/v1/tasks", "/api/v1/routines", "/api/v1/briefing/daily", "/api/v1/memory"):
        response = await client.get(path)
        assert response.status_code == 401, f"{path} did not require the API key"
