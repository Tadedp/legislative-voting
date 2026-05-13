import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, status

from src.api.dependencies.auth_deps import check_access
from src.api.dependencies.common_deps import DbSessionDep
from src.api.exceptions import NotFoundException
from src.core.websocket import manager
from src.models.system_user import SystemUserRole
from src.schemas.legislator_schemas import DeviceResponse
from src.services import device_service

device_router = APIRouter(
    prefix="/devices",
    tags=["Devices"],
)

@device_router.post(
    "/{device_id}/wipe",
    response_model=DeviceResponse,
    status_code=status.HTTP_200_OK,
    summary="Wipe and revoke a device",
    description=(
        "Soft-deletes the device and its linked legislator, invalidates "
        "the device token, and pushes a targeted DEVICE_WIPE_COMMAND via WebSocket."
    ),
    dependencies=[Depends(check_access([SystemUserRole.ADMIN]))],
)
async def wipe_device(
    db_session: DbSessionDep,
    background_tasks: BackgroundTasks,
    device_id: uuid.UUID,
) -> DeviceResponse:
    try:
        device, old_device_token = await device_service.wipe_device(
            db_session, device_id,
        )
    except ValueError as exc:
        raise NotFoundException(str(exc))

    response = DeviceResponse.model_validate(device)

    background_tasks.add_task(
        manager.send_to_device,
        old_device_token,
        "DEVICE_WIPE_COMMAND",
        {"device_id": str(device_id)},
    )

    return response
