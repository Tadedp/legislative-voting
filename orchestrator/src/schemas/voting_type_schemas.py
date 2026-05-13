import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

class VotingTypeCreate(BaseModel):
    name: Annotated[
        str,
        Field(min_length=1, max_length=100),
    ]
    allows_abstentions: bool = True
    approval_threshold: Annotated[
        Decimal,
        Field(gt=0, le=100, decimal_places=2),
    ]

class VotingTypeUpdate(BaseModel):
    name: Annotated[
        str | None,
        Field(default=None, min_length=1, max_length=100),
    ]
    allows_abstentions: bool | None = None
    approval_threshold: Annotated[
        Decimal | None,
        Field(default=None, gt=0, le=100, decimal_places=2),
    ]

class VotingTypeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    allows_abstentions: bool
    approval_threshold: Decimal
    created_at: datetime
    updated_at: datetime | None = None
    deleted_at: datetime | None = None