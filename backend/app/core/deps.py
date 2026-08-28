from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.database.session import get_db
from app.providers.base import LLMProvider
from app.providers.factory import provider_factory


def get_llm_provider(provider: Optional[str] = None) -> LLMProvider:
    """Resolve the active LLM provider from configuration (or an explicit
    override, e.g. `?provider=claude` on the chat endpoint for testing).
    """
    try:
        return provider_factory.get_provider(provider)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# Phase 11: single shared API key (see Settings.API_KEY's docstring in
# app/core/config.py for exactly what this does and does not protect
# against - not a multi-user auth system, see app/models/user.py).
# auto_error=False so a missing header reaches our own check as None
# rather than FastAPI auto-raising a less specific 403 first.
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(provided_key: Optional[str] = Depends(_api_key_header)) -> None:
    """Applied to every route except /health (see app/api/v1/router.py) -
    health stays public so a client can distinguish "server unreachable"
    from "server reachable, key missing/wrong" (the Android app checks
    health at startup before the user has necessarily entered a key in
    Settings).

    A no-op when settings.API_KEY is unset (the default): this is an
    opt-in hardening step, not a breaking change - every deployment that
    existed before Phase 11 keeps working exactly as before until its
    owner deliberately sets API_KEY.
    """
    if not settings.API_KEY:
        return
    if provided_key != settings.API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key.",
            headers={"WWW-Authenticate": "ApiKey"},
        )
