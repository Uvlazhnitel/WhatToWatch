from __future__ import annotations

from app.db.repositories.feedback_repo import get_feedback_count
from app.db.repositories.taste_profile import get_taste_profile, upsert_taste_profile
from app.llm.text_tasks import rewrite_profile_summary


async def maybe_refresh_summary_text(session, user_id: int, every_n: int = 10) -> None:
    count = await get_feedback_count(session, user_id)
    if count <= 0 or (count % every_n) != 0:
        return

    profile = await get_taste_profile(session, user_id)
    if profile is None:
        return

    payload = {"weights_json": profile.weights_json, "current_summary": profile.summary_text}
    try:
        out = rewrite_profile_summary(payload)
    except Exception:
        return

    # обновляем только summary_text, веса остаются прежние
    await upsert_taste_profile(
        session=session,
        user_id=user_id,
        summary_text=out.summary_text.strip(),
        weights_json=profile.weights_json,
        avoids_json=profile.avoids_json or {},
    )
