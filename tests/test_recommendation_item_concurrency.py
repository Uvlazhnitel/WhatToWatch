"""
Test recommendation item creation to ensure no duplicates.
"""
from __future__ import annotations

import pytest
from sqlalchemy import select, func

from app.db.repositories.users import get_or_create_user
from app.db.repositories.recommendations import create_recommendation, add_recommendation_item
from app.db.models import AgentRecommendationItem


@pytest.mark.asyncio
async def test_different_positions_allowed(session):
    """
    Test that items with different positions can be added to the same recommendation.
    """
    user = await get_or_create_user(session, telegram_id=8887)
    await session.commit()

    rec = await create_recommendation(
        session,
        user.id,
        context={"mode": "test"},
    )

    # Add items with different positions
    item1 = await add_recommendation_item(session, rec.id, 550, 1, "safe", "Item 1")
    item2 = await add_recommendation_item(session, rec.id, 550, 2, "safe", "Item 2")
    item3 = await add_recommendation_item(session, rec.id, 550, 3, "safe", "Item 3")
    
    results = [item1, item2, item3]
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
async def test_different_tmdb_ids_allowed(session):
    """
    Test that items with different tmdb_ids can be added to the same recommendation.
    """
    user = await get_or_create_user(session, telegram_id=8886)
    await session.commit()

    rec = await create_recommendation(
        session,
        user.id,
        context={"mode": "test"},
    )

    # Add items with different tmdb_ids
    item1 = await add_recommendation_item(session, rec.id, 550, 1, "safe", "Movie 1")
    item2 = await add_recommendation_item(session, rec.id, 680, 1, "adjacent", "Movie 2")
    item3 = await add_recommendation_item(session, rec.id, 13, 1, "wildcard", "Movie 3")
    
    results = [item1, item2, item3]
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
    Test that adding the same item multiple times returns the same record.
    This validates the upsert logic that prevents duplicates.
    """
    user = await get_or_create_user(session, telegram_id=8885)
    await session.commit()

    rec = await create_recommendation(
        session,
        user.id,
        context={"mode": "test"},
    )

    # Add the same item twice
    item1 = await add_recommendation_item(session, rec.id, 550, 1, "safe", "Test")
    item2 = await add_recommendation_item(session, rec.id, 550, 1, "safe", "Test")

    # Should be the same record (same ID) - this is the key test for duplicate prevention
    assert item1.id == item2.id
    assert item1.recommendation_id == item2.recommendation_id
    assert item1.tmdb_id == item2.tmdb_id
    assert item1.position == item2.position

    # Verify only one record exists in database
    count = (await session.execute(
        select(func.count()).select_from(AgentRecommendationItem).where(
            AgentRecommendationItem.recommendation_id == rec.id,
        )
    )).scalar_one()

    assert count == 1, f"Expected 1 item in database, got {count}"
