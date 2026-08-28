from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.database.session import get_db
from app.schemas.briefing import DailyBriefingResponse, ProactiveSuggestionsResponse
from app.services.daily_briefing_service import DailyBriefingService
from app.services.proactive_suggestion_service import ProactiveSuggestionService

router = APIRouter()


@router.get("/daily", response_model=DailyBriefingResponse)
async def get_daily_briefing(
    within_hours: int = Query(24, ge=1, le=24 * 30),
    # Phase 12 (ARCH-TZ): optional IANA zone from the client, used for
    # routine time-of-day matching (see DailyBriefingService.build /
    # RoutineService.get_active_around). Falls back to
    # settings.DEFAULT_TIMEZONE here at the API boundary, not inside the
    # service - the service itself defaults to None (no conversion) so its
    # own unit tests, which pass explicit already-local reference values,
    # keep their exact pre-Phase-12 meaning.
    client_timezone: Optional[str] = Query(None, description="IANA timezone name, e.g. 'Asia/Kolkata'"),
    db: AsyncSession = Depends(get_db),
):
    from datetime import timedelta
    service = DailyBriefingService(db)
    return await service.build(
        upcoming_window=timedelta(hours=within_hours),
        client_timezone=client_timezone or settings.DEFAULT_TIMEZONE,
    )


@router.get("/suggestions", response_model=ProactiveSuggestionsResponse)
async def get_proactive_suggestions(
    client_timezone: Optional[str] = Query(None, description="IANA timezone name, e.g. 'Asia/Kolkata'"),
    db: AsyncSession = Depends(get_db),
):
    """Mission brief section 6/17: meant to be polled by the client
    (e.g. Android WorkManager every 15-30 minutes, or on app foreground) -
    not a backend background loop. Pure DB queries, no LLM call - see
    app/services/proactive_suggestion_service.py.

    Phase 12 (ARCH-TZ): see get_daily_briefing above for why the
    DEFAULT_TIMEZONE fallback happens here rather than inside the service.
    """
    service = ProactiveSuggestionService(db)
    return await service.get_suggestions(client_timezone=client_timezone or settings.DEFAULT_TIMEZONE)
