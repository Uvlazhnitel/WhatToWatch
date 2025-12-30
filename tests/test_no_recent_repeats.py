from __future__ import annotations

import pytest
from datetime import datetime, timedelta, timezone

from app.db.repositories.users import get_or_create_user
from app.db.models import AgentRecommendation, AgentRecommendationItem, WatchedFilm
from app.recommender.v0 import recommend_v0


@pytest.mark.asyncio
async def test_do_not_recommend_recently_suggested(session):
    user = await get_or_create_user(session, telegram_id=2222)

    # Seed (чтобы v0 вообще работал)
    session.add(WatchedFilm(
        user_id=user.id, tmdb_id=101, title="Seed", year=1999,
        your_rating=4.5, your_review=None, watched_date=None, source="letterboxd"
    ))
    await session.commit()

    # Создаем рекомендацию 10 дней назад с item tmdb_id=555
    rec = AgentRecommendation(user_id=user.id, context_json={"mode": "test"})
    rec.created_at = datetime.now(timezone.utc) - timedelta(days=10)
    session.add(rec)
    await session.commit()
    await session.refresh(rec)

    item = AgentRecommendationItem(
        recommendation_id=rec.id,
        tmdb_id=555,
        position=1,
        strategy="safe",
        status="suggested",
        explanation_shown=None,
    )
    session.add(item)
    await session.commit()

    picks = await recommend_v0(session=session, user_id=user.id, count=5, recent_days=60, seeds_limit=20)
    assert all(p.tmdb_id != 555 for p in picks)
