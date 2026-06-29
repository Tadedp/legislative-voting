from sqlalchemy.ext.asyncio import AsyncSession

from src.models.legislative_session import LegislativeSession, PresidentType
from src.repositories import attendance_repository, legislator_repository

from src.models.voting_type import CalculationBase

def compute_quorum_minimum(total_members: int) -> int:
    return total_members // 2 + 1

def calculate_effective_denominator(
    calculation_base: CalculationBase,
    president_type: PresidentType,
    president_votes_ordinarily: bool,
    raw_quorum: int,
    raw_total_members: int,
    votes_cast: int = 0,
) -> int:
    """Computes the mathematically correct denominator based on calculation_base."""
    should_subtract = False
    if president_type == PresidentType.EX_OFFICIO:
        should_subtract = True
    elif president_type == PresidentType.LEGISLATOR and not president_votes_ordinarily:
        should_subtract = True

    if calculation_base == CalculationBase.TOTAL_MEMBERS:
        denominator = raw_total_members - (1 if should_subtract else 0)
    elif calculation_base == CalculationBase.MEMBERS_PRESENT:
        denominator = raw_quorum - (1 if should_subtract else 0)
    elif calculation_base == CalculationBase.VOTES_CAST:
        # For VOTES_CAST, the denominator is exactly the votes cast (affirmative + negative).
        # The president deduction does not apply here because if they didn't vote, they aren't in votes_cast.
        denominator = votes_cast
    else:
        denominator = raw_total_members - (1 if should_subtract else 0)

    return max(denominator, 0)

async def get_certified_quorum(
    db: AsyncSession,
    leg_session: LegislativeSession,
    *,
    president_votes_ordinarily: bool,
) -> tuple[int, int]:
    """Computes the legally binding quorum snapshot based on the attendance ledger."""
    raw_quorum = await attendance_repository.count_present_by_session(
        db, leg_session.id,
    )
    raw_total = await legislator_repository.count_active_legislators(db)

    quorum_present = calculate_effective_denominator(
        CalculationBase.MEMBERS_PRESENT,
        leg_session.pres_type,
        president_votes_ordinarily,
        raw_quorum,
        raw_total,
    )
    
    total_members = calculate_effective_denominator(
        CalculationBase.TOTAL_MEMBERS,
        leg_session.pres_type,
        president_votes_ordinarily,
        raw_quorum,
        raw_total,
    )

    return quorum_present, total_members
