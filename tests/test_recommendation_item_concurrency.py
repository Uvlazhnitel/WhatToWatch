"""
Test concurrent recommendation item creation to ensure no duplicates.
"""
from __future__ import annotations

import asyncio
import pytest
from sqlalchemy import select, func

from app.db.repositories.users import get_or_create_user
from app.db.repositories.recommendations import create_recommendation, add_recommendation_item
from app.db.models import AgentRecommendation, AgentRecommendationItem


@pytest.mark.asyncio
async def test_concurrent_add_recommendation_item_prevents_duplicates(session):
    """
    Test that concurrent calls to add_recommendation_item for the same
    recommendation don't create duplicate entries.
    """
    user = await get_or_create_user(session, telegram_id=8888)
    await session.commit()

    # Create a recommendation
    rec = await create_recommendation(
        session,
        user.id,
        context={"mode": "test", "count": 3},
    )

    # Try to add the same item concurrently (same recommendation_id, tmdb_id, position)
    results = await asyncio.gather(
        add_recommendation_item(session, rec.id, 550, 1, "safe", "Test explanation"),
        add_recommendation_item(session, rec.id, 550, 1, "safe", "Test explanation"),
        add_recommendation_item(session, rec.id, 550, 1, "safe", "Test explanation"),
        add_recommendation_item(session, rec.id, 550, 1, "safe", "Test explanation"),
        add_recommendation_item(session, rec.id, 550, 1, "safe", "Test explanation"),
    )

    # All should return successfully (either insert or return existing)
    assert len(results) == 5
    for item in results:
        assert item is not None
        assert item.recommendation_id == rec.id
        assert item.tmdb_id == 550
        assert item.position == 1

    # But only ONE record should exist in the database
    count = (await session.execute(
        select(func.count()).select_from(AgentRecommendationItem).where(
            AgentRecommendationItem.recommendation_id == rec.id,
            AgentRecommendationItem.tmdb_id == 550,
            AgentRecommendationItem.position == 1,
        )
    )).scalar_one()

    assert count == 1, f"Expected 1 item in database, got {count}"


@pytest.mark.asyncio
async def test_concurrent_different_positions_allowed(session):
    """
    Test that concurrent calls with different positions are allowed.
    """
    user = await get_or_create_user(session, telegram_id=8887)
    await session.commit()

    rec = await create_recommendation(
        session,
        user.id,
        context={"mode": "test"},
    )

    # Add items with different positions concurrently
    results = await asyncio.gather(
        add_recommendation_item(session, rec.id, 550, 1, "safe", "Item 1"),
        add_recommendation_item(session, rec.id, 550, 2, "safe", "Item 2"),
        add_recommendation_item(session, rec.id, 550, 3, "safe", "Item 3"),
    )

    assert len(results) == 3

    # All three should exist
    count = (await session.execute(
        select(func.count()).select_from(AgentRecommendationItem).where(
            AgentRecommendationItem.recommendation_id == rec.id,
            AgentRecommendationItem.tmdb_id == 550,
        )
    )).scalar_one()

    assert count == 3, f"Expected 3 items in database, got {count}"


@pytest.mark.asyncio
async def test_concurrent_different_tmdb_ids_allowed(session):
    """
    Test that concurrent calls with different tmdb_ids are allowed.
    """
    user = await get_or_create_user(session, telegram_id=8886)
    await session.commit()

    rec = await create_recommendation(
        session,
        user.id,
        context={"mode": "test"},
    )

    # Add items with different tmdb_ids concurrently
    results = await asyncio.gather(
        add_recommendation_item(session, rec.id, 550, 1, "safe", "Movie 1"),
        add_recommendation_item(session, rec.id, 680, 1, "adjacent", "Movie 2"),
        add_recommendation_item(session, rec.id, 13, 1, "wildcard", "Movie 3"),
    )

    assert len(results) == 3

    # All three should exist
    count = (await session.execute(
        select(func.count()).select_from(AgentRecommendationItem).where(
            AgentRecommendationItem.recommendation_id == rec.id,
        )
    )).scalar_one()

    assert count == 3, f"Expected 3 items in database, got {count}"


@pytest.mark.asyncio
async def test_sequential_same_item_returns_same_record(session):
    """
    Test that adding the same item sequentially returns the same record.
    """
    user = await get_or_create_user(session, telegram_id=8885)
    await session.commit()

    rec = await create_recommendation(
        session,
        user.id,
        context={"mode": "test"},
    )

    # Add the same item twice sequentially
    item1 = await add_recommendation_item(session, rec.id, 550, 1, "safe", "Test")
    item2 = await add_recommendation_item(session, rec.id, 550, 1, "safe", "Test")

    # Should be the same record (same ID)
    assert item1.id == item2.id
    assert item1.recommendation_id == item2.recommendation_id
    assert item1.tmdb_id == item2.tmdb_id
    assert item1.position == item2.position

    # Verify only one record exists
    count = (await session.execute(
        select(func.count()).select_from(AgentRecommendationItem).where(
            AgentRecommendationItem.recommendation_id == rec.id,
        )
    )).scalar_one()

    assert count == 1, f"Expected 1 item in database, got {count}"
