from sqlalchemy import Column, Integer, DateTime
from app.database.base_class import Base
from app.utils.time import utc_now

class TimestampModel(Base):
    __abstract__ = True
    
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)
