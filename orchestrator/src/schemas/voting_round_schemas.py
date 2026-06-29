import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from src.models.voting_round import RoundStage, RoundStatus
from src.schemas.agenda_item_schemas import AgendaItemResponse

class VotingRoundCreate(BaseModel):
    agenda_item_id: uuid.UUID
    stage: RoundStage
    specific_reference: Annotated[
        str | None,
        Field(default=None, max_length=100),
    ]
    voting_type_id: uuid.UUID
    is_nominal: bool = True
    president_votes_ordinarily: bool = False
    time_limit_seconds: Annotated[
        int | None,
        Field(default=None, ge=1, description="Countdown timer in seconds"),
    ] = None

class VotingRoundUpdate(BaseModel):
    specific_reference: Annotated[
        str | None,
        Field(default=None, max_length=100),
    ]
    voting_type_id: uuid.UUID | None = None
    is_nominal: bool | None = None
    president_votes_ordinarily: bool | None = None
    time_limit_seconds: Annotated[
        int | None,
        Field(default=None, ge=1, description="Countdown timer in seconds"),
    ] = None

class VotingRoundResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    agenda_item_id: uuid.UUID
    legislative_session_id: uuid.UUID
    stage: RoundStage
    specific_reference: str | None = None
    voting_type_id: uuid.UUID
    is_nominal: bool
    status: RoundStatus
    result: str | None = None
    quorum_present_count: int | None = None
    certified_quorum_count: int | None = None
    time_limit_seconds: int | None = None
    president_votes_ordinarily: bool
    tie_breaker_vote_value: str | None = None
    opened_at: datetime | None = None
    closed_at: datetime | None = None
    created_at: datetime
    deleted_at: datetime | None = None

class VotingRoundWithItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    agenda_item_id: uuid.UUID
    legislative_session_id: uuid.UUID
    stage: RoundStage
    specific_reference: str | None = None
    voting_type_id: uuid.UUID
    is_nominal: bool
    status: RoundStatus
    result: str | None = None
    quorum_present_count: int | None = None
    certified_quorum_count: int | None = None
    time_limit_seconds: int | None = None
    president_votes_ordinarily: bool
    tie_breaker_vote_value: str | None = None
    opened_at: datetime | None = None
    closed_at: datetime | None = None
    created_at: datetime

    agenda_item: AgendaItemResponse
