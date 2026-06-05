from fastapi import APIRouter, Depends, Request, Response, status

from src.api.dependencies.auth_deps import get_current_user
from src.api.dependencies.common_deps import DbSessionDep
from src.api.exceptions import UnauthorizedException
from src.core.config import settings
from src.schemas.auth_schemas import LoginRequest
from src.services import auth_service

auth_router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)

from src.schemas.user_schemas import UserResponse

@auth_router.post(
    "/login",
    status_code=status.HTTP_200_OK,
    response_model=UserResponse,
    summary="System user login",
    description="Authenticate with username/password. Returns user data and session cookie.",
)
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db_session: DbSessionDep,
) -> UserResponse:
    try:
        user = await auth_service.authenticate_user(
            db_session,
            username=body.username,
            password=body.password,
        )
    except ValueError:
        raise UnauthorizedException("Invalid username or password.")
    
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    session_id = await auth_service.create_session(
        db_session,
        user_id=user.id,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    response.set_cookie(
        key=settings.security.SESSION_COOKIE_NAME,
        value=session_id,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=settings.security.SESSION_EXPIRY_SECONDS,
    )

    return UserResponse.model_validate(user)

@auth_router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="System user logout",
    description="Destroy the current session and clear the cookie.",
    dependencies=[Depends(get_current_user)],
)
async def logout(
    request: Request,
    response: Response,
    db_session: DbSessionDep,
) -> None:
    session_id: str | None = request.cookies.get(settings.security.SESSION_COOKIE_NAME)

    if session_id is not None:
        await auth_service.destroy_session(db_session, session_id=session_id)

    response.delete_cookie(
        key=settings.security.SESSION_COOKIE_NAME,
        httponly=True,
        secure=True,
        samesite="strict",
    )