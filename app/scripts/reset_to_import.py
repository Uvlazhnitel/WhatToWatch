"""
Reset User Data Script

Resets a user's data to the state immediately after Letterboxd import, removing all
bot-generated or manually-added data while preserving imported Letterboxd history.

This script removes:
- Agent recommendations and their items
- User feedback on recommendations
- Watched films from "agent" or "manual" sources
- Pending actions
- Current taste profile (will be rebuilt from Letterboxd data only)

The taste profile is then regenerated based solely on Letterboxd data.

Usage:
    python -m app.scripts.reset_to_import \\
        --telegram-id YOUR_TELEGRAM_ID \\
        --dry-run  # Optional: preview changes without applying them

WARNING: This is a destructive operation. Use --dry-run first to verify what will be deleted.
"""

from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.db.models import (
    User,
    WatchedFilm,
    AgentRecommendation,
    AgentRecommendationItem,
    Feedback,
    PendingAction,
    TasteProfile,
)
from app.recommender.taste_profile_v0 import update_taste_profile_v0


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Reset user data to 'after Letterboxd import' state.")
    p.add_argument("--telegram-id", required=True, type=int, help="Your Telegram numeric id")
    p.add_argument("--dry-run", action="store_true", help="Only show what would be deleted")
    return p.parse_args()


async def get_user(session: AsyncSession, telegram_id: int) -> User:
    user = (await session.execute(select(User).where(User.telegram_id == telegram_id))).scalar_one_or_none()
    if not user:
        raise SystemExit(f"User with telegram_id={telegram_id} not found")
    return user


async def main() -> None:
    args = parse_args()

    async with AsyncSessionLocal() as session:
        user = await get_user(session, args.telegram_id)

        # ---- Count what will be affected
        # Recommendations
        rec_ids = (await session.execute(
            select(AgentRecommendation.id).where(AgentRecommendation.user_id == user.id)
        )).scalars().all()
        rec_ids = [int(x) for x in rec_ids]

        items_count = 0
        feedback_count = 0
        if rec_ids:
            item_ids = (await session.execute(
                select(AgentRecommendationItem.id).where(AgentRecommendationItem.recommendation_id.in_(rec_ids))
            )).scalars().all()
            item_ids = [int(x) for x in item_ids]
            items_count = len(item_ids)

            if item_ids:
                feedback_count = (await session.execute(
                    select(Feedback.id).where(Feedback.recommendation_item_id.in_(item_ids))
                )).scalars().all()
                feedback_count = len(feedback_count)

        # Watched to delete (agent/manual)
        watched_to_delete = (await session.execute(
            select(WatchedFilm.id).where(
                WatchedFilm.user_id == user.id,
                WatchedFilm.source.in_(("agent", "manual")),
            )
        )).scalars().all()
        watched_del_count = len(watched_to_delete)

        pending_exists = (await session.execute(
            select(PendingAction.user_id).where(PendingAction.user_id == user.id)
        )).scalar_one_or_none() is not None

        profile_exists = (await session.execute(
            select(TasteProfile.user_id).where(TasteProfile.user_id == user.id)
        )).scalar_one_or_none() is not None

        print("=== RESET PLAN ===")
        print(f"User id: {user.id}")
        print(f"Agent recommendations: {len(rec_ids)}")
        print(f"Recommendation items: {items_count}")
        print(f"Feedback rows: {feedback_count}")
        print(f"Watched rows to delete (source=agent/manual): {watched_del_count}")
        print(f"Pending action exists: {pending_exists}")
        print(f"Taste profile exists: {profile_exists}")

        if args.dry_run:
            print("\nDry-run only. No changes made.")
            return

        # ---- Delete in FK-safe order:
        # feedback -> items -> recommendations
        if rec_ids:
            # delete feedback by join via items
            item_ids = (await session.execute(
                select(AgentRecommendationItem.id).where(AgentRecommendationItem.recommendation_id.in_(rec_ids))
            )).scalars().all()
            item_ids = [int(x) for x in item_ids]

            if item_ids:
                await session.execute(delete(Feedback).where(Feedback.recommendation_item_id.in_(item_ids)))
                await session.execute(delete(AgentRecommendationItem).where(AgentRecommendationItem.id.in_(item_ids)))

            await session.execute(delete(AgentRecommendation).where(AgentRecommendation.id.in_(rec_ids)))

        # delete pending actions
        await session.execute(delete(PendingAction).where(PendingAction.user_id == user.id))

        # delete taste profile (we will rebuild)
        await session.execute(delete(TasteProfile).where(TasteProfile.user_id == user.id))

        # delete watched films created by bot/manual
        await session.execute(
            delete(WatchedFilm).where(
                WatchedFilm.user_id == user.id,
                WatchedFilm.source.in_(("agent", "manual")),
            )
        )

        await session.commit()

        # Recompute taste profile ONLY from letterboxd
        await update_taste_profile_v0(session=session, user_id=user.id, sources=("letterboxd",))
        print("\n✅ Reset done. Taste profile rebuilt from Letterboxd only.")


if __name__ == "__main__":
    asyncio.run(main())
