from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import TasteProfile


async def get_taste_profile(session: AsyncSession, user_id: int) -> TasteProfile | None:
    return (await session.execute(select(TasteProfile).where(TasteProfile.user_id == user_id))).scalar_one_or_none()


async def upsert_taste_profile(
    session: AsyncSession,
    user_id: int,
    summary_text: str,
    weights_json: dict,
    avoids_json: dict | None = None,
) -> None:
    profile = await get_taste_profile(session, user_id)
    now = datetime.now(timezone.utc)

    if profile is None:
        profile = TasteProfile(
            user_id=user_id,
            summary_text=summary_text,
            weights_json=weights_json,
            avoids_json=avoids_json or {},
            updated_at=now,
        )
        session.add(profile)
        await session.commit()
        return

    profile.summary_text = summary_text
    profile.weights_json = weights_json
    if avoids_json is not None:
        profile.avoids_json = avoids_json
    profile.updated_at = now
    await session.commit()
