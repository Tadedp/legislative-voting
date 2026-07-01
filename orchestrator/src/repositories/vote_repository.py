import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.nominal_vote import NominalVote, VoteValue
from src.models.non_nominal_tally import NonNominalTally
from src.models.non_nominal_voter import NonNominalVoter

async def create_nominal_vote(
    db: AsyncSession,
    *,
    vote: NominalVote,
) -> NominalVote:
    db.add(vote)
    await db.flush()
    return vote

async def create_non_nominal_voter_and_tally(
    db: AsyncSession,
    *,
    voter: NonNominalVoter,
    tally: NonNominalTally,
) -> None:
    db.add(voter)
    db.add(tally)
    await db.flush()

async def create_non_nominal_tally(
    db: AsyncSession,
    *,
    tally: NonNominalTally,
) -> None:
    db.add(tally)
    await db.flush()

async def create_non_nominal_voter(
    db: AsyncSession,
    *,
    voter: NonNominalVoter,
) -> None:
    db.add(voter)
    await db.flush()

async def get_non_nominal_voter(
    db: AsyncSession,
    voting_round_id: uuid.UUID,
    legislator_id: uuid.UUID,
) -> NonNominalVoter | None:
    stmt = select(NonNominalVoter).where(
        NonNominalVoter.voting_round_id == voting_round_id,
        NonNominalVoter.legislator_id == legislator_id,
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()

async def count_non_nominal_tallies_by_round(
    db: AsyncSession,
    voting_round_id: uuid.UUID,
) -> dict[VoteValue, int]:
    stmt = (
        select(NonNominalTally.vote_value, func.count())
        .where(NonNominalTally.voting_round_id == voting_round_id)
        .group_by(NonNominalTally.vote_value)
    )
    result = await db.execute(stmt)
    return {row[0]: row[1] for row in result.all()}

async def count_nominal_votes_by_round(
    db: AsyncSession,
    voting_round_id: uuid.UUID,
) -> dict[VoteValue, int]:
    stmt = (
        select(NominalVote.vote_value, func.count())
        .where(NominalVote.voting_round_id == voting_round_id)
        .group_by(NominalVote.vote_value)
    )
    result = await db.execute(stmt)
    return {row[0]: row[1] for row in result.all()}

async def count_tokens_issued(
    db: AsyncSession,
    voting_round_id: uuid.UUID,
) -> int:
    stmt = select(func.count()).select_from(NonNominalVoter).where(NonNominalVoter.voting_round_id == voting_round_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none() or 0

async def count_votes_received(
    db: AsyncSession,
    voting_round_id: uuid.UUID,
) -> int:
    stmt_non_nominal = select(func.count()).select_from(NonNominalTally).where(NonNominalTally.voting_round_id == voting_round_id)
    stmt_nominal = select(func.count()).select_from(NominalVote).where(NominalVote.voting_round_id == voting_round_id)
    
    res_non_nominal = await db.execute(stmt_non_nominal)
    res_nominal = await db.execute(stmt_nominal)
    
    return (res_non_nominal.scalar_one_or_none() or 0) + (res_nominal.scalar_one_or_none() or 0)