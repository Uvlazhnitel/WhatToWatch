from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

from sqlalchemy import select, func

from app.bot.safe_send import safe_answer
from app.bot.keyboards import movie_pick_keyboard, rec_item_keyboard
from app.bot.parsing import parse_rating_from_text, parse_title_and_year

from app.db.session import AsyncSessionLocal, AsyncSession
from app.db.models import TasteProfile, WatchedFilm, TextEmbedding

from app.db.repositories.users import get_or_create_user
from app.db.repositories.recommendations import (
    create_recommendation,
    add_recommendation_item,
    set_item_status,
    upsert_feedback,
)
from app.db.repositories.pending import set_pending, get_pending, clear_pending
from app.db.repositories.rate_limit import check_and_touch
from app.db.repositories.taste_profile import set_avoids_json

from app.integrations.tmdb import (
    search_movie,
    get_movie_details,
    get_movie_keywords,
    TMDBError,
)

logger = logging.getLogger(__name__)
router = Router()


# -----------------------------
# Helpers
# -----------------------------

def today_in_tz(tz_name: str) -> datetime.date:
    try:
        return datetime.now(ZoneInfo(tz_name)).date()
    except Exception:
        return datetime.utcnow().date()


def label_for_strategy(strategy: str) -> str:
    return {
        "safe": "🎯 Попадание",
        "adjacent": "🧭 Рядом, но иначе",
        "wildcard": "🎲 Эксперимент",
    }.get(strategy, strategy)


# -----------------------------
# /start /cancel /myid
# -----------------------------

@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    if message.from_user is None:
        return

    async with AsyncSessionLocal() as session:
        user = await get_or_create_user(session, telegram_id=message.from_user.id)
        await clear_pending(session, user.id)

    await message.answer(
        "Привет! Я кино-агент.\n\n"
        "Команды:\n"
        "/review — написать отзыв на фильм (выбор через TMDB)\n"
        "/recommend — получить рекомендации (v1 если есть эмбеддинги, иначе v0)\n"
        "/avoid <тема> — мягко избегать темы\n"
        "/cancel — отменить текущий ввод\n"
        "/myid — показать telegram id\n\n"
        "Можно писать длинные рецензии — сколько хочешь."
    )


@router.message(Command("cancel"))
async def cmd_cancel(message: Message) -> None:
    if message.from_user is None:
        return

    async with AsyncSessionLocal() as session:
        user = await get_or_create_user(session, telegram_id=message.from_user.id)
        await clear_pending(session, user.id)

    await message.answer("Ок, отменил ✅")


@router.message(Command("myid"))
async def cmd_myid(message: Message) -> None:
    if message.from_user is None:
        return
    await message.answer(f"Твой telegram id: {message.from_user.id}")


# -----------------------------
# Manual review flow (/review)
# -----------------------------

@router.message(Command("review"))
async def cmd_review(message: Message) -> None:
    if message.from_user is None:
        return

    async with AsyncSessionLocal() as session:
        user = await get_or_create_user(session, telegram_id=message.from_user.id)
        await set_pending(session, user.id, "awaiting_movie_query", {"mode": "manual"})

    await message.answer(
        "Напиши название фильма (можно с годом).\n"
        "Примеры:\n"
        "• Alien 1979\n"
        "• Alien (1979)\n"
        "• Alien"
    )


