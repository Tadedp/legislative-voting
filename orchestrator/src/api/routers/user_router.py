import uuid

from fastapi import APIRouter, Depends, status

from src.api.dependencies.auth_deps import check_access
from src.api.dependencies.common_deps import DbSessionDep
from src.api.exceptions import BadRequestException, ConflictException, NotFoundException
from src.models.system_user import SystemUserRole
from src.schemas.user_schemas import UserCreate, UserResponse, UserUpdate
from src.services import user_service

user_router = APIRouter(
    prefix="/users",
    tags=["Users"],
)

@user_router.get(
    "",
    response_model=list[UserResponse],
    summary="List all users",
    description="Returns all active system operators.",
    dependencies=[Depends(check_access([SystemUserRole.ADMIN, SystemUserRole.PRESIDENCY]))],
)
async def list_users(
    db_session: DbSessionDep,
) -> list[UserResponse]:
    users = await user_service.list_users(db_session)
    return [UserResponse.model_validate(u) for u in users]

@user_router.get(
    "/{user_id}",
    response_model=UserResponse,
    summary="Get user by ID",
    dependencies=[Depends(check_access([SystemUserRole.ADMIN, SystemUserRole.PRESIDENCY]))],
)
async def get_user(
    db_session: DbSessionDep,
    user_id: uuid.UUID,
) -> UserResponse:
    try:
        user = await user_service.get_user(db_session, user_id)
    except ValueError as exc:
        raise NotFoundException(str(exc))
    
    return UserResponse.model_validate(user)

@user_router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new user",
    dependencies=[Depends(check_access([SystemUserRole.ADMIN]))],
)
async def create_user(
    db_session: DbSessionDep,
    body: UserCreate,
) -> UserResponse:
    try:
        user = await user_service.create_user(
            db_session,
            username=body.username,
            password=body.password,
            role=body.role,
        )
    except ValueError as exc:
        raise ConflictException(str(exc))
    
    return UserResponse.model_validate(user)

@user_router.patch(
    "/{user_id}",
    response_model=UserResponse,
    summary="Update a user",
    description="Partial update — only supplied fields are modified.",
    dependencies=[Depends(check_access([SystemUserRole.ADMIN]))],
)
async def update_user(
    db_session: DbSessionDep,
    user_id: uuid.UUID,
    body: UserUpdate,
) -> UserResponse:
    update_data = body.model_dump(exclude_unset=True)

    if not update_data:
        raise BadRequestException("No fields provided for update.")

    try:
        user = await user_service.update_user(db_session, user_id, update_data=update_data)
    except ValueError as exc:
        raise NotFoundException(str(exc))
    
    return UserResponse.model_validate(user)

@user_router.delete(
    "/{user_id}",
    response_model=UserResponse,
    summary="Soft-delete a user",
    description="Sets deleted_at = now().",
    dependencies=[Depends(check_access([SystemUserRole.ADMIN]))],
)
async def delete_user(
    db_session: DbSessionDep,
    user_id: uuid.UUID,
) -> UserResponse:
    try:
        user = await user_service.soft_delete_user(db_session, user_id)
    except ValueError as exc:
        raise NotFoundException(str(exc))
    
    return UserResponse.model_validate(user)