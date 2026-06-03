import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.legislative_session import LegislativeSession, PresidentType
from src.repositories import attendance_repository, legislator_repository

def compute_quorum_minimum(total_members: int) -> int:
    return total_members // 2 + 1

async def get_certified_quorum(
    db: AsyncSession,
    leg_session: LegislativeSession,
    *,
    president_votes_ordinarily: bool,
) -> tuple[int, int]:
    """Computes the legally binding quorum snapshot based on the attendance ledger."""
    quorum_present = await attendance_repository.count_present_by_session(
        db, leg_session.id,
    )
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
        # Assuming the president is always marked PRESENT if they are presiding.
        # If they aren't marked PRESENT, they shouldn't be presiding, but structurally
        # we reduce the requirements.
        if quorum_present > 0:
            quorum_present -= 1
        total_members -= 1

    return max(quorum_present, 0), max(total_members, 0)
