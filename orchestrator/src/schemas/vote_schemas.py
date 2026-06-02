import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from src.models.nominal_vote import NominalVoteValue

class NominalVote(BaseModel):
    motion_id: uuid.UUID
    legislator_id: uuid.UUID
    vote_value: NominalVoteValue
    timestamp: Annotated[
        int,
        Field(gt=0, description="Unix epoch milliseconds"),
    ]
    cryptographic_signature: Annotated[
        str,
        Field(min_length=1),
    ]

class NonNominalVote(BaseModel):
    motion_id: uuid.UUID
    legislator_id: uuid.UUID
    encrypted_payload: Annotated[
        str,
        Field(min_length=1),
    ]
    timestamp: Annotated[
        int,
        Field(gt=0, description="Unix epoch milliseconds"),
    ]
    cryptographic_signature: Annotated[
        str,
        Field(min_length=1),
    ]

class TieBreakerVote(BaseModel):
    motion_id: uuid.UUID
    legislator_id: uuid.UUID
    vote_value: NominalVoteValue
    timestamp: Annotated[
        int,
        Field(gt=0, description="Unix epoch milliseconds"),
    ]
    cryptographic_signature: Annotated[
        str,
        Field(min_length=1),
    ]

class NominalVoteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_id: uuid.UUID
    voting_round_id: uuid.UUID
    legislator_id: uuid.UUID
    vote_value: NominalVoteValue
    cryptographic_signature: str
    timestamp: datetime


class NonNominalVoteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_id: uuid.UUID
    voting_round_id: uuid.UUID
    legislator_id: uuid.UUID
    encrypted_payload: str
    cryptographic_signature: str
    is_voided: bool
    timestamp: datetime