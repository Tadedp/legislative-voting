import uuid
from typing import Annotated
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from src.models.nominal_vote import NominalVoteValue

class NominalVote(BaseModel):
    """Schema for a cryptographically signed nominal vote payload.

    Sent from the voter terminal (Android device). The signature covers
    the canonical JSON representation of all fields except the signature
    itself.
    """

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
    """Schema for a cryptographically signed non-nominal vote payload.

    The encrypted_payload is opaque to the orchestrator (blind conduit).
    The signature proves the legislator cast the vote without revealing
    its content.
    """

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
    """Schema for a cryptographically signed presidential tie-breaking vote.

    The payload structure mirrors NominalVote but is validated against
    the session's presiding_officer_id instead of the general legislator
    pool. Only AFFIRMATIVE or NEGATIVE values are permitted.
    """

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
    motion_id: uuid.UUID
    legislator_id: uuid.UUID
    vote_value: NominalVoteValue
    cryptographic_signature: str
    timestamp: datetime

class NonNominalVoteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_id: uuid.UUID
    motion_id: uuid.UUID
    legislator_id: uuid.UUID
    encrypted_payload: str
    cryptographic_signature: str
    is_voided: bool
    timestamp: datetime