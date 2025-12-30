from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import EmbeddingJob, TextEmbedding


async def enqueue_embedding_job(
    session: AsyncSession,
    user_id: int,
    source_type: str,
    source_id: int,
    content_text: str,
    model: str,
    dimensions: int,
) -> None:
    """
    Upsert: если job уже есть для (user_id, source_type, source_id) — обновим текст и вернём в pending.
    """
    stmt = insert(EmbeddingJob).values(
        user_id=user_id,
        source_type=source_type,
        source_id=source_id,
        content_text=content_text,
        model=model,
        dimensions=dimensions,
        status="pending",
        attempts=0,
        last_error=None,
        locked_at=None,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[EmbeddingJob.user_id, EmbeddingJob.source_type, EmbeddingJob.source_id],
        set_={
            "content_text": content_text,
            "model": model,
            "dimensions": dimensions,
            "status": "pending",
            "attempts": 0,
            "last_error": None,
            "locked_at": None,
        },
    )
    await session.execute(stmt)
    await session.commit()


async def upsert_text_embedding(
    session: AsyncSession,
    user_id: int,
    source_type: str,
    source_id: int,
    content_text: str,
    embedding: list[float],
) -> None:
    stmt = insert(TextEmbedding).values(
        user_id=user_id,
        source_type=source_type,
        source_id=source_id,
        content_text=content_text,
        embedding=embedding,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[TextEmbedding.user_id, TextEmbedding.source_type, TextEmbedding.source_id],
        set_={
            "content_text": content_text,
            "embedding": embedding,
        },
    )
    await session.execute(stmt)
    await session.commit()


async def get_pending_jobs(session: AsyncSession, batch_size: int = 10) -> list[EmbeddingJob]:
    """
    Берём пачку pending job'ов и лочим их (SKIP LOCKED).
    """
    stmt = (
        select(EmbeddingJob)
        .where(EmbeddingJob.status == "pending")
        .with_for_update(skip_locked=True)
        .limit(batch_size)
    )
    jobs = (await session.execute(stmt)).scalars().all()
    return list(jobs)


async def mark_jobs_processing(session: AsyncSession, jobs: list[EmbeddingJob]) -> None:
    for j in jobs:
        j.status = "processing"
        j.attempts = int(j.attempts or 0) + 1
    await session.commit()


async def mark_job_done(session: AsyncSession, job: EmbeddingJob) -> None:
    job.status = "done"
    job.last_error = None
    await session.commit()


async def mark_job_failed(session: AsyncSession, job: EmbeddingJob, err: str) -> None:
    job.status = "failed"
    job.last_error = err[:4000]
    await session.commit()
