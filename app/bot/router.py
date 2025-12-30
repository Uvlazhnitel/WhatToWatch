from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

from app.db.session import AsyncSessionLocal, AsyncSession
from app.db.repositories.pending import set_pending, get_pending, clear_pending
from app.db.repositories.watched import insert_watched
from app.db.repositories.recommendations import (
    create_recommendation,
    add_recommendation_item,
    set_item_status,
    upsert_feedback,
)
from app.integrations.tmdb import (
    search_movie,
    get_movie_details,
    get_movie_keywords,
    get_trending_movies,
    TMDBError,
)
from app.bot.keyboards import movie_pick_keyboard, rec_item_keyboard
from app.bot.parsing import parse_rating_from_text, parse_title_and_year

router = Router()
from app.db.repositories.users import get_or_create_user  # Import the missing function

router = Router()

def today_in_tz(tz_name: str) -> datetime.date:
    try:
        return datetime.now(ZoneInfo(tz_name)).date()
    except Exception:
        return datetime.utcnow().date()


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
        "/recommend — получить 3 демо-рекомендации (trending)\n"
        "/cancel — отменить текущий ввод\n\n"
        "Главное: я умею принимать длинные рецензии — пиши сколько хочешь."
    )


@router.message(Command("cancel"))
async def cmd_cancel(message: Message) -> None:
    if message.from_user is None:
        return
    async with AsyncSessionLocal() as session:
        user = await get_or_create_user(session, telegram_id=message.from_user.id)
        await clear_pending(session, user.id)

    await message.answer("Ок, отменил ✅")


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
# Demo recommend flow (/recommend)
# -----------------------------

@router.message(Command("recommend"))
async def cmd_recommend(message: Message) -> None:
    if message.from_user is None:
        return

    async with AsyncSessionLocal() as session:
        user = await get_or_create_user(session, telegram_id=message.from_user.id)

        # v0 рекомендации
        from app.recommender.v0 import recommend_v0

        picks = await recommend_v0(
            session=session,
            user_id=user.id,
            count=3,          # можешь поставить 5
            recent_days=60,
            seeds_limit=40,
        )

        if not picks:
            await message.answer(
                "Пока не могу собрать рекомендации (мало данных или всё отфильтровалось).\n"
                "Попробуй сначала импортировать Letterboxd и/или добавить пару оценок через /review."
            )
            return

        rec = await create_recommendation(
            session,
            user.id,
            context={"mode": "v0", "count": len(picks), "recent_days": 60},
        )

        await message.answer("Вот рекомендации на вечер 👇 (v0, без векторной памяти пока)")

        for i, p in enumerate(picks, start=1):
            item = await add_recommendation_item(
                session=session,
                recommendation_id=rec.id,
                tmdb_id=p.tmdb_id,
                position=i,
                strategy=p.strategy,
                explanation_shown=f"{p.strategy}: {p.reason}",
            )

            details = await get_movie_details(session, p.tmdb_id)
            keywords = await get_movie_keywords(session, p.tmdb_id)
            kw_preview = ", ".join(keywords[:6]) if keywords else "—"

            label = {"safe": "🎯 Попадание", "adjacent": "🧭 Рядом, но иначе", "wildcard": "🎲 Эксперимент"}.get(p.strategy, p.strategy)

            text = (
                f"{i}) {label}\n"
                f"{details.title} ({details.year})\n"
                f"Runtime: {details.runtime} мин\n"
                f"Genres: {', '.join(details.genres) if details.genres else '—'}\n"
                f"Keywords: {kw_preview}\n\n"
                "Выбор:"
            )
            await message.answer(text, reply_markup=rec_item_keyboard(item.id, p.tmdb_id).as_markup())

from aiogram.filters import Command

