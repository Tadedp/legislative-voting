import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from src.models.agenda_item import ItemCategory, ItemStatus, ParliamentaryStage

class AgendaItemCreate(BaseModel):
    category: ItemCategory
    title: Annotated[
        str,
        Field(min_length=1, max_length=500),
    ]
    summary: str | None = None
    file_number: Annotated[
        str | None,
        Field(default=None, max_length=100),
    ]

class AgendaItemUpdate(BaseModel):
    title: Annotated[
        str | None,
        Field(default=None, min_length=1, max_length=500),
    ]
    summary: str | None = None
    file_number: str | None = None
    status: ItemStatus | None = None
    parliamentary_stage: ParliamentaryStage | None = None
    is_active: bool | None = None

class AgendaItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    category: ItemCategory
    file_number: str | None = None
    title: str
    summary: str | None = None
    parliamentary_stage: ParliamentaryStage
    status: ItemStatus
    is_active: bool
    created_at: datetime
    updated_at: datetime | None = None
    deleted_at: datetime | None = None
