import uuid

from fastapi import APIRouter, Depends, status, BackgroundTasks

from src.api.dependencies.auth_deps import get_current_user, check_access
from src.api.dependencies.common_deps import DbSessionDep
from src.api.exceptions import BadRequestException, ConflictException, NotFoundException
from src.core.websocket import manager
from src.models.system_user import SystemUserRole
from src.schemas.agenda_item_schemas import (
    AgendaItemCreate,
    AgendaItemResponse,
    AgendaItemUpdate,
)
from src.services import agenda_item_service

agenda_item_router = APIRouter(
    prefix="/agenda-items",
    tags=["Agenda Items"],
)

@agenda_item_router.get(
    "",
    response_model=list[AgendaItemResponse],
    summary="List all agenda items",
    description="Returns all active (non-deleted) agenda items.",
    dependencies=[Depends(get_current_user)],
)
async def list_agenda_items(
    db_session: DbSessionDep,
) -> list[AgendaItemResponse]:
    items = await agenda_item_service.list_agenda_items(db_session)
    return [AgendaItemResponse.model_validate(i) for i in items]

@agenda_item_router.post(
    "",
    response_model=AgendaItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an agenda item",
    description="Creates a new agenda item in DRAFT status.",
    dependencies=[Depends(check_access([SystemUserRole.PRESIDENCY]))],
)
async def create_agenda_item(
    db_session: DbSessionDep,
    body: AgendaItemCreate,
) -> AgendaItemResponse:
    item = await agenda_item_service.create_agenda_item(
        db_session,
        category=body.category,
        title=body.title,
        summary=body.summary,
        file_number=body.file_number,
    )
    return AgendaItemResponse.model_validate(item)

@agenda_item_router.get(
    "/{agenda_item_id}",
    response_model=AgendaItemResponse,
    summary="Get agenda item by ID",
    dependencies=[Depends(get_current_user)],
)
async def get_agenda_item(
    db_session: DbSessionDep,
    agenda_item_id: uuid.UUID,
) -> AgendaItemResponse:
    try:
        item = await agenda_item_service.get_agenda_item(
            db_session, agenda_item_id,
        )
    except ValueError as exc:
        raise NotFoundException(str(exc))

    return AgendaItemResponse.model_validate(item)

@agenda_item_router.patch(
    "/{agenda_item_id}",
    response_model=AgendaItemResponse,
    summary="Update an agenda item",
    dependencies=[Depends(check_access([SystemUserRole.PRESIDENCY]))],
)
async def update_agenda_item(
    db_session: DbSessionDep,
    background_tasks: BackgroundTasks,
    agenda_item_id: uuid.UUID,
    body: AgendaItemUpdate,
) -> AgendaItemResponse:
    update_data = body.model_dump(exclude_unset=True)

    if not update_data:
        raise BadRequestException("No fields provided for update.")

    try:
        item = await agenda_item_service.update_agenda_item(
            db_session, agenda_item_id, update_data=update_data,
        )
    except ValueError as exc:
        raise ConflictException(str(exc))

    response = AgendaItemResponse.model_validate(item)
    
    # Broadcast the updated item to all connected terminals
    background_tasks.add_task(
        manager.broadcast,
        "AGENDA_ITEM_UPDATED",
        response.model_dump(mode="json"),
    )

    return response

@agenda_item_router.delete(
    "/{agenda_item_id}",
    response_model=AgendaItemResponse,
    summary="Soft-delete an agenda item",
    dependencies=[Depends(check_access([SystemUserRole.PRESIDENCY]))],
)
async def delete_agenda_item(
    db_session: DbSessionDep,
    agenda_item_id: uuid.UUID,
) -> AgendaItemResponse:
    try:
        item = await agenda_item_service.soft_delete_agenda_item(
            db_session, agenda_item_id,
        )
    except ValueError as exc:
        raise ConflictException(str(exc))

    return AgendaItemResponse.model_validate(item)
