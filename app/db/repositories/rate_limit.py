from __future__ import annotations

from datetime import datetime, timezone, timedelta
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CommandRateLimit


async def check_and_touch(
    session: AsyncSession,
    user_id: int,
    command: str,
    interval_seconds: int,
) -> tuple[bool, int]:
    """
    Возвращает (allowed, retry_after_seconds).
    Если allowed=True — обновляет last_used_at.
    """
    row = (await session.execute(
        select(CommandRateLimit).where(
            CommandRateLimit.user_id == user_id,
            CommandRateLimit.command == command,
        )
    )).scalar_one_or_none()

    now = datetime.now(timezone.utc)

    if row is None:
        stmt = insert(CommandRateLimit).values(user_id=user_id, command=command, last_used_at=now)
        await session.execute(stmt)
        await session.commit()
        return True, 0

    delta = now - row.last_used_at
    if delta < timedelta(seconds=interval_seconds):
        retry = int(interval_seconds - delta.total_seconds())
        return False, retry

    row.last_used_at = now
    await session.commit()
    return True, 0
