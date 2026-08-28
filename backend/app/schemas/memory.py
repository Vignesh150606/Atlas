from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from app.models.memory import MemoryType

class MemoryBase(BaseModel):
    title: str = Field(..., description="Memory title or summary")
    content: str = Field(..., description="Detailed content of the memory")
    memory_type: MemoryType = Field(default=MemoryType.FACT, description="Memory type classification")
    category: str = Field(default="general", description="Category grouping")
    importance: int = Field(default=3, ge=1, le=5, description="Importance level 1-5")
    is_pinned: bool = Field(default=False, description="Whether memory is pinned")
    source: str = Field(default="manual", description="Source of memory (manual, chat_extraction, system)")
    tags: List[str] = Field(default_factory=list, description="Tags for categorization")
    structured_data: Dict[str, Any] = Field(default_factory=dict, description="Type-specific structured payload")

class MemoryCreate(MemoryBase):
    pass

class MemoryUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    memory_type: Optional[MemoryType] = None
    category: Optional[str] = None
    importance: Optional[int] = Field(None, ge=1, le=5)
    is_pinned: Optional[bool] = None
    source: Optional[str] = None
    tags: Optional[List[str]] = None
    structured_data: Optional[Dict[str, Any]] = None

class MemoryResponse(MemoryBase):
    id: str
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None
    # Lifecycle fields (Phase 5) - system-managed, not settable via create/update
    confidence: int = 100
    last_used: Optional[datetime] = None
    access_count: int = 0
    verification_state: str = "unverified"

    class Config:
        from_attributes = True

class MemoryFilterParams(BaseModel):
    memory_type: Optional[MemoryType] = None
    category: Optional[str] = None
    tag: Optional[str] = None
    importance: Optional[int] = None
    is_pinned: Optional[bool] = None
    source: Optional[str] = None
    skip: int = 0
    limit: int = 100
