from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class RoutineCreate(BaseModel):
    name: str = Field(..., min_length=1)
    description: Optional[str] = None
    steps: List[str] = Field(default_factory=list)
    time_of_day: Optional[str] = Field(default=None, description="'HH:MM' 24-hour local time, e.g. '07:30'")
    days_of_week: List[int] = Field(default_factory=list, description="0=Monday..6=Sunday; empty means every day")


class RoutineUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    steps: Optional[List[str]] = None
    time_of_day: Optional[str] = None
    days_of_week: Optional[List[int]] = None
    is_active: Optional[bool] = None


class RoutineResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    steps: List[str] = Field(default_factory=list)
    time_of_day: Optional[str] = None
    days_of_week: List[int] = Field(default_factory=list)
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
