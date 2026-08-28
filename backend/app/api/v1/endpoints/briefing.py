from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.session import get_db
from app.schemas.briefing import DailyBriefingResponse, ProactiveSuggestionsResponse
from app.services.daily_briefing_service import DailyBriefingService
from app.services.proactive_suggestion_service import ProactiveSuggestionService

router = APIRouter()


@router.get("/daily", response_model=DailyBriefingResponse)
async def get_daily_briefing(
    within_hours: int = Query(24, ge=1, le=24 * 30),
    db: AsyncSession = Depends(get_db),
):
    from datetime import timedelta
    service = DailyBriefingService(db)
    return await service.build(upcoming_window=timedelta(hours=within_hours))


@router.get("/suggestions", response_model=ProactiveSuggestionsResponse)
async def get_proactive_suggestions(db: AsyncSession = Depends(get_db)):
    """Mission brief section 6/17: meant to be polled by the client
    (e.g. Android WorkManager every 15-30 minutes, or on app foreground) -
    not a backend background loop. Pure DB queries, no LLM call - see
    app/services/proactive_suggestion_service.py."""
    service = ProactiveSuggestionService(db)
    return await service.get_suggestions()
