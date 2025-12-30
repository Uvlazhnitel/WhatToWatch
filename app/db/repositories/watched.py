from __future__ import annotations

from datetime import date
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import WatchedFilm


async def watched_exists(session: AsyncSession, user_id: int, tmdb_id: int, watched_date: date | None) -> bool:
    stmt = select(WatchedFilm.id).where(
        WatchedFilm.user_id == user_id,
        WatchedFilm.tmdb_id == tmdb_id,
    )
    if watched_date is None:
        stmt = stmt.where(WatchedFilm.watched_date.is_(None))
    else:
        stmt = stmt.where(WatchedFilm.watched_date == watched_date)

    return (await session.execute(stmt)).scalar_one_or_none() is not None


async def insert_watched(
    session: AsyncSession,
    user_id: int,
    tmdb_id: int,
    title: str,
    year: int | None,
    rating: float | None,
    review: str | None,
    watched_date: date | None,
    source: str,
) -> None:
    if await watched_exists(session, user_id, tmdb_id, watched_date):
        return

    wf = WatchedFilm(
        user_id=user_id,
        tmdb_id=tmdb_id,
        title=title,
        year=year,
        your_rating=rating,
        your_review=review,
        watched_date=watched_date,
        source=source,
    )
    session.add(wf)
    await session.commit()
