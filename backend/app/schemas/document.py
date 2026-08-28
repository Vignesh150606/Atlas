from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from app.models.document import DocumentSourceType


class DocumentMetadata(BaseModel):
    """The metadata set the Phase 6 brief calls out explicitly. Kept as its
    own schema (rather than inlined into DocumentResponse) so importers can
    build and validate it before a Document row exists.
    """
    title: str
    source: str = "upload"
    file_type: DocumentSourceType
    original_filename: Optional[str] = None
    author: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    content_hash: str
    size_bytes: int = 0


class DocumentResponse(BaseModel):
    id: str
    title: str
    source: str
    file_type: str
    original_filename: Optional[str] = None
    author: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    content: str
    structured_data: Dict[str, Any] = Field(default_factory=dict)
    content_hash: str
    size_bytes: int
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class DocumentSummary(BaseModel):
    """Lighter-weight shape for list views - omits full content/structured_data
    so listing many documents doesn't ship megabytes of text over the wire."""
    id: str
    title: str
    source: str
    file_type: str
    tags: List[str] = Field(default_factory=list)
    author: Optional[str] = None
    size_bytes: int
    created_at: datetime

    class Config:
        from_attributes = True


class DocumentUpdate(BaseModel):
    title: Optional[str] = None
    tags: Optional[List[str]] = None
    author: Optional[str] = None


class DocumentFilterParams(BaseModel):
    file_type: Optional[str] = None
    source: Optional[str] = None
    tag: Optional[str] = None
    skip: int = 0
    limit: int = 100
