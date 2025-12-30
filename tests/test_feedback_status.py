from __future__ import annotations

import pytest
from sqlalchemy import select

from app.db.repositories.users import get_or_create_user
from app.db.models import AgentRecommendation, AgentRecommendationItem, Feedback
from app.services.review_service import save_review


@pytest.mark.asyncio
async def test_feedback_sets_status_watched(session):
    user = await get_or_create_user(session, telegram_id=4444)
    user.timezone = "Europe/Stockholm"
    await session.commit()

    rec = AgentRecommendation(user_id=user.id, context_json={"mode": "test"})
    session.add(rec)
    await session.commit()
    await session.refresh(rec)

    item = AgentRecommendationItem(
        recommendation_id=rec.id,
        tmdb_id=348,
        position=1,
        strategy="safe",
        status="suggested",
        explanation_shown=None,
    )
    session.add(item)
    await session.commit()
    await session.refresh(item)

    await save_review(
        session,
        user_id=user.id,
        user_timezone=user.timezone,
        tmdb_id=item.tmdb_id,
        rating=4.5,
        review_text="топ",
        mode="agent",
        recommendation_item_id=item.id,
    )

    updated_item = (await session.execute(select(AgentRecommendationItem).where(AgentRecommendationItem.id == item.id))).scalar_one()
    assert updated_item.status == "watched"

    fb = (await session.execute(select(Feedback).where(Feedback.recommendation_item_id == item.id))).scalar_one()
    assert fb.your_rating == 4.5
    assert fb.your_review == "топ"
