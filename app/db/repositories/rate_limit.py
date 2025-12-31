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
    
    Uses row-level locking (SELECT FOR UPDATE) to prevent race conditions
    when multiple concurrent requests try to check and update the same rate limit.
    """
    # Try to acquire row lock - this makes the check-and-update atomic
    row = (await session.execute(
        select(CommandRateLimit)
        .where(
            CommandRateLimit.user_id == user_id,
            CommandRateLimit.command == command,
        )
        .with_for_update()
    )).scalar_one_or_none()

    now = datetime.now(timezone.utc)

    if row is None:
        # Use ON CONFLICT DO NOTHING to handle race condition where
        # multiple requests try to insert the same (user_id, command) pair
        stmt = insert(CommandRateLimit).values(
            user_id=user_id, 
            command=command, 
            last_used_at=now
        ).on_conflict_do_nothing(
            index_elements=['user_id', 'command']
        )
        result = await session.execute(stmt)
        await session.commit()
        
        # If we successfully inserted, allow the request
        if result.rowcount > 0:
            return True, 0
        
        # If insert failed due to conflict, another request just created it
        # Retry the check with lock
        row = (await session.execute(
            select(CommandRateLimit)
            .where(
                CommandRateLimit.user_id == user_id,
                CommandRateLimit.command == command,
            )
            .with_for_update()
        )).scalar_one_or_none()
        
        if row is None:
            # Very unlikely, but handle it gracefully
            return True, 0

    # Check if enough time has passed
    delta = now - row.last_used_at
    if delta < timedelta(seconds=interval_seconds):
        retry = int(interval_seconds - delta.total_seconds())
        # Don't update the timestamp, just return False
        return False, retry

    # Update the timestamp and commit
    row.last_used_at = now
    await session.commit()
    return True, 0
