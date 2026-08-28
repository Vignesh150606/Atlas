from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.session import get_db
from app.schemas.memory import MemoryCreate, MemoryUpdate, MemoryResponse, MemoryFilterParams
from app.services.memory_service import MemoryService
from app.models.memory import MemoryType

router = APIRouter()

@router.post("", response_model=MemoryResponse, status_code=status.HTTP_201_CREATED)
async def create_memory(
    request: MemoryCreate,
    db: AsyncSession = Depends(get_db)
):
    try:
        service = MemoryService(db)
        return await service.create_memory(request)
    except ValueError as val_err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(val_err))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/search", response_model=List[MemoryResponse])
async def search_memories(
    q: str = Query(..., min_length=1, description="Search keyword"),
    memory_type: Optional[str] = Query(None, description="Optional memory type filter"),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db)
):
    service = MemoryService(db)
    return await service.search_memories(query=q, memory_type=memory_type, limit=limit)

@router.get("/{memory_id}", response_model=MemoryResponse)
async def get_memory(
    memory_id: str,
    db: AsyncSession = Depends(get_db)
):
    service = MemoryService(db)
    memory = await service.get_memory(memory_id)
    if not memory:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory not found")
    return memory

@router.get("", response_model=List[MemoryResponse])
async def list_memories(
    memory_type: Optional[MemoryType] = Query(None),
    category: Optional[str] = Query(None),
    tag: Optional[str] = Query(None),
    importance: Optional[int] = Query(None, ge=1, le=5),
    is_pinned: Optional[bool] = Query(None),
    source: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db)
):
    filters = MemoryFilterParams(
        memory_type=memory_type,
        category=category,
        tag=tag,
        importance=importance,
        is_pinned=is_pinned,
        source=source,
        skip=skip,
        limit=limit
    )
    service = MemoryService(db)
    return await service.list_memories(filters)

@router.patch("/{memory_id}", response_model=MemoryResponse)
async def update_memory(
    memory_id: str,
    request: MemoryUpdate,
    db: AsyncSession = Depends(get_db)
):
    service = MemoryService(db)
    updated = await service.update_memory(memory_id, request)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory not found")
    return updated

@router.delete("/{memory_id}", response_model=MemoryResponse)
async def delete_memory(
    memory_id: str,
    db: AsyncSession = Depends(get_db)
):
    service = MemoryService(db)
    deleted = await service.delete_memory(memory_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory not found")
    return deleted
