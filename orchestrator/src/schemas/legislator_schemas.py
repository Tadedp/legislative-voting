import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

class LegislatorEnroll(BaseModel):
    national_id: Annotated[
        str, 
        Field(min_length=1, max_length=255),
    ]
    full_name: Annotated[
        str, 
        Field(min_length=1, max_length=500),
    ]
    device_public_key: Annotated[
        str, 
        Field(min_length=1, max_length=255),
    ]
    mac_address: Annotated[
        str, 
        Field(min_length=1, max_length=50),
    ]

class LegislatorUpdate(BaseModel):
    national_id: Annotated[
        str | None, 
        Field(default=None, min_length=1, max_length=255),
    ]
    full_name: Annotated[
        str | None, 
        Field(default=None, min_length=1, max_length=500),
    ]

class DeviceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    legislator_id: uuid.UUID
    mac_address: str
    device_token: str
    assigned_at: datetime
    deleted_at: datetime | None = None

class LegislatorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    national_id: str
    full_name: str
    current_public_key: str | None = None
    enrolled_at: datetime
    updated_at: datetime | None = None
    deleted_at: datetime | None = None
    device: DeviceResponse | None = None