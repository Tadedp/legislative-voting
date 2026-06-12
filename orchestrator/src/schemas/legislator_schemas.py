import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

class LegislatorCreate(BaseModel):
    national_id: Annotated[
        str, 
        Field(min_length=1, max_length=255),
    ]
    full_name: Annotated[
        str, 
        Field(min_length=1, max_length=500),
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
    hardware_fingerprint: str
    device_token: str
    assigned_at: datetime
    deleted_at: datetime | None = None

class LegislatorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    national_id: str
    full_name: str
    provisioning_token: str | None = None
    provisioning_token_expires_at: datetime | None = None
    enrolled_at: datetime
    updated_at: datetime | None = None
    deleted_at: datetime | None = None
    device: DeviceResponse | None = None