@router.message(Command("myid"))
async def cmd_myid(message: Message) -> None:
    if message.from_user is None:
        return
    await message.answer(f"Твой telegram id: {message.from_user.id}")

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
            # Нет ожидания — подсказываем команды
            await message.answer("Я тебя понял, но сейчас не жду ввод. Используй /review или /recommend.")
            return

        # 1) Ждём название фильма
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

            # Если ровно 1 кандидат и год совпал — автопик
            if len(candidates) == 1 or (year is not None and candidates[0].year == year):
                tmdb_id = candidates[0].tmdb_id
                await set_pending(session, user.id, "awaiting_review", {"mode": "manual", "tmdb_id": tmdb_id})
                details = await get_movie_details(session, tmdb_id)
                await message.answer(
                    f"Ок: {details.title} ({details.year}).\n\n"
                    "Теперь оцени 0–5 и напиши мысли (можно длинно).\n"
                    "Формат: 4.5/5 текст..."
                )
                return

            # Иначе — предлагаем выбрать из топ-5
            payload_candidates = [{"tmdb_id": c.tmdb_id, "title": c.title, "year": c.year} for c in candidates[:5]]
            await set_pending(session, user.id, "awaiting_movie_pick", {"mode": "manual", "candidates": payload_candidates})
            kb = movie_pick_keyboard(payload_candidates)
            await message.answer("Я нашёл несколько вариантов. Выбери правильный:", reply_markup=kb.as_markup())
            return

        # 2) Ждём рецензию (может быть без оценки)
        if pending.action_type == "awaiting_review":
            payload = pending.payload_json
            mode = payload.get("mode")
            tmdb_id = int(payload.get("tmdb_id"))

            parsed = parse_rating_from_text(text)

            if parsed is None:
                # Рейтинга нет — запомним текст как черновик и спросим оценку
                await set_pending(session, user.id, "awaiting_rating", {"mode": mode, "tmdb_id": tmdb_id, "draft_review": text, "item_id": payload.get("item_id")})
                await message.answer("Принял текст ✅ Теперь напиши только оценку 0–5 (например 4.5 или 4/5).")
                return

            rating = parsed.rating
            review_text = parsed.rest_text if parsed.rest_text else None

            await _save_review(session, user.telegram_id, tmdb_id, mode, rating, review_text, payload.get("item_id"))
            await clear_pending(session, user.id)
            await message.answer("Принято ✅")
            return

        # 3) Ждём только оценку (текст уже есть)
        if pending.action_type == "awaiting_rating":
            payload = pending.payload_json
            mode = payload.get("mode")
            tmdb_id = int(payload.get("tmdb_id"))
            draft_review = payload.get("draft_review")

            parsed = parse_rating_from_text(text)
            if parsed is None:
                await message.answer("Не понял оценку. Напиши, пожалуйста, число 0–5 (например 4.5 или 4/5).")
                return

            rating = parsed.rating
            # если пользователь случайно добавил текст — добавим к черновику
            combined_review = (draft_review or "").strip()
            if parsed.rest_text:
                combined_review = (combined_review + "\n\n" + parsed.rest_text).strip()

            await _save_review(session, user.telegram_id, tmdb_id, mode, rating, combined_review or None, payload.get("item_id"))
            await clear_pending(session, user.id)
            await message.answer("Принято ✅")
            return

        # 4) awaiting_movie_pick — пользователь должен нажать кнопку
        if pending.action_type == "awaiting_movie_pick":
            await message.answer("Выбери вариант кнопкой выше или /cancel.")
            return


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
    """
    # получим user + timezone
    from app.db.repositories.users import get_or_create_user  # локально, чтобы избежать циклов

    user = await get_or_create_user(session, telegram_id=telegram_id)
    watched_date = today_in_tz(user.timezone)

    details = await get_movie_details(session, tmdb_id)

    if mode == "agent" and item_id is not None:
        await upsert_feedback(session, recommendation_item_id=int(item_id), rating=rating, review=review_text)
        await set_item_status(session, int(item_id), "watched")
        source = "agent"
    else:
        source = "manual"

    await insert_watched(
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
