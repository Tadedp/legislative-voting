from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import db_session_factory

async def get_db_session() -> AsyncIterator[AsyncSession]:
    async with db_session_factory() as session:
        yield session
        await session.commit()

class PaginationParams:
    __slots__ = ("page", "page_size", "order_by", "order_dir")

    def __init__(
        self,
        page: Annotated[
            int, 
            Query(
                ge=1, 
                description="Page number",
            ),
        ] = 1,
        page_size: Annotated[
            int, 
            Query(
                ge=1,
                le=100, 
                description="Items per page",
            ),
        ] = 20,
        order_by: Annotated[
            str | None, 
            Query(
                description="Column name to sort by",
            ),
        ] = None,
        order_dir: Annotated[
            str, 
            Query(
                pattern="^(asc|desc)$", 
                description="Sort direction",
            ),
        ] = "asc",
    ) -> None:
        self.page = page
        self.page_size = page_size
        self.order_by = order_by
        self.order_dir = order_dir

DbSessionDep = Annotated[AsyncSession, Depends(get_db_session)]
PaginationDep = Annotated[PaginationParams, Depends(PaginationParams)]