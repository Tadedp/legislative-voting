import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from src.models.voting_type import CalculationBase

class VotingTypeCreate(BaseModel):
    name: Annotated[
        str,
        Field(min_length=1, max_length=100),
    ]
    allows_abstentions: bool = True
    approval_threshold: Annotated[
        float,
        Field(ge=0, le=100, decimal_places=2),
    ]
    calc_base: CalculationBase = CalculationBase.VOTES_CAST

class VotingTypeUpdate(BaseModel):
    name: Annotated[
        str | None,
        Field(default=None, min_length=1, max_length=100),
    ]
    allows_abstentions: bool | None = None
    approval_threshold: Annotated[
        float | None,
        Field(default=None, ge=0, le=100, decimal_places=2),
    ]
    calc_base: CalculationBase | None = None

class VotingTypeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    allows_abstentions: bool
    approval_threshold: float
    calc_base: CalculationBase
    created_at: datetime
    updated_at: datetime | None = None
    deleted_at: datetime | None = None