from typing import Annotated

from pydantic import BaseModel, Field

class ErrorDetail(BaseModel):
    code: Annotated[
        str, 
        Field(
            description="A machine-readable error code",
        )
    ]
    message: Annotated[
        str, 
        Field(
            description="A human-readable error message",
        )
    ]

class MetaData(BaseModel):
    page: Annotated[
        int | None, 
        Field(
            default=None, 
            ge=1, 
            description="Current page number",
        )
    ]
    page_size: Annotated[
        int | None, 
        Field(
            default=None, 
            ge=1, 
            description="Items per page",
        )
    ]
    order_by: Annotated[
        str | None, 
        Field(
            default=None, 
            description="Column name to sort by",
        )
    ]
    order_dir: Annotated[
        str | None, 
        Field(
            default=None, 
            pattern="^(asc|desc)$", 
            description="Sort direction",
        )
    ]
    total_pages: Annotated[
        int | None, 
        Field(
            default=None, 
            ge=1, 
            description="Total number of pages",
        )
    ]
    total: Annotated[
        int | None, 
        Field(
            default=None, 
            ge=0, 
            description="Total number of items",
        )
    ]

class ResponseEnvelope[T](BaseModel):
    data: T | None = None
    error: ErrorDetail | None = None
    meta: MetaData | None = None