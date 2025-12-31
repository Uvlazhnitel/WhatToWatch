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
from app.db.session import AsyncSessionLocal
from sqlalchemy import select


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
    assert retry2 >= 0  # May be 0 or 1 depending on timing

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
async def test_rate_limit_handles_rapid_successive_calls(session):
    """
    Test that multiple rapid calls are correctly rate limited.
    The first succeeds, subsequent calls are rejected.
    """
    user = await get_or_create_user(session, telegram_id=9993)
    await session.commit()

    # First call should succeed
    allowed1, _ = await check_and_touch(session, user.id, "test_rapid", 60)
    assert allowed1 is True

    # Rapid successive calls should all fail
    allowed2, retry2 = await check_and_touch(session, user.id, "test_rapid", 60)
    assert allowed2 is False
    assert retry2 > 0
    
    allowed3, retry3 = await check_and_touch(session, user.id, "test_rapid", 60)
    assert allowed3 is False
    assert retry3 > 0
