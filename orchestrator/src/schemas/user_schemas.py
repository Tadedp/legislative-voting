from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from src.infrastructure.models.usuario import UserRole

_PASSWORD_PATTERN = (
    r"^"
    r"(?=.*[A-Z])"
    r"(?=.*[a-z])"
    r"(?=.*\d)"
    r'(?=.*[!@#$%^&*(),.?":{}|<>_\-+=\[\]\\/`~;\'])'
    r".{8,64}"
    r"$"
)

class UserCreate(BaseModel):
    username: Annotated[
        str,
        Field(min_length=1, max_length=64),
    ]
    password: Annotated[
        str,
        Field(pattern=_PASSWORD_PATTERN),
    ]
    nombre: Annotated[
        str,
        Field(min_length=1, max_length=64),
    ]
    apellido: Annotated[
        str,
        Field(min_length=1, max_length=64),
    ]
    rol: UserRole
    

class UserUpdate(BaseModel):
    username: Annotated[
        str | None,
        Field(default=None, min_length=1, max_length=64),
    ]
    nombre: Annotated[
        str | None,
        Field(default=None, min_length=1, max_length=64),
    ]
    apellido: Annotated[
        str | None,
        Field(default=None, min_length=1, max_length=64),
    ]

class PasswordUpdate(BaseModel):
    new_password: Annotated[
        str,
        Field(pattern=_PASSWORD_PATTERN),
    ]

class UserAdminUpdate(UserUpdate):
    rol: UserRole | None = None
    
class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    username: str
    nombre: str
    apellido: str
    
class UserAdminRead(UserRead):
    id: int
    rol: str
    created_at: datetime
    updated_at: datetime | None
    deleted_at: datetime | None
