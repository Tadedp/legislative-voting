import uuid

from fastapi import APIRouter, Depends, status

from src.api.dependencies.auth_deps import get_current_user, check_access
from src.api.dependencies.common_deps import DbSessionDep
from src.api.exceptions import BadRequestException, ConflictException, NotFoundException
from src.models.system_user import SystemUserRole
from src.schemas.voting_type_schemas import (
    VotingTypeCreate,
    VotingTypeResponse,
    VotingTypeUpdate,
)
from src.services import voting_type_service

voting_type_router = APIRouter(
    prefix="/voting-types",
    tags=["Voting Types"],
)

@voting_type_router.get(
    "",
    response_model=list[VotingTypeResponse],
    summary="List all voting types",
    description="Returns all active voting types.",
    dependencies=[Depends(get_current_user)],
)
async def list_voting_types(
    db_session: DbSessionDep,
) -> list[VotingTypeResponse]:
    voting_types = await voting_type_service.list_voting_types(db_session)
    return [VotingTypeResponse.model_validate(vt) for vt in voting_types]

@voting_type_router.get(
    "/{voting_type_id}",
    response_model=VotingTypeResponse,
    summary="Get voting type by ID",
    dependencies=[Depends(get_current_user)],
)
async def get_voting_type(
    db_session: DbSessionDep,
    voting_type_id: uuid.UUID,
) -> VotingTypeResponse:
    try:
        voting_type = await voting_type_service.get_voting_type(db_session, voting_type_id)
    except ValueError as exc:
        raise NotFoundException(str(exc))

    return VotingTypeResponse.model_validate(voting_type)

@voting_type_router.post(
    "",
    response_model=VotingTypeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a voting type",
    description="Defines a new voting type with threshold and abstention rules.",
    dependencies=[Depends(check_access([SystemUserRole.PRESIDENCY]))],
)
async def create_voting_type(
    db_session: DbSessionDep,
    body: VotingTypeCreate,
) -> VotingTypeResponse:
    try:
        voting_type = await voting_type_service.create_voting_type(
            db_session,
            name=body.name,
            allows_abstentions=body.allows_abstentions,
            approval_threshold=body.approval_threshold,
            calc_base=body.calc_base,
        )
    except ValueError as exc:
        raise ConflictException(str(exc))

    return VotingTypeResponse.model_validate(voting_type)

@voting_type_router.patch(
    "/{voting_type_id}",
    response_model=VotingTypeResponse,
    summary="Update a voting type",
    description="Partial update — only supplied fields are modified.",
    dependencies=[Depends(check_access([SystemUserRole.PRESIDENCY]))],
)
async def update_voting_type(
    db_session: DbSessionDep,
    voting_type_id: uuid.UUID,
    body: VotingTypeUpdate,
) -> VotingTypeResponse:
    update_data = body.model_dump(exclude_unset=True)

    if not update_data:
        raise BadRequestException("No fields provided for update.")

    try:
        voting_type = await voting_type_service.update_voting_type(
            db_session, voting_type_id, update_data=update_data,
        )
    except ValueError as exc:
        raise ConflictException(str(exc))

    return VotingTypeResponse.model_validate(voting_type)

@voting_type_router.delete(
    "/{voting_type_id}",
    response_model=VotingTypeResponse,
    summary="Soft-delete a voting type",
    description="Sets deleted_at. Protected if linked to active motions.",
    dependencies=[Depends(check_access([SystemUserRole.PRESIDENCY]))],
)
async def delete_voting_type(
    db_session: DbSessionDep,
    voting_type_id: uuid.UUID,
) -> VotingTypeResponse:
    try:
        voting_type = await voting_type_service.soft_delete_voting_type(
            db_session, voting_type_id,
        )
    except ValueError as exc:
        raise ConflictException(str(exc))

    return VotingTypeResponse.model_validate(voting_type)