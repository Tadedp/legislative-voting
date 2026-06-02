import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from src.models.legislative_session import LegSessionStatus, PresidentType
from src.schemas.voting_round_schemas import VotingRoundWithItemResponse
from src.schemas.agenda_item_schemas import AgendaItemResponse

class LegislativeSessionCreate(BaseModel):
    title: Annotated[
        str,
        Field(min_length=1, max_length=500),
    ]
    pres_type: PresidentType = PresidentType.EX_OFFICIO
    presiding_officer_id: uuid.UUID | None = None

class LegislativeSessionUpdate(BaseModel):
    title: Annotated[
        str | None,
        Field(default=None, min_length=1, max_length=500),
    ]
    pres_type: PresidentType | None = None
    presiding_officer_id: uuid.UUID | None = None

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
    pres_type: PresidentType
    presiding_officer_id: uuid.UUID | None = None
    opened_at: datetime | None = None
    closed_at: datetime | None = None
    created_at: datetime
    deleted_at: datetime | None = None

class CurrentLegislativeSessionResponse(BaseModel):
    session: LegislativeSessionResponse
    active_voting_round: VotingRoundWithItemResponse | None = None
    active_agenda_item: AgendaItemResponse | None = None