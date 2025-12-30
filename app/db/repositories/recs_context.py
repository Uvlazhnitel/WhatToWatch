from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AgentRecommendation, AgentRecommendationItem, WatchedFilm


async def get_recent_recommended_tmdb_ids(session: AsyncSession, user_id: int, days: int = 60, limit: int = 200) -> list[int]:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    stmt = (
        select(AgentRecommendationItem.tmdb_id)
        .join(AgentRecommendation, AgentRecommendation.id == AgentRecommendationItem.recommendation_id)
        .where(AgentRecommendation.user_id == user_id)
        .where(AgentRecommendation.created_at >= since)
        .order_by(AgentRecommendation.created_at.desc(), AgentRecommendationItem.id.desc())
        .limit(limit)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [int(x) for x in rows]


async def get_recent_watched_tmdb_ids(session: AsyncSession, user_id: int, limit: int = 50) -> list[int]:
    stmt = (
        select(WatchedFilm.tmdb_id)
        .where(WatchedFilm.user_id == user_id)
        .order_by(WatchedFilm.watched_date.desc().nullslast(), WatchedFilm.id.desc())
        .limit(limit)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [int(x) for x in rows]
