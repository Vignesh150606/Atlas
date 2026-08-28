from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.session import get_db
from app.schemas.routine import RoutineCreate, RoutineUpdate, RoutineResponse
from app.services.routine_service import RoutineService

router = APIRouter()


@router.post("", response_model=RoutineResponse, status_code=status.HTTP_201_CREATED)
async def create_routine(request: RoutineCreate, db: AsyncSession = Depends(get_db)):
    service = RoutineService(db)
    routine = await service.create(request)
    await db.commit()
    return routine


@router.get("", response_model=List[RoutineResponse])
async def list_routines(
    is_active: Optional[bool] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    service = RoutineService(db)
    return await service.list(is_active=is_active, skip=skip, limit=limit)


@router.get("/{routine_id}", response_model=RoutineResponse)
async def get_routine(routine_id: str, db: AsyncSession = Depends(get_db)):
    service = RoutineService(db)
    routine = await service.get(routine_id)
    if not routine:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Routine not found")
    return routine


@router.patch("/{routine_id}", response_model=RoutineResponse)
async def update_routine(routine_id: str, request: RoutineUpdate, db: AsyncSession = Depends(get_db)):
    service = RoutineService(db)
    routine = await service.update(routine_id, request)
    if not routine:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Routine not found")
    await db.commit()
    return routine


@router.delete("/{routine_id}", response_model=RoutineResponse)
async def delete_routine(routine_id: str, db: AsyncSession = Depends(get_db)):
    service = RoutineService(db)
    routine = await service.delete(routine_id)
    if not routine:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Routine not found")
    await db.commit()
    return routine
