from sqlalchemy import Column, String, Boolean
from app.models.base import TimestampModel

class User(TimestampModel):
    """Reserved for future authentication work.

    ATLAS currently operates as a single-user assistant with no auth layer,
    so this model is intentionally unused by any repository/service/endpoint
    today. It's kept (rather than deleted) because auth-related config and
    dependencies (SECRET_KEY, python-jose, passlib) already exist in
    anticipation of this. Do not treat this as dead code to clean up without
    checking in first - it's a deliberate placeholder, not an oversight.
    """

    __tablename__ = "users"

    email = Column(String, unique=True, index=True, nullable=True)
    username = Column(String, unique=True, index=True, nullable=False, default="user")
    is_active = Column(Boolean, default=True)