@router.callback_query(F.data.startswith("pick:"))
async def cb_pick_movie(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.data is None:
        return

    tmdb_id = int(callback.data.split(":")[1])

    async with AsyncSessionLocal() as session:
        user = await get_or_create_user(session, telegram_id=callback.from_user.id)
        await set_pending(session, user.id, "awaiting_review", {"mode": "manual", "tmdb_id": tmdb_id})
        details = await get_movie_details(session, tmdb_id)

    if callback.message:
        await callback.message.answer(
            f"Ок: {details.title} ({details.year}).\n\n"
            "Теперь оцени 0–5 и напиши мысли (можно длинно).\n"
            "Форматы:\n"
            "• 4.5/5 тут текст...\n"
            "• 4 тут текст...\n"
            "• или просто текст — я потом уточню оценку"
        )
    await callback.answer()


# -----------------------------
# Recommend flow (/recommend)
# -----------------------------

@router.message(Command("recommend"))
async def cmd_recommend(message: Message) -> None:
    if message.from_user is None:
        return

    async with AsyncSessionLocal() as session:
        user = await get_or_create_user(session, telegram_id=message.from_user.id)

        # rate limit: не чаще 1 раза в минуту
        allowed, retry = await check_and_touch(session, user.id, "recommend", interval_seconds=60)
        if not allowed:
            await message.answer(f"Чуть-чуть подожди 🙂 Можно снова через {retry} сек.")
            return

        # --- Try v1 first ---
        try:
            from app.recommender.v1 import recommend_v1
            picks_v1 = await recommend_v1(
                session=session,
                user_id=user.id,
                count=3,
                recent_days=60,
                seeds_limit=40,
            )
        except Exception:
            logger.exception("recommend_v1 crashed (user_id=%s)", user.id)
            picks_v1 = []

        # ВАЖНО: возвращаем поведение "как раньше" по меткам:
        # 1) safe  2) adjacent  3) wildcard
        slot_plan = ["safe", "adjacent", "wildcard"]

        if picks_v1:
            # LLM слой (опционально): вопросы + объяснения
            try:
                from app.llm.text_tasks import generate_explanations, generate_evening_questions
                from app.llm.policy import should_ask_questions
                from app.db.repositories.recommendations_updates import set_item_explanation, set_recommendation_questions
            except Exception:
                generate_explanations = None
                generate_evening_questions = None
                should_ask_questions = None
                set_item_explanation = None
                set_recommendation_questions = None

            profile = (
                await session.execute(select(TasteProfile).where(TasteProfile.user_id == user.id))
            ).scalar_one_or_none()
            taste_summary = (profile.summary_text if profile and profile.summary_text else "").strip()

            # детерминированные метрики для policy
            rated_count = (
                await session.execute(
                    select(func.count()).select_from(WatchedFilm)
                    .where(WatchedFilm.user_id == user.id)
                    .where(WatchedFilm.your_rating.is_not(None))
                )
            ).scalar_one()

            cand_ids = [p.tmdb_id for p in picks_v1]
            have_vec = (
                await session.execute(
                    select(func.count()).select_from(TextEmbedding)
                    .where(TextEmbedding.user_id == user.id)
                    .where(TextEmbedding.source_type == "film_meta")
                    .where(TextEmbedding.source_id.in_(cand_ids))
                )
            ).scalar_one()
            coverage = float(have_vec) / max(1, len(cand_ids))

            # если ты хранишь sim_like в pick — сюда ставь реальное.
            avg_sim_like = 0.22

            ask = False
            signal = ""
            if should_ask_questions:
                try:
                    ask, signal = should_ask_questions(
                        rated_films_count=int(rated_count),
                        embeddings_coverage_ratio=float(coverage),
                        avg_sim_like=float(avg_sim_like),
                    )
                except Exception:
                    ask, signal = False, ""

            rec = await create_recommendation(
                session,
                user.id,
                context={"mode": "v1", "count": len(picks_v1), "recent_days": 60, "llm_text": bool(generate_explanations)},
            )

            item_id_by_tmdb: dict[int, int] = {}
            llm_items_payload: list[dict] = []

            # создаём items (strategy = slot_strategy) и собираем payload для LLM
            for pos, p in enumerate(picks_v1, start=1):
                slot_strategy = slot_plan[pos - 1] if pos - 1 < len(slot_plan) else p.strategy

                item = await add_recommendation_item(
                    session=session,
                    recommendation_id=rec.id,
                    tmdb_id=p.tmdb_id,
                    position=pos,
                    strategy=slot_strategy,   # <- ключевой фикс "как раньше"
                    explanation_shown=None,
                )
                item_id_by_tmdb[p.tmdb_id] = int(item.id)

                try:
                    details = await get_movie_details(session, p.tmdb_id)
                    keywords = await get_movie_keywords(session, p.tmdb_id)
                except TMDBError:
                    logger.exception("TMDB failed for tmdb_id=%s", p.tmdb_id)
                    continue

                llm_items_payload.append({
                    "tmdb_id": p.tmdb_id,
                    "title": details.title,
                    "year": details.year,
                    "genres": details.genres or [],
                    "keywords": (keywords or [])[:10],
                    "strategy": slot_strategy,
                    "score": float(p.score),
                })

            # вопросы (опционально)
            if ask and generate_evening_questions and set_recommendation_questions:
                try:
                    qout = generate_evening_questions({"taste_summary": taste_summary, "signal": signal})
                    if qout.questions:
                        await set_recommendation_questions(session, rec.id, qout.questions)
                        await message.answer(
                            "Пара коротких вопросов, чтобы точнее попасть сегодня:\n- " +
                            "\n- ".join(qout.questions)
                        )
                except Exception:
                    logger.exception("LLM questions failed")

            # объяснения (один LLM-вызов)
            explanations_map: dict[int, str] = {}
            if generate_explanations:
                try:
                    out = generate_explanations({"taste_summary": taste_summary, "items": llm_items_payload})
                    for it in out.items:
                        explanations_map[int(it.tmdb_id)] = it.explanation.strip()
                except Exception:
                    logger.exception("LLM explanations failed")

            await message.answer("Вот рекомендации на вечер 👇")

            for i, p in enumerate(picks_v1, start=1):
                tmdb_id = p.tmdb_id
                item_id = item_id_by_tmdb.get(tmdb_id)

                # если item по какой-то причине не создался — пропустим
                if item_id is None:
                    continue

                slot_strategy = slot_plan[i - 1] if i - 1 < len(slot_plan) else p.strategy
                label = label_for_strategy(slot_strategy)

                try:
                    details = await get_movie_details(session, tmdb_id)
                    keywords = await get_movie_keywords(session, tmdb_id)
                except TMDBError:
                    logger.exception("TMDB failed for tmdb_id=%s", tmdb_id)
                    continue

                kw_preview = ", ".join((keywords or [])[:6]) if keywords else "—"
                explanation = explanations_map.get(tmdb_id) or "Похоже по настроению и темам на то, что тебе обычно заходит."

                # сохраняем explanation_shown, если репозиторий есть
                try:
                    if "set_item_explanation" in locals() and set_item_explanation:
                        await set_item_explanation(session, item_id, explanation)
                except Exception:
                    logger.exception("set_item_explanation failed")

                text = (
                    f"{i}) {label}\n"
                    f"{details.title} ({details.year})\n"
                    f"{explanation}\n"
                    f"Runtime: {details.runtime} мин\n"
                    f"Genres: {', '.join(details.genres) if details.genres else '—'}\n"
                    f"Keywords: {kw_preview}\n"
                )
                await message.answer(text, reply_markup=rec_item_keyboard(item_id, tmdb_id).as_markup())
            return

        # --- Fallback v0 ---
        from app.recommender.v0 import recommend_v0

        picks = await recommend_v0(
            session=session,
            user_id=user.id,
            count=3,
            recent_days=60,
            seeds_limit=40,
        )

        if not picks:
            await message.answer(
                "Пока не могу собрать рекомендации (мало данных или всё отфильтровалось).\n"
                "Импортируй Letterboxd и/или добавь пару оценок через /review.\n"
                "Для v1 ещё нужны эмбеддинги (backfill + embedding_worker)."
            )
            return

        rec = await create_recommendation(
            session,
            user.id,
            context={"mode": "v0", "count": len(picks), "recent_days": 60},
        )

        await message.answer("Вот рекомендации на вечер 👇")

        for i, p in enumerate(picks, start=1):
            item = await add_recommendation_item(
                session=session,
                recommendation_id=rec.id,
                tmdb_id=p.tmdb_id,
                position=i,
                strategy=p.strategy,
                explanation_shown=f"{p.strategy}: {p.reason}",
            )

            try:
                details = await get_movie_details(session, p.tmdb_id)
                keywords = await get_movie_keywords(session, p.tmdb_id)
            except TMDBError:
                logger.exception("TMDB failed for tmdb_id=%s", p.tmdb_id)
                continue

            kw_preview = ", ".join((keywords or [])[:6]) if keywords else "—"
            label = label_for_strategy(p.strategy)

            text = (
                f"{i}) {label}\n"
                f"{details.title} ({details.year})\n"
                f"Runtime: {details.runtime} мин\n"
                f"Genres: {', '.join(details.genres) if details.genres else '—'}\n"
                f"Keywords: {kw_preview}\n"
            )
            await message.answer(text, reply_markup=rec_item_keyboard(int(item.id), p.tmdb_id).as_markup())


# -----------------------------
# Recommendation callbacks
# -----------------------------

@router.callback_query(F.data.startswith("skip:"))
async def cb_skip(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.data is None:
        return

    item_id = int(callback.data.split(":")[1])

    async with AsyncSessionLocal() as session:
        user = await get_or_create_user(session, telegram_id=callback.from_user.id)
        await set_item_status(session, item_id, "skipped")
        await clear_pending(session, user.id)

    await callback.answer("Пропустил ✅", show_alert=False)


@router.callback_query(F.data.startswith("watched:"))
async def cb_watched(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.data is None:
        return

    _, item_id_s, tmdb_id_s = callback.data.split(":")
    item_id = int(item_id_s)
    tmdb_id = int(tmdb_id_s)

    async with AsyncSessionLocal() as session:
        user = await get_or_create_user(session, telegram_id=callback.from_user.id)
        await set_pending(session, user.id, "awaiting_review", {"mode": "agent", "tmdb_id": tmdb_id, "item_id": item_id})
        details = await get_movie_details(session, tmdb_id)

    if callback.message:
        await callback.message.answer(
            f"Ок! Пиши рецензию на {details.title} ({details.year}).\n\n"
            "Сначала можно оценку, потом текст:\n"
            "• 4.5/5 текст...\n"
            "• 4 текст...\n"
            "• или просто текст — я уточню оценку"
        )
    await callback.answer()


# ---------------------------------
# Universal message handler (pending)
# ---------------------------------

@router.message(F.text)
async def handle_text(message: Message) -> None:
    if message.from_user is None or message.text is None:
        return

    text = message.text.strip()
    if not text:
        return

    async with AsyncSessionLocal() as session:
        user = await get_or_create_user(session, telegram_id=message.from_user.id)
        pending = await get_pending(session, user.id)

        if pending is None:
            await message.answer("Сейчас я не жду ввод. Используй /review или /recommend.")
            return

        # 1) awaiting_movie_query
        if pending.action_type == "awaiting_movie_query":
            title, year = parse_title_and_year(text)
            if not title:
                await message.answer("Напиши название фильма.")
                return

            try:
                candidates = await search_movie(query=title, year=year)
            except TMDBError as e:
                await message.answer(f"TMDB ошибка: {e}")
                return

            if not candidates:
                await message.answer("Не нашёл в TMDB. Попробуй другое название или добавь год.")
                return

            # авто-выбор если один кандидат
            if len(candidates) == 1:
                tmdb_id = candidates[0].tmdb_id
                await set_pending(session, user.id, "awaiting_review", {"mode": "manual", "tmdb_id": tmdb_id})
                details = await get_movie_details(session, tmdb_id)
                await message.answer(
                    f"Ок: {details.title} ({details.year}).\n\n"
                    "Теперь оцени 0–5 и напиши мысли (можно длинно).\n"
                    "Формат: 4.5/5 текст..."
                )
                return

            # если указан год, попробуем найти точное совпадение по году среди первых результатов
            if year is not None:
                exact = next((c for c in candidates[:10] if c.year == year), None)
                if exact is not None:
                    tmdb_id = exact.tmdb_id
                    await set_pending(session, user.id, "awaiting_review", {"mode": "manual", "tmdb_id": tmdb_id})
                    details = await get_movie_details(session, tmdb_id)
                    await message.answer(
                        f"Ок: {details.title} ({details.year}).\n\n"
                        "Теперь оцени 0–5 и напиши мысли (можно длинно).\n"
                        "Формат: 4.5/5 текст..."
                    )
                    return

            payload_candidates = [{"tmdb_id": c.tmdb_id, "title": c.title, "year": c.year} for c in candidates[:5]]
            await set_pending(session, user.id, "awaiting_movie_pick", {"mode": "manual", "candidates": payload_candidates})
            kb = movie_pick_keyboard(payload_candidates)
            await message.answer("Я нашёл несколько вариантов. Выбери правильный:", reply_markup=kb.as_markup())
            return

        # 2) awaiting_review
        if pending.action_type == "awaiting_review":
            payload = pending.payload_json
            mode = str(payload.get("mode"))
            tmdb_id = int(payload.get("tmdb_id"))
            item_id = payload.get("item_id")

            parsed = parse_rating_from_text(text)

            if parsed is None:
                await set_pending(
                    session,
                    user.id,
                    "awaiting_rating",
                    {"mode": mode, "tmdb_id": tmdb_id, "draft_review": text, "item_id": item_id},
                )
                await message.answer("Принял текст ✅ Теперь напиши только оценку 0–5 (например 4.5 или 4/5).")
                return

            rating = parsed.rating
            review_text = parsed.rest_text if parsed.rest_text else None

            await _save_review(session, user.telegram_id, tmdb_id, mode, rating, review_text, item_id)
            await clear_pending(session, user.id)
            await safe_answer(message, "Принято ✅")
            return

        # 3) awaiting_rating
        if pending.action_type == "awaiting_rating":
            payload = pending.payload_json
            mode = str(payload.get("mode"))
            tmdb_id = int(payload.get("tmdb_id"))
            item_id = payload.get("item_id")
            draft_review = payload.get("draft_review")

            parsed = parse_rating_from_text(text)
            if parsed is None:
                await message.answer("Не понял оценку. Напиши число 0–5 (например 4.5 или 4/5).")
                return

            rating = parsed.rating
            combined_review = (draft_review or "").strip()
            if parsed.rest_text:
                combined_review = (combined_review + "\n\n" + parsed.rest_text).strip()

            await _save_review(session, user.telegram_id, tmdb_id, mode, rating, combined_review or None, item_id)
            await clear_pending(session, user.id)
            await safe_answer(message, "Принято ✅")
            return

        # 4) awaiting_movie_pick
        if pending.action_type == "awaiting_movie_pick":
            await message.answer("Выбери вариант кнопкой выше или /cancel.")
            return


# -----------------------------
# Save review (manual/agent)
# -----------------------------

async def _save_review(
    session: AsyncSession,
    telegram_id: int,
    tmdb_id: int,
    mode: str,
    rating: float | None,
    review_text: str | None,
    item_id: int | None,
) -> None:
    """
    Сохраняем:
    - если mode=agent: feedback + status watched + watched_films(source=agent)
    - если mode=manual: watched_films(source=manual)
    Далее:
    - пересчёт taste_profile v0
    - (опционально) refresh summary_text через LLM
    - enqueue jobs на эмбеддинги (review / film_meta / profile)
    """
    from app.recommender.taste_profile_v0 import update_taste_profile_v0
    from app.db.repositories.taste_profile import get_taste_profile
    from app.db.repositories.embeddings import enqueue_embedding_job
    from app.recommender.embedding_texts import build_review_text, build_film_meta_text
    from app.db.repositories.watched import upsert_watched
    from app.core.config import settings

    user = await get_or_create_user(session, telegram_id=telegram_id)
    watched_date = today_in_tz(user.timezone)

    details = await get_movie_details(session, tmdb_id)

    # feedback + status
    if mode == "agent" and item_id is not None:
        await upsert_feedback(
            session,
            recommendation_item_id=int(item_id),
            rating=rating,
            review=review_text,
        )
        await set_item_status(session, int(item_id), "watched")
        source = "agent"
    else:
        source = "manual"

    watched_id = await upsert_watched(
        session=session,
        user_id=user.id,
        tmdb_id=tmdb_id,
        title=details.title,
        year=details.year,
        rating=rating,
        review=review_text,
        watched_date=watched_date,
        source=source,
    )

    await update_taste_profile_v0(session=session, user_id=user.id)

    # раз в N отзывов красиво переписать summary (если модуль есть)
    try:
        from app.llm.summary_refresh import maybe_refresh_summary_text
        await maybe_refresh_summary_text(session=session, user_id=user.id, every_n=10)
    except Exception:
        pass

    # enqueue embeddings
    review_embed_text = await build_review_text(
        title=details.title,
        year=details.year,
        rating=rating,
        review=review_text,
    )
    if review_embed_text.strip():
        await enqueue_embedding_job(
            session=session,
            user_id=user.id,
            source_type="review",
            source_id=int(watched_id),
            content_text=review_embed_text,
            model=settings.openai_embed_model,
            dimensions=settings.openai_embed_dimensions,
        )

    film_meta_text = await build_film_meta_text(session, tmdb_id)
    if film_meta_text.strip():
        await enqueue_embedding_job(
            session=session,
            user_id=user.id,
            source_type="film_meta",
            source_id=int(tmdb_id),
            content_text=film_meta_text,
            model=settings.openai_embed_model,
            dimensions=settings.openai_embed_dimensions,
        )

    profile = await get_taste_profile(session, user.id)
    if profile and profile.summary_text and profile.summary_text.strip():
        await enqueue_embedding_job(
            session=session,
            user_id=user.id,
            source_type="profile",
            source_id=int(user.id),
            content_text=profile.summary_text.strip(),
            model=settings.openai_embed_model,
            dimensions=settings.openai_embed_dimensions,
        )


# -----------------------------
# /avoid
# -----------------------------

@router.message(Command("avoid"))
async def cmd_avoid(message: Message) -> None:
    if message.from_user is None or message.text is None:
        return

    raw = message.text.replace("/avoid", "", 1).strip()
    if not raw:
        await message.answer("Используй: /avoid <описание темы>\nНапример: /avoid офисная нью-йоркская корпоративная тема")
        return

    words = [w.lower() for w in re.findall(r"[a-zA-Zа-яА-ЯёЁ]+", raw) if len(w) >= 4]
    keywords = words[:8] if words else [raw.lower()[:30]]

    async with AsyncSessionLocal() as session:
        user = await get_or_create_user(session, telegram_id=message.from_user.id)
        profile = (await session.execute(select(TasteProfile).where(TasteProfile.user_id == user.id))).scalar_one_or_none()

        avoids = (profile.avoids_json if profile else {}) or {}
        if not isinstance(avoids, dict):
            avoids = {}

        patterns = avoids.get("patterns", [])
        if not isinstance(patterns, list):
            patterns = []

        pid = f"p_{int(datetime.now(timezone.utc).timestamp())}"
        patterns.append({
            "id": pid,
            "label": raw,
            "keywords": keywords,
            "weight": -0.35,
            "confidence": 0.7,
            "cooldown_days": 14,
            "last_triggered": None,
        })

        avoids["version"] = "v1"
        avoids["patterns"] = patterns

        await set_avoids_json(session, user.id, avoids)

    await message.answer(f"Ок ✅ добавил мягкое избегание: {raw}\nKeywords: {', '.join(keywords)}")
