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