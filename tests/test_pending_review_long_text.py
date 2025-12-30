from __future__ import annotations

import pytest

from app.db.repositories.users import get_or_create_user
from app.db.models import WatchedFilm
from sqlalchemy import select

from app.services.review_service import save_review


@pytest.mark.asyncio
async def test_long_review_saved(session):
    user = await get_or_create_user(session, telegram_id=3333)
    user.timezone = "Europe/Stockholm"
    await session.commit()

    long_text = "очень_длинная_рецензия " * 2000  # ~40k символов
    tmdb_id = 348  # любой id (для тестов лучше замокать TMDB, но минимум — так)

    # ВНИМАНИЕ:
    # Этот тест будет ходить в TMDB (get_movie_details).
    # Для полного оффлайна лучше замокать TMDB (ниже покажу как).
    watched_id = await save_review(
        session,
        user_id=user.id,
        user_timezone=user.timezone,
        tmdb_id=tmdb_id,
        rating=4.0,
        review_text=long_text,
        mode="manual",
    )

    row = (await session.execute(select(WatchedFilm).where(WatchedFilm.id == watched_id))).scalar_one()
    assert row.your_review is not None
    assert len(row.your_review) == len(long_text)
