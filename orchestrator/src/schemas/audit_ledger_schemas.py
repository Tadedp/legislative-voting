from typing import Annotated

from pydantic import BaseModel, Field

class NominalVote(BaseModel):
    legislator_id: str
    legislator_name: str
    public_key_pem: str
    value: str
    signature: str
    timestamp: int

class AnonymousVote(BaseModel):
    value: str
    salt: str

class VerifiedParticipant(BaseModel):
    legislator_id: str
    legislator_name: str
    public_key_pem: str
    signature: str
    timestamp: int

class TallyPayload(BaseModel):
    voting_round_id: str
    agenda_item_title: str
    is_nominal: bool
    timestamp: str
    tallies: dict[str, int]
    nominal_votes: Annotated[
        list[NominalVote],
        Field(default_factory=list),
    ]
    anonymous_votes: Annotated[
        list[AnonymousVote],
        Field(default_factory=list),
    ]
    verified_participants: Annotated[
        list[VerifiedParticipant],
        Field(default_factory=list),
    ]