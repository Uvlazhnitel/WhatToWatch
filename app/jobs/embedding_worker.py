"""
Embedding Worker

Background worker that processes embedding generation jobs from the queue.
Fetches pending jobs in batches, calls the OpenAI embeddings API, and stores
the resulting vectors in the database.

The worker:
1. Polls the database for pending embedding jobs
2. Batches jobs together for efficient API calls
3. Generates embeddings using OpenAI's embedding model
4. Stores embeddings in PostgreSQL with pgvector
5. Handles failures with appropriate error logging

Run with:
    python -m app.jobs.embedding_worker

This should run continuously alongside the bot for optimal performance.
"""

from __future__ import annotations

import asyncio
import traceback

from app.core.config import settings
from app.db.session import AsyncSessionLocal

from app.db.repositories.embeddings import (
    get_pending_jobs,
    mark_jobs_processing,
    upsert_text_embedding,
    mark_job_done,
    mark_job_failed,
)
from app.integrations.openai_embeddings import embed_texts
from app.core.logging import setup_logging
setup_logging()



async def worker_loop(poll_seconds: float = 2.0, batch_size: int = 10) -> None:
    print("Embedding worker started")

    while True:
        async with AsyncSessionLocal() as session:
            jobs = await get_pending_jobs(session, batch_size=batch_size)
            if not jobs:
                await asyncio.sleep(poll_seconds)
                continue

            await mark_jobs_processing(session, jobs)

            # batch-call embeddings API
            try:
                texts = [j.content_text for j in jobs]
                model = jobs[0].model
                dimensions = jobs[0].dimensions

                # Важно: лучше группировать по model/dim, но для v0 достаточно так:
                vectors = await asyncio.to_thread(embed_texts, texts, model, dimensions)

                # записываем результаты
                for job, vec in zip(jobs, vectors):
                    await upsert_text_embedding(
                        session=session,
                        user_id=job.user_id,
                        source_type=job.source_type,
                        source_id=job.source_id,
                        content_text=job.content_text,
                        embedding=vec,
                    )
                    await mark_job_done(session, job)

            except Exception as e:
                err = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"
                # если пачка упала — пометим все как failed (можно улучшить позже)
                for job in jobs:
                    await mark_job_failed(session, job, err)

        await asyncio.sleep(0)  # отдаём цикл


def main() -> None:
    asyncio.run(worker_loop())


if __name__ == "__main__":
    main()
