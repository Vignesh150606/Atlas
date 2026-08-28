from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
from app.models.entity import EntityType


class EntityResponse(BaseModel):
    id: int
    entity_type: str
    name: str
    details: Dict[str, Any] = Field(default_factory=dict)
    document_id: str
    confidence: int
    created_at: datetime

    class Config:
        from_attributes = True


class EntityRelationshipResponse(BaseModel):
    id: int
    source_entity_id: int
    target_entity_id: int
    relationship_type: str

    class Config:
        from_attributes = True


class EntityFilterParams(BaseModel):
    entity_type: Optional[EntityType] = None
    document_id: Optional[str] = None
    skip: int = 0
    limit: int = 200
