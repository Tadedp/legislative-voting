
from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends, Request, Header
from fastapi.security import APIKeyCookie
from structlog import get_logger

from src.api.exceptions import UnauthorizedException, ForbiddenException
from src.core.config import settings
from src.api.dependencies.common_deps import DbSessionDep
from src.repositories import device_repository, session_repository
from src.models.system_user import SystemUser, SystemUserRole
from src.models.device import Device

log = get_logger(__name__)

api_key_cookie = APIKeyCookie(
    name=settings.security.SESSION_COOKIE_NAME, 
    auto_error=False,
)

async def get_current_user(
    request: Request,
    db_session: DbSessionDep,
    cookie_token: str | None = Depends(api_key_cookie),
) -> SystemUser:
    if cookie_token is not None:
        session = await session_repository.get_session_with_user(db_session, cookie_token)
        
        if session is not None:
            return session.user

    raise UnauthorizedException("Authentication required.")

CurrentUserDep = Annotated[SystemUser, Depends(get_current_user)]

def check_access(
    allowed_roles: list[SystemUserRole] | None = None,
) -> Callable[[SystemUser], Awaitable[SystemUser]]:
    roles: frozenset[SystemUserRole] = frozenset(allowed_roles or [])

    async def _check_role(
        current_user: CurrentUserDep,
    ) -> SystemUser:
        if current_user.role not in roles:
            log.warning(
                "auth.forbidden",
                allowed_roles=allowed_roles,
                actual_role=current_user.role,
                usuario_id=str(current_user.id),
            )
            raise ForbiddenException(
                "You do not have permission to perform this action."
            )
        return current_user

    return _check_role

async def get_device_by_token(
    db_session: DbSessionDep,
    x_device_token: str | None = Header(None),
) -> Device:
    if x_device_token is None:
        raise UnauthorizedException("X-Device-Token header missing.")

    device = await device_repository.get_active_device_by_token(db_session, x_device_token)

    if device is None:
        raise UnauthorizedException("Invalid or deactivated device token.")

    return device