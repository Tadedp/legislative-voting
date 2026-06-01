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
    president_votes_ordinarily: bool = False

class MotionUpdate(BaseModel):
    title: Annotated[
        str | None,
        Field(default=None, min_length=1, max_length=500),
    ]
    summary: str | None = None
    voting_type_id: uuid.UUID | None = None
    is_nominal: bool | None = None
    president_votes_ordinarily: bool | None = None

class MotionStatusUpdate(BaseModel):
    status: MotionStatus

class MotionResolveRequest(BaseModel):
    affirmative: Annotated[
        int | None,
        Field(
            default=None,
            ge=0,
            description="Affirmative vote count (required for non-nominal motions)",
        ),
    ]
    negative: Annotated[
        int | None,
        Field(
            default=None,
            ge=0,
            description="Negative vote count (required for non-nominal motions)",
        ),
    ]
    abstentions: Annotated[
        int | None,
        Field(
            default=None,
            ge=0,
            description="Abstention count (required for non-nominal motions)",
        ),
    ]

class MotionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    legislative_session_id: uuid.UUID
    title: str
    summary: str | None = None
    voting_type_id: uuid.UUID
    is_nominal: bool
    status: MotionStatus
    result: str | None = None
    quorum_present_count: int | None = None
    president_votes_ordinarily: bool
    tie_breaker_vote_value: str | None = None
    opened_at: datetime | None = None
    closed_at: datetime | None = None
    created_at: datetime
    deleted_at: datetime | None = None