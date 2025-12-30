from __future__ import annotations

from datetime import date
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import WatchedFilm


async def get_existing_watched(
    session: AsyncSession,
    user_id: int,
    tmdb_id: int,
    watched_date: date | None,
) -> WatchedFilm | None:
    stmt = select(WatchedFilm).where(
        WatchedFilm.user_id == user_id,
        WatchedFilm.tmdb_id == tmdb_id,
    )
    if watched_date is None:
        stmt = stmt.where(WatchedFilm.watched_date.is_(None))
    else:
        stmt = stmt.where(WatchedFilm.watched_date == watched_date)

    return (await session.execute(stmt)).scalar_one_or_none()


async def upsert_watched(
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

    existing = await get_existing_watched(session, user_id, tmdb_id, watched_date)

    if existing is None:
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
        return

    existing.title = title or existing.title
    existing.year = year if year is not None else existing.year

    if rating is not None:
        existing.your_rating = rating
    if review is not None and str(review).strip():
        existing.your_review = review

    existing.source = source

    await session.commit()
