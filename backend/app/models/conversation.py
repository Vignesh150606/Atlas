from sqlalchemy import Column, String, ForeignKey
from sqlalchemy.orm import relationship
from app.models.base import TimestampModel

class Conversation(TimestampModel):
    __tablename__ = "conversations"

    title = Column(String, nullable=False, default="New Conversation")
    user_id = Column(String, nullable=True)

    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")
