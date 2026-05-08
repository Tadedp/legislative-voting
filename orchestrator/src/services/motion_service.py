from typing import Any
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.motion import Motion, MotionStatus
from src.repositories import legislative_session_repository, motion_repository

async def list_motions_by_session(
    db: AsyncSession,
    session_id: uuid.UUID,
) -> list[Motion]:
    session = await legislative_session_repository.get_by_id(db, session_id)

    if session is None or session.deleted_at is not None:
        raise ValueError("Legislative session not found.")

    return await motion_repository.get_by_session_id(db, session_id)

async def get_motion(db: AsyncSession, motion_id: uuid.UUID) -> Motion:
    motion = await motion_repository.get_by_id(db, motion_id)

    if motion is None or motion.deleted_at is not None:
        raise ValueError("Motion not found.")

    return motion

async def create_motion(
    db: AsyncSession,
    *,
    session_id: uuid.UUID,
    title: str,
    is_nominal: bool = True,
) -> Motion:
    session = await legislative_session_repository.get_by_id(db, session_id)

    if session is None or session.deleted_at is not None:
        raise ValueError("Legislative session not found.")

    motion = Motion(
        legislative_session_id=session_id,
        title=title,
        is_nominal=is_nominal,
    )
    return await motion_repository.create(db, motion=motion)

async def update_motion(
    db: AsyncSession,
    motion_id: uuid.UUID,
    *,
    update_data: dict[str, Any],
) -> Motion:
    motion = await motion_repository.get_by_id(db, motion_id)

    if motion is None or motion.deleted_at is not None:
        raise ValueError("Motion not found.")

    if motion.status != MotionStatus.DRAFT:
        raise ValueError(
            "Cannot update motion: only motions with status 'DRAFT' "
            "can be modified.",
        )

    for field, value in update_data.items():
        setattr(motion, field, value)

    await db.flush()
    return motion

async def soft_delete_motion(
    db: AsyncSession,
    motion_id: uuid.UUID,
) -> Motion:
    motion = await motion_repository.get_by_id(db, motion_id)

    if motion is None or motion.deleted_at is not None:
        raise ValueError("Motion not found.")

    if motion.status != MotionStatus.DRAFT:
        raise ValueError(
            "Cannot delete motion: only motions with status 'DRAFT' "
            "can be deleted.",
        )

    motion.deleted_at = datetime.now(timezone.utc)
    await db.flush()
    return motion

async def update_motion_status(
    db: AsyncSession,
    motion_id: uuid.UUID,
    *,
    new_status: MotionStatus,
) -> Motion:
    motion = await motion_repository.get_by_id(db, motion_id)

    if motion is None or motion.deleted_at is not None:
        raise ValueError("Motion not found.")

    now = datetime.now(timezone.utc)

    if new_status == MotionStatus.VOTING_OPEN:
        existing_open = await motion_repository.get_open_motion_in_session(
            db, motion.legislative_session_id,
        )
        if existing_open is not None and existing_open.id != motion.id:
            raise ValueError(
                "Cannot open voting: another motion is already open "
                "in this session.",
            )
        motion.opened_at = now

    if new_status == MotionStatus.VOTING_CLOSED:
        motion.closed_at = now

    motion.status = new_status
    await db.flush()
    return motion

async def abort_motion(
    db: AsyncSession,
    motion_id: uuid.UUID,
) -> Motion:
    motion = await motion_repository.get_by_id(db, motion_id)

    if motion is None or motion.deleted_at is not None:
        raise ValueError("Motion not found.")

    await motion_repository.void_non_nominal_votes(db, motion_id)

    motion.status = MotionStatus.DRAFT
    motion.opened_at = None
    motion.closed_at = None
    await db.flush()
    return motion