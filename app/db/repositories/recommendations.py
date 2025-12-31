from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AgentRecommendation, AgentRecommendationItem, Feedback


async def create_recommendation(session: AsyncSession, user_id: int, context: dict) -> AgentRecommendation:
    rec = AgentRecommendation(user_id=user_id, context_json=context)
    session.add(rec)
    await session.commit()
    await session.refresh(rec)
    return rec


async def add_recommendation_item(
    session: AsyncSession,
    recommendation_id: int,
    tmdb_id: int,
    position: int,
    strategy: str,
    explanation_shown: str | None = None,
) -> AgentRecommendationItem:
    """
    Add a recommendation item, handling duplicate inserts gracefully.
    
    Uses upsert logic to prevent duplicates when the same recommendation
    is processed concurrently. The unique constraint on 
    (recommendation_id, tmdb_id, position) prevents duplicate entries.
    """
    # Try to insert, but if conflict occurs (duplicate), do nothing and return existing
    stmt = insert(AgentRecommendationItem).values(
        recommendation_id=recommendation_id,
        tmdb_id=tmdb_id,
        position=position,
        strategy=strategy,
        status="suggested",
        explanation_shown=explanation_shown,
    ).on_conflict_do_nothing(
        index_elements=['recommendation_id', 'tmdb_id', 'position']
    ).returning(AgentRecommendationItem.id)
    
    result = await session.execute(stmt)
    row = result.fetchone()
    
    # If insert succeeded, get the ID
    if row is not None:
        item_id = row[0]
    else:
        # Conflict occurred, fetch the existing item
        existing = (await session.execute(
            select(AgentRecommendationItem).where(
                AgentRecommendationItem.recommendation_id == recommendation_id,
                AgentRecommendationItem.tmdb_id == tmdb_id,
                AgentRecommendationItem.position == position,
            )
        )).scalar_one()
        item_id = existing.id
    
    # Commit once at the end
    await session.commit()
    
    # Fetch and return the complete item
    item = (await session.execute(
        select(AgentRecommendationItem).where(AgentRecommendationItem.id == item_id)
    )).scalar_one()
    
    return item


async def set_item_status(session: AsyncSession, item_id: int, status: str) -> None:
    item = (await session.execute(select(AgentRecommendationItem).where(AgentRecommendationItem.id == item_id))).scalar_one_or_none()
    if item is None:
        return
    item.status = status
    await session.commit()


async def upsert_feedback(session: AsyncSession, recommendation_item_id: int, rating: float | None, review: str | None) -> None:
    stmt = insert(Feedback).values(
        recommendation_item_id=recommendation_item_id,
        your_rating=rating,
        your_review=review,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[Feedback.recommendation_item_id],
        set_={"your_rating": rating, "your_review": review},
    )
    await session.execute(stmt)
    await session.commit()
