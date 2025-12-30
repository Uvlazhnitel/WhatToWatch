from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.recommendations import set_item_status, upsert_feedback
from app.db.repositories.watched import upsert_watched
from app.integrations.tmdb import get_movie_details
from app.recommender.taste_profile_v0 import update_taste_profile_v0


def _today_in_tz(tz: str) -> datetime.date:
    try:
        return datetime.now(ZoneInfo(tz)).date()
    except Exception:
        return datetime.utcnow().date()


async def save_review(
    session: AsyncSession,
    *,
    user_id: int,
    user_timezone: str,
    tmdb_id: int,
    rating: float | None,
    review_text: str | None,
    mode: str,  # "agent" | "manual"
    recommendation_item_id: int | None = None,
) -> int:
    """
    Возвращает watched_film_id.
    Делает все нужные записи + пересчет профиля вкуса.
    """
    details = await get_movie_details(session, tmdb_id)
    watched_date = _today_in_tz(user_timezone)

    if mode == "agent" and recommendation_item_id is not None:
        await upsert_feedback(session, recommendation_item_id=recommendation_item_id, rating=rating, review=review_text)
        await set_item_status(session, recommendation_item_id, "watched")
        source = "agent"
    else:
        source = "manual"

    watched_id = await upsert_watched(
        session=session,
        user_id=user_id,
        tmdb_id=tmdb_id,
        title=details.title,
        year=details.year,
        rating=rating,
        review=review_text,
        watched_date=watched_date,
        source=source,
    )

    await update_taste_profile_v0(session=session, user_id=user_id)
    return watched_id
