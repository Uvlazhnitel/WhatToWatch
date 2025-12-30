from __future__ import annotations

import pytest

from app.db.models import User, WatchedFilm
from app.db.repositories.users import get_or_create_user
from app.recommender.v0 import recommend_v0


@pytest.mark.asyncio
async def test_do_not_recommend_watched(session):
    user = await get_or_create_user(session, telegram_id=1111)

    # добавим просмотренный фильм
    wf = WatchedFilm(
        user_id=user.id,
        tmdb_id=999,
        title="Watched",
        year=2000,
        your_rating=4.5,
        your_review=None,
        watched_date=None,
        source="letterboxd",
    )
    session.add(wf)
    await session.commit()

    picks = await recommend_v0(session=session, user_id=user.id, count=3, recent_days=60, seeds_limit=20)

    # ключевой инвариант: tmdb_id=999 не должен появиться
    assert all(p.tmdb_id != 999 for p in picks)
