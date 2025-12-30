from __future__ import annotations

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AgentRecommendationItem, AgentRecommendation


async def set_item_explanation(session: AsyncSession, item_id: int, explanation: str) -> None:
    await session.execute(
        update(AgentRecommendationItem)
        .where(AgentRecommendationItem.id == item_id)
        .values(explanation_shown=explanation)
    )
    await session.commit()


async def set_recommendation_questions(session: AsyncSession, recommendation_id: int, questions: list[str]) -> None:
    # кладём в context_json
    rec = await session.get(AgentRecommendation, recommendation_id)
    if rec is None:
        return
    ctx = rec.context_json or {}
    ctx["evening_questions"] = questions
    rec.context_json = ctx
    await session.commit()
