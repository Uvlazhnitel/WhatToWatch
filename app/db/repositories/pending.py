from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import PendingAction


async def set_pending(session: AsyncSession, user_id: int, action_type: str, payload: dict) -> None:
    stmt = insert(PendingAction).values(
        user_id=user_id,
        action_type=action_type,
        payload_json=payload,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[PendingAction.user_id],
        set_={
            "action_type": action_type,
            "payload_json": payload,
        },
    )
    await session.execute(stmt)
    await session.commit()


async def get_pending(session: AsyncSession, user_id: int) -> PendingAction | None:
    return (await session.execute(select(PendingAction).where(PendingAction.user_id == user_id))).scalar_one_or_none()


async def clear_pending(session: AsyncSession, user_id: int) -> None:
    pending = await get_pending(session, user_id)
    if pending is None:
        return
    await session.delete(pending)
    await session.commit()
