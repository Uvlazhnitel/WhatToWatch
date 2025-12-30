from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import select, func
from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.db.models import User, WatchedFilm
from app.db.repositories.embeddings import enqueue_embedding_job
from app.recommender.embedding_texts import build_film_meta_text, build_review_text
from app.db.repositories.taste_profile import get_taste_profile


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--telegram-id", required=True, type=int)
    p.add_argument("--limit", type=int, default=500)
    return p.parse_args()


async def main():
    args = parse_args()

    async with AsyncSessionLocal() as session:
        user = (await session.execute(select(User).where(User.telegram_id == args.telegram_id))).scalar_one()

        rows = (await session.execute(
            select(WatchedFilm).where(WatchedFilm.user_id == user.id).order_by(WatchedFilm.id.desc()).limit(args.limit)
        )).scalars().all()

        count_jobs = 0

        for wf in rows:
            # film_meta (tmdb_id)
            meta_text = await build_film_meta_text(session, int(wf.tmdb_id))
            if meta_text.strip():
                await enqueue_embedding_job(
                    session, user.id, "film_meta", int(wf.tmdb_id), meta_text,
                    settings.openai_embed_model, settings.openai_embed_dimensions
                )
                count_jobs += 1

            # review (если есть rating или review)
            if wf.your_rating is not None or (wf.your_review and wf.your_review.strip()):
                review_text = await build_review_text(wf.title, wf.year, float(wf.your_rating) if wf.your_rating is not None else None, wf.your_review)
                if review_text.strip():
                    await enqueue_embedding_job(
                        session, user.id, "review", int(wf.id), review_text,
                        settings.openai_embed_model, settings.openai_embed_dimensions
                    )
                    count_jobs += 1

        profile = await get_taste_profile(session, user.id)
        if profile and profile.summary_text and profile.summary_text.strip():
            await enqueue_embedding_job(
                session, user.id, "profile", user.id, profile.summary_text.strip(),
                settings.openai_embed_model, settings.openai_embed_dimensions
            )
            count_jobs += 1

        print(f"✅ Enqueued jobs: {count_jobs}")


if __name__ == "__main__":
    asyncio.run(main())
