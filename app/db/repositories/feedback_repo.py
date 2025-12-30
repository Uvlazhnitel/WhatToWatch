from __future__ import annotations

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Feedback, AgentRecommendationItem, AgentRecommendation


async def get_feedback_count(session: AsyncSession, user_id: int) -> int:
    """
    Feedback привязан к recommendation_item, а user_id лежит в agent_recommendations.
    Поэтому считаем через join.
    """
    n = (await session.execute(
        select(func.count())
        .select_from(Feedback)
        .join(AgentRecommendationItem, Feedback.recommendation_item_id == AgentRecommendationItem.id)
        .join(AgentRecommendation, AgentRecommendationItem.recommendation_id == AgentRecommendation.id)
        .where(AgentRecommendation.user_id == user_id)
    )).scalar_one()
    return int(n)
