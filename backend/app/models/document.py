import hashlib
import uuid
from enum import Enum
from sqlalchemy import Column, String, Text, Integer, DateTime, JSON
from app.models.base import TimestampModel


class DocumentSourceType(str, Enum):
    """File formats importable today, plus future-ready external sources.

    The first five are functional import pipelines (Phase 6). The last four
    are deliberately not implemented yet - they'd each need real external
    integration work (OAuth, API clients) that's out of scope here. They
    exist as named, registered placeholders (see
    app/importers/placeholders.py) rather than being invented later as an
    afterthought, following the same pattern this repo already uses for
    reserved-but-unbuilt scaffolding (see User/Setting models).
    """
    PDF = "pdf"
    MARKDOWN = "markdown"
    TXT = "txt"
    JSON = "json"
    CSV = "csv"
    CALENDAR = "calendar"   # placeholder - not implemented
    GITHUB = "github"       # placeholder - not implemented
    NOTES = "notes"         # placeholder - not implemented
    RESUME = "resume"       # placeholder - not implemented


class Document(TimestampModel):
    __tablename__ = "documents"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    title = Column(String, nullable=False, index=True)
    source = Column(String, nullable=False, default="upload", index=True)  # e.g. "upload"; future: "calendar", "github"
    file_type = Column(String, nullable=False, index=True)  # DocumentSourceType value
    original_filename = Column(String, nullable=True)
    author = Column(String, nullable=True)
    tags = Column(JSON, nullable=False, default=list)
    content = Column(Text, nullable=False, default="")  # extracted plain text, used for keyword search
    structured_data = Column(JSON, nullable=False, default=dict)  # format-specific payload (CSV rows, JSON body, etc.)
    content_hash = Column(String(64), nullable=False, index=True)  # sha256 of raw bytes, for de-dup
    size_bytes = Column(Integer, nullable=False, default=0)
    deleted_at = Column(DateTime, nullable=True, index=True)

    @staticmethod
    def compute_hash(raw_bytes: bytes) -> str:
        return hashlib.sha256(raw_bytes).hexdigest()
