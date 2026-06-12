import uuid
from typing import Annotated

from pydantic import BaseModel, Field

class DeviceEnrollRequest(BaseModel):
    provisioning_token: Annotated[
        str, 
        Field(min_length=8, max_length=8),
    ]
    biometric_payload: Annotated[
        str, 
        Field(min_length=1),
    ]
    hardware_fingerprint: Annotated[
        str, 
        Field(min_length=64, max_length=64),
    ]
    certificate_chain: Annotated[
        list[str], 
        Field(min_length=1),
    ]

class DeviceEnrollResponse(BaseModel):
    device_token: str
    device_id: uuid.UUID
    legislator_id: uuid.UUID
