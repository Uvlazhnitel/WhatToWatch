from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.db.models import User, WatchedFilm, TextEmbedding
from app.integrations.tmdb import get_movie_details
from pgvector.sqlalchemy import avg


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--telegram-id", required=True, type=int)
    p.add_argument("--limit", type=int, default=10)
    return p.parse_args()


async def main():
    args = parse_args()

    async with AsyncSessionLocal() as session:
        user = (await session.execute(select(User).where(User.telegram_id == args.telegram_id))).scalar_one()

        # 1) берём один из любимых (rating>=4) и его film_meta embedding
        fav_tmdb_id = (await session.execute(
            select(WatchedFilm.tmdb_id)
            .where(WatchedFilm.user_id == user.id)
            .where(WatchedFilm.your_rating >= 4.0)
            .order_by(WatchedFilm.your_rating.desc(), WatchedFilm.id.desc())
            .limit(1)
        )).scalar_one_or_none()

        if fav_tmdb_id is None:
            print("No favorite films (rating>=4) found.")
            return

        fav_tmdb_id = int(fav_tmdb_id)

        fav_emb = (await session.execute(
            select(TextEmbedding)
            .where(TextEmbedding.user_id == user.id)
            .where(TextEmbedding.source_type == "film_meta")
            .where(TextEmbedding.source_id == fav_tmdb_id)
        )).scalar_one_or_none()

        if fav_emb is None:
            print("No film_meta embedding for favorite yet. Run backfill + worker first.")
            return

        q = fav_emb.embedding  # list[float]

        # 2) ищем похожие film_meta (исключая сам фильм)
        dist = TextEmbedding.embedding.cosine_distance(q)
        rows = (await session.execute(
            select(TextEmbedding.source_id, dist.label("dist"))
            .where(TextEmbedding.user_id == user.id)
            .where(TextEmbedding.source_type == "film_meta")
            .where(TextEmbedding.source_id != fav_tmdb_id)
            .order_by(dist)
            .limit(args.limit)
        )).all()

        fav_details = await get_movie_details(session, fav_tmdb_id)
        print(f"\nFavorite: {fav_details.title} ({fav_details.year})\n")

        for tmdb_id, d in rows:
            details = await get_movie_details(session, int(tmdb_id))
            similarity = 1.0 - float(d)  # cosine distance -> similarity
            print(f"{similarity:.3f}  {details.title} ({details.year})")


if __name__ == "__main__":
    asyncio.run(main())
