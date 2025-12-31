from __future__ import annotations

import argparse
import asyncio
from sqlalchemy import select

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.db.models import User
from app.db.repositories.recs_sources import get_top_rated_tmdb_ids, get_watched_tmdb_ids
from app.integrations.tmdb import get_similar, get_recommendations
from app.recommender.embedding_texts import build_film_meta_text
from app.db.repositories.embeddings import enqueue_embedding_job


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--telegram-id", required=True, type=int)
    p.add_argument("--seeds", type=int, default=35)
    p.add_argument("--limit", type=int, default=1500)
    return p.parse_args()


async def main():
    args = parse_args()

    async with AsyncSessionLocal() as session:
        user = (await session.execute(select(User).where(User.telegram_id == args.telegram_id))).scalar_one()

        seeds = await get_top_rated_tmdb_ids(session, user.id, min_rating=4.0, limit=args.seeds)
        watched = await get_watched_tmdb_ids(session, user.id)

        pool: dict[int, float] = {}  # tmdb_id -> quality heuristic
        for s in seeds:
            sim = await get_similar(s, page=1)
            rec = await get_recommendations(s, page=1)
            for c in (sim or []) + (rec or []):
                if c.tmdb_id in watched:
                    continue
                q = float(c.vote_average or 0) + float(c.popularity or 0) / 100.0
                pool[c.tmdb_id] = max(pool.get(c.tmdb_id, 0.0), q)

        cand_ids = [tid for tid, _ in sorted(pool.items(), key=lambda kv: kv[1], reverse=True)]
        cand_ids = cand_ids[: args.limit]

        enq = 0
        for tid in cand_ids:
            text = await build_film_meta_text(session, tid)
            if not text.strip():
                continue
            await enqueue_embedding_job(
                session=session,
                user_id=user.id,
                source_type="film_meta",
                source_id=tid,
                content_text=text,
                model=settings.openai_embed_model,
                dimensions=settings.openai_embed_dimensions,
            )
            enq += 1

        print(f"✅ Enqueued film_meta jobs for candidates: {enq}")


if __name__ == "__main__":
    asyncio.run(main())
