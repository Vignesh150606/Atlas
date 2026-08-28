from fastapi import APIRouter, Depends
from app.core.deps import verify_api_key
from app.api.v1.endpoints import (
    health, chat, memory, documents, knowledge,
    reminders, tasks, routines, briefing,
)

api_router = APIRouter()
# Phase 11: shared API key auth (see app/core/deps.py::verify_api_key and
# Settings.API_KEY). /health is deliberately excluded - it must stay
# reachable without a key so a client can tell "server down" apart from
# "server up, key missing/wrong" (the Android app's startup connectivity
# check happens before the user necessarily has a key entered).
api_router.include_router(health.router, prefix="/health", tags=["health"])
_auth = [Depends(verify_api_key)]
api_router.include_router(chat.router, prefix="/chat", tags=["chat"], dependencies=_auth)
api_router.include_router(memory.router, prefix="/memory", tags=["memory"], dependencies=_auth)
api_router.include_router(documents.router, prefix="/documents", tags=["documents"], dependencies=_auth)
api_router.include_router(knowledge.router, prefix="/knowledge", tags=["knowledge"], dependencies=_auth)
# Phase 10: Personal Assistant & Proactive Intelligence
api_router.include_router(reminders.router, prefix="/reminders", tags=["reminders"], dependencies=_auth)
api_router.include_router(tasks.router, prefix="/tasks", tags=["tasks"], dependencies=_auth)
api_router.include_router(routines.router, prefix="/routines", tags=["routines"], dependencies=_auth)
api_router.include_router(briefing.router, prefix="/briefing", tags=["briefing"], dependencies=_auth)


