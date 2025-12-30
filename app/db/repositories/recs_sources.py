from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import WatchedFilm, AgentRecommendation, AgentRecommendationItem


async def get_top_rated_tmdb_ids(
    session: AsyncSession,
    user_id: int,
    min_rating: float = 4.0,
    limit: int = 50,
) -> list[int]:
    stmt = (
        select(WatchedFilm.tmdb_id)
        .where(WatchedFilm.user_id == user_id)
        .where(WatchedFilm.your_rating.is_not(None))
        .where(WatchedFilm.your_rating >= min_rating)
        .order_by(WatchedFilm.your_rating.desc(), WatchedFilm.watched_date.desc().nullslast(), WatchedFilm.id.desc())
        .limit(limit)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [int(x) for x in rows]


async def get_fallback_top_tmdb_ids(session: AsyncSession, user_id: int, limit: int = 50) -> list[int]:

    stmt = (
        select(WatchedFilm.tmdb_id)
        .where(WatchedFilm.user_id == user_id)
        .order_by(WatchedFilm.your_rating.desc().nullslast(), WatchedFilm.watched_date.desc().nullslast(), WatchedFilm.id.desc())
        .limit(limit)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [int(x) for x in rows]


async def get_watched_tmdb_ids(session: AsyncSession, user_id: int) -> set[int]:
    stmt = select(func.distinct(WatchedFilm.tmdb_id)).where(WatchedFilm.user_id == user_id)
    rows = (await session.execute(stmt)).scalars().all()
    return {int(x) for x in rows}


async def get_recent_recommended_tmdb_ids(session: AsyncSession, user_id: int, days: int = 60) -> set[int]:
    since = datetime.now(timezone.utc) - timedelta(days=days)

    stmt = (
        select(func.distinct(AgentRecommendationItem.tmdb_id))
        .join(AgentRecommendation, AgentRecommendation.id == AgentRecommendationItem.recommendation_id)
        .where(AgentRecommendation.user_id == user_id)
        .where(AgentRecommendation.created_at >= since)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return {int(x) for x in rows}
