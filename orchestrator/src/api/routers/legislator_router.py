import uuid

from fastapi import APIRouter, Depends, status

from src.api.dependencies.auth_deps import get_current_user, check_access
from src.api.dependencies.common_deps import DbSessionDep
from src.api.exceptions import BadRequestException, ConflictException, NotFoundException
from src.models.system_user import SystemUserRole
from src.schemas.legislator_schemas import (
    LegislatorCreate,
    LegislatorResponse,
    LegislatorUpdate,
)
from src.services import legislator_service

legislator_router = APIRouter(
    prefix="/legislators",
    tags=["Legislators"],
)

@legislator_router.get(
    "",
    response_model=list[LegislatorResponse],
    summary="List all legislators",
    description="Returns all active legislators with their devices.",
    dependencies=[Depends(get_current_user)],
)
async def list_legislators(
    db_session: DbSessionDep,
) -> list[LegislatorResponse]:
    legislators = await legislator_service.list_legislators(db_session)
    return [LegislatorResponse.model_validate(leg) for leg in legislators]

@legislator_router.get(
    "/{legislator_id}",
    response_model=LegislatorResponse,
    summary="Get legislator by ID",
    dependencies=[Depends(get_current_user)],
)
async def get_legislator(
    db_session: DbSessionDep,
    legislator_id: uuid.UUID,
) -> LegislatorResponse:
    try:
        legislator = await legislator_service.get_legislator(db_session, legislator_id)
    except ValueError as exc:
        raise NotFoundException(str(exc))
    
    return LegislatorResponse.model_validate(legislator)

@legislator_router.post(
    "",
    response_model=LegislatorResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a legislator",
    description="Creates a legislator and generates a provisioning token.",
    dependencies=[Depends(check_access([SystemUserRole.ADMIN, SystemUserRole.PRESIDENCY]))],
)
async def create_legislator(
    db_session: DbSessionDep,
    body: LegislatorCreate,
) -> LegislatorResponse:
    try:
        legislator = await legislator_service.create_legislator(
            db_session,
            national_id=body.national_id,
            full_name=body.full_name,
        )
    except ValueError as exc:
        raise ConflictException(str(exc))
    
    return LegislatorResponse.model_validate(legislator)

@legislator_router.post(
    "/{legislator_id}/provisioning-token",
    response_model=LegislatorResponse,
    status_code=status.HTTP_200_OK,
    summary="Regenerate a provisioning token",
    dependencies=[Depends(check_access([SystemUserRole.ADMIN, SystemUserRole.PRESIDENCY]))],
)
async def regenerate_token(
    db_session: DbSessionDep,
    legislator_id: uuid.UUID,
) -> LegislatorResponse:
    try:
        legislator = await legislator_service.regenerate_provisioning_token(db_session, legislator_id)
    except ValueError as exc:
        raise NotFoundException(str(exc))
        
    return LegislatorResponse.model_validate(legislator)

@legislator_router.patch(
    "/{legislator_id}",
    response_model=LegislatorResponse,
    summary="Update a legislator",
    description="Allows typo corrections on names or national IDs.",
    dependencies=[Depends(check_access([SystemUserRole.ADMIN]))],
)
async def update_legislator(
    db_session: DbSessionDep,
    legislator_id: uuid.UUID,
    body: LegislatorUpdate,
) -> LegislatorResponse:
    update_data = body.model_dump(exclude_unset=True)

    if not update_data:
        raise BadRequestException("No fields provided for update.")

    try:
        legislator = await legislator_service.update_legislator(
            db_session, legislator_id, update_data=update_data,
        )
    except ValueError as exc:
        raise NotFoundException(str(exc))
    
    return LegislatorResponse.model_validate(legislator)

@legislator_router.delete(
    "/{legislator_id}",
    response_model=LegislatorResponse,
    summary="Soft-delete a legislator",
    description="Deactivates legislator and cascades to their device.",
    dependencies=[Depends(check_access([SystemUserRole.ADMIN]))],
)
async def delete_legislator(
    db_session: DbSessionDep,
    legislator_id: uuid.UUID,
) -> LegislatorResponse:
    try:
        legislator = await legislator_service.soft_delete_legislator(
            db_session, legislator_id,
        )
    except ValueError as exc:
        raise NotFoundException(str(exc))
    
    return LegislatorResponse.model_validate(legislator)