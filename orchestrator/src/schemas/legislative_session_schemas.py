import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from src.models.legislative_session import LegSessionStatus
from src.models.motion import MotionStatus

class LegislativeSessionCreate(BaseModel):
    title: Annotated[
        str, 
        Field(min_length=1, max_length=500),
    ]

class LegislativeSessionUpdate(BaseModel):
    title: Annotated[
        str | None, 
        Field(default=None, min_length=1, max_length=500),
    ]

class LegislativeSessionStatusUpdate(BaseModel):
    status: LegSessionStatus

class EphemeralKeyRequest(BaseModel):
    ephemeral_public_key: Annotated[
        str, 
        Field(min_length=1),
    ]

class LegislativeSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    status: LegSessionStatus
    ephemeral_public_key: str | None
    opened_at: datetime | None = None
    closed_at: datetime | None = None
    created_at: datetime
    deleted_at: datetime | None = None

class MotionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    summary: str | None = None
    is_nominal: bool
    status: MotionStatus

class CurrentLegislativeSessionResponse(BaseModel):
    session: LegislativeSessionResponse
    active_motion: MotionResponse | None = None