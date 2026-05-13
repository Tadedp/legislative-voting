import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from src.models.motion import MotionStatus

class MotionCreate(BaseModel):
    title: Annotated[
        str,
        Field(min_length=1, max_length=500),
    ]
    summary: str | None = None
    voting_type_id: uuid.UUID
    is_nominal: bool = True

class MotionUpdate(BaseModel):
    title: Annotated[
        str | None, 
        Field(default=None, min_length=1, max_length=500)
    ]
    summary: str | None = None
    voting_type_id: uuid.UUID | None = None
    is_nominal: bool | None = None

class MotionStatusUpdate(BaseModel):
    status: MotionStatus

class MotionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    legislative_session_id: uuid.UUID
    title: str
    summary: str | None = None
    voting_type_id: uuid.UUID
    is_nominal: bool
    status: MotionStatus
    opened_at: datetime | None = None
    closed_at: datetime | None = None
    created_at: datetime
    deleted_at: datetime | None = None