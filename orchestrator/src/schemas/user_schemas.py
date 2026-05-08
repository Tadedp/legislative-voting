import uuid
from datetime import datetime
from re import match
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field
from pydantic.functional_validators import AfterValidator

from src.models.system_user import SystemUserRole

_PASSWORD_PATTERN = (
    r"^"
    r"(?=.*[A-Z])"
    r"(?=.*[a-z])"
    r"(?=.*\d)"
    r'(?=.*[!@#$%^&*(),.?":{}|<>_\-+=\[\]\\/`~;\'])'
    r".{8,64}"
    r"$"
)

def validate_password(password: str) -> str:
    if not match(_PASSWORD_PATTERN, password):
        raise ValueError(
            "The password must be between 8 and 64 characters long, and include at least "
            "one uppercase letter, one lowercase letter, one number, and one special character."
        )
    return password

class UserCreate(BaseModel):
    username: Annotated[
        str,
        Field(min_length=1, max_length=64),
    ]
    password: Annotated[
        str,
        AfterValidator(validate_password),
    ]
    role: SystemUserRole

class UserUpdate(BaseModel):
    username: Annotated[
        str | None,
        Field(default=None, min_length=1, max_length=64),
    ]
    password: Annotated[
        str | None,
        AfterValidator(validate_password),
    ] = None
    role: SystemUserRole | None = None

class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str
    role: SystemUserRole
    created_at: datetime
    updated_at: datetime | None = None
    deleted_at: datetime | None = None