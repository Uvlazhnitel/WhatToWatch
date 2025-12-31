"""
Test concurrent command rate limiting to ensure no race conditions.
"""
from __future__ import annotations

import asyncio
import pytest
from datetime import datetime, timezone

from app.db.repositories.users import get_or_create_user
from app.db.repositories.rate_limit import check_and_touch
from app.db.models import CommandRateLimit
from sqlalchemy import select


@pytest.mark.asyncio
async def test_concurrent_rate_limit_prevents_duplicates(session):
    """
    Test that concurrent calls to check_and_touch don't allow multiple
    requests through when they should be rate-limited.
    """
    user = await get_or_create_user(session, telegram_id=9999)
    await session.commit()

    # Make concurrent calls to check_and_touch
    results = await asyncio.gather(
        check_and_touch(session, user.id, "recommend", 60),
        check_and_touch(session, user.id, "recommend", 60),
        check_and_touch(session, user.id, "recommend", 60),
        check_and_touch(session, user.id, "recommend", 60),
        check_and_touch(session, user.id, "recommend", 60),
    )

    # Only one should be allowed
    allowed_count = sum(1 for allowed, _ in results if allowed)
    assert allowed_count == 1, f"Expected 1 allowed request, got {allowed_count}"

    # All others should be denied with a retry time
    denied_results = [r for r in results if not r[0]]
    assert len(denied_results) == 4, "Expected 4 denied requests"
    
    # All denied requests should have a retry time close to 60 seconds
    for allowed, retry in denied_results:
        assert not allowed
        assert 58 <= retry <= 60, f"Expected retry around 60 seconds, got {retry}"


@pytest.mark.asyncio
async def test_rate_limit_allows_after_interval(session):
    """
    Test that rate limit allows requests after the interval has passed.
    """
    user = await get_or_create_user(session, telegram_id=9998)
    await session.commit()

    # First call should succeed
    allowed1, retry1 = await check_and_touch(session, user.id, "recommend", 1)
    assert allowed1 is True
    assert retry1 == 0

    # Immediate second call should fail
    allowed2, retry2 = await check_and_touch(session, user.id, "recommend", 1)
    assert allowed2 is False
    assert retry2 > 0

    # Wait for the interval
    await asyncio.sleep(1.1)

    # Third call should succeed
    allowed3, retry3 = await check_and_touch(session, user.id, "recommend", 1)
    assert allowed3 is True
    assert retry3 == 0


@pytest.mark.asyncio
async def test_rate_limit_per_command(session):
    """
    Test that rate limits are per-command, not per-user.
    """
    user = await get_or_create_user(session, telegram_id=9997)
    await session.commit()

    # Different commands should not interfere with each other
    allowed1, _ = await check_and_touch(session, user.id, "recommend", 60)
    allowed2, _ = await check_and_touch(session, user.id, "review", 60)

    assert allowed1 is True
    assert allowed2 is True

    # But the same command should be rate limited
    allowed3, retry3 = await check_and_touch(session, user.id, "recommend", 60)
    assert allowed3 is False
    assert retry3 > 0


@pytest.mark.asyncio
async def test_rate_limit_per_user(session):
    """
    Test that rate limits are per-user.
    """
    user1 = await get_or_create_user(session, telegram_id=9996)
    user2 = await get_or_create_user(session, telegram_id=9995)
    await session.commit()

    # Different users should not interfere with each other
    allowed1, _ = await check_and_touch(session, user1.id, "recommend", 60)
    allowed2, _ = await check_and_touch(session, user2.id, "recommend", 60)

    assert allowed1 is True
    assert allowed2 is True


@pytest.mark.asyncio
async def test_concurrent_first_time_rate_limit(session):
    """
    Test that concurrent first-time calls (no existing rate limit record)
    only allow one through.
    """
    user = await get_or_create_user(session, telegram_id=9994)
    await session.commit()

    # Ensure no rate limit record exists
    existing = (await session.execute(
        select(CommandRateLimit).where(
            CommandRateLimit.user_id == user.id,
            CommandRateLimit.command == "test_cmd",
        )
    )).scalar_one_or_none()
    assert existing is None

    # Make concurrent calls for a command that has no rate limit record yet
    results = await asyncio.gather(
        check_and_touch(session, user.id, "test_cmd", 60),
        check_and_touch(session, user.id, "test_cmd", 60),
        check_and_touch(session, user.id, "test_cmd", 60),
    )

    # Only one should be allowed
    allowed_count = sum(1 for allowed, _ in results if allowed)
    assert allowed_count == 1, f"Expected 1 allowed request, got {allowed_count}"
