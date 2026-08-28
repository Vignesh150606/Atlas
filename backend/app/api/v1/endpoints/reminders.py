from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.session import get_db
from app.schemas.reminder import ReminderCreate, ReminderCreateFromText, ReminderUpdate, ReminderResponse
from app.services.reminder_service import ReminderService

router = APIRouter()


@router.post("", response_model=ReminderResponse, status_code=status.HTTP_201_CREATED)
async def create_reminder(request: ReminderCreate, db: AsyncSession = Depends(get_db)):
    service = ReminderService(db)
    reminder = await service.create(request, source="api")
    await db.commit()
    return reminder


@router.post("/from-text", response_model=ReminderResponse, status_code=status.HTTP_201_CREATED)
async def create_reminder_from_text(request: ReminderCreateFromText, db: AsyncSession = Depends(get_db)):
    """Same parsing path chat uses (ReminderSkill/MemoryExtractor.parse_reminder
    + app/nlp/datetime_parser.py) - lets a non-chat client (e.g. a quick-add
    widget) get identical "tomorrow at 7pm"-style interpretation without
    going through the full /chat pipeline."""
    service = ReminderService(db)
    reminder = await service.create_from_text(
        text=request.text,
        reference_time=request.reference_time,
        timezone=request.timezone,
        conversation_id=request.conversation_id,
        source="api",
    )
    if not reminder:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not recognize a reminder request in that text (expected something like 'remind me to ...').",
        )
    await db.commit()
    return reminder


@router.get("", response_model=List[ReminderResponse])
async def list_reminders(
    status_filter: Optional[str] = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    service = ReminderService(db)
    return await service.list(status=status_filter, skip=skip, limit=limit)


@router.get("/upcoming", response_model=List[ReminderResponse])
async def list_upcoming_reminders(
    within_hours: int = Query(24, ge=1, le=24 * 30),
    db: AsyncSession = Depends(get_db),
):
    from datetime import timedelta
    service = ReminderService(db)
    return await service.get_upcoming(timedelta(hours=within_hours))


@router.get("/{reminder_id}", response_model=ReminderResponse)
async def get_reminder(reminder_id: str, db: AsyncSession = Depends(get_db)):
    service = ReminderService(db)
    reminder = await service.get(reminder_id)
    if not reminder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reminder not found")
    return reminder


@router.patch("/{reminder_id}", response_model=ReminderResponse)
async def update_reminder(reminder_id: str, request: ReminderUpdate, db: AsyncSession = Depends(get_db)):
    service = ReminderService(db)
    reminder = await service.update(reminder_id, request)
    if not reminder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reminder not found")
    await db.commit()
    return reminder


@router.post("/{reminder_id}/complete", response_model=ReminderResponse)
async def complete_reminder(reminder_id: str, db: AsyncSession = Depends(get_db)):
    service = ReminderService(db)
    reminder = await service.complete(reminder_id)
    if not reminder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reminder not found")
    await db.commit()
    return reminder


@router.post("/{reminder_id}/cancel", response_model=ReminderResponse)
async def cancel_reminder(reminder_id: str, db: AsyncSession = Depends(get_db)):
    service = ReminderService(db)
    reminder = await service.cancel(reminder_id)
    if not reminder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reminder not found")
    await db.commit()
    return reminder


@router.delete("/{reminder_id}", response_model=ReminderResponse)
async def delete_reminder(reminder_id: str, db: AsyncSession = Depends(get_db)):
    service = ReminderService(db)
    reminder = await service.delete(reminder_id)
    if not reminder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reminder not found")
    await db.commit()
    return reminder
