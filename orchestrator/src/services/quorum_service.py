import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.websocket import ConnectionManager
from src.models.legislative_session import LegislativeSession, PresidentType
from src.repositories import legislator_repository

def compute_quorum_minimum(total_members: int) -> int:
    return total_members // 2 + 1

async def get_session_quorum(
    db: AsyncSession,
    leg_session: LegislativeSession,
    ws_manager: ConnectionManager,
) -> tuple[int, int]:
    connected_ids: set[uuid.UUID] = ws_manager.connected_legislator_ids
    quorum_present = len(connected_ids)
    total_members = await legislator_repository.count_active_legislators(db)

    # Ex-officio presidents do not constitute quorum.
    if (
        leg_session.pres_type == PresidentType.EX_OFFICIO
        and leg_session.presiding_officer_id is not None
    ):
        if leg_session.presiding_officer_id in connected_ids:
            quorum_present -= 1
        total_members -= 1

    return quorum_present, total_members

async def get_motion_quorum(
    db: AsyncSession,
    leg_session: LegislativeSession,
    ws_manager: ConnectionManager,
    *,
    president_votes_ordinarily: bool,
) -> tuple[int, int]:
    connected_ids: set[uuid.UUID] = ws_manager.connected_legislator_ids
    quorum_present = len(connected_ids)
    total_members = await legislator_repository.count_active_legislators(db)

    should_subtract = False

    if (
        leg_session.pres_type == PresidentType.EX_OFFICIO
        and leg_session.presiding_officer_id is not None
    ):
        should_subtract = True
    elif (
        leg_session.pres_type == PresidentType.LEGISLATOR
        and not president_votes_ordinarily
        and leg_session.presiding_officer_id is not None
    ):
        # Legislator-president who does not vote ordinarily is
        # mathematically treated as an ex-officio president.
        should_subtract = True

    if should_subtract and leg_session.presiding_officer_id is not None:
        if leg_session.presiding_officer_id in connected_ids:
            quorum_present -= 1
        total_members -= 1

    return quorum_present, total_members
