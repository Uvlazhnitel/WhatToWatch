from __future__ import annotations

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Feedback


async def get_feedback_count(session: AsyncSession, user_id: int) -> int:
    n = (await session.execute(
        select(func.count()).select_from(Feedback).where(Feedback.user_id == user_id)
    )).scalar_one()
    return int(n)
