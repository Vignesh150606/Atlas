from sqlalchemy import Column, String, Text
from app.models.base import TimestampModel

class Setting(TimestampModel):
    """Reserved for future runtime configuration (e.g. active LLM provider,
    persona preferences). The Android Settings screen already exists as a UI
    placeholder for this but isn't wired to any backend yet. Kept intentionally
    rather than deleted - not dead code, just not built out yet.
    """

    __tablename__ = "settings"

    key = Column(String, unique=True, index=True, nullable=False)
    value = Column(Text, nullable=False)
