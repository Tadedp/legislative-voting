import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from src.models.nominal_vote import VoteValue

class NominalVote(BaseModel):
    raw_payload_string: str
    cryptographic_signature: Annotated[
        str,
        Field(min_length=1),
    ]


class TieBreakerVote(BaseModel):
    raw_payload_string: str
    cryptographic_signature: Annotated[
        str,
        Field(min_length=1),
    ]

class NominalVoteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_id: uuid.UUID
    voting_round_id: uuid.UUID
    legislator_id: uuid.UUID
    vote_value: VoteValue
    cryptographic_signature: str
    timestamp: datetime

class VotingRoundTallyResponse(BaseModel):
    affirmative: int
    negative: int
    abstentions: int
    suggested_result: str

class VoteAuthorizeRequest(BaseModel):
    raw_payload_string: str
    ecdsa_signature: str

class VoteAuthorizeResponse(BaseModel):
    signed_blinded_token: str

class VoteCastRequest(BaseModel):
    voting_round_id: uuid.UUID
    vote_value: VoteValue
    ephemeral_pub: str
    server_signature: str
    vote_signature: str

class VoteCastResponse(BaseModel):
    status: str
    message: str