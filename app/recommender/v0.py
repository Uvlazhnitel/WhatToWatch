from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import TasteProfile
from app.db.repositories.recs_sources import (
    get_top_rated_tmdb_ids,
    get_fallback_top_tmdb_ids,
    get_watched_tmdb_ids,
    get_recent_recommended_tmdb_ids,
)

# ВАЖНО: импортируем модуль целиком, чтобы monkeypatch работал корректно
import app.integrations.tmdb as tmdb


@dataclass(frozen=True)
class RecPick:
    tmdb_id: int
    strategy: str  # safe / adjacent / wildcard
    score: float
    reason: str


def _normalize_weights(counts: dict[int, int]) -> dict[int, float]:
    total = sum(counts.values())
    if total <= 0:
        return {}
    return {k: v / total for k, v in counts.items()}


def _quality_score(c: tmdb.MovieCandidate) -> float:
    """
    0..1 примерно
    """
    vote = (c.vote_average or 0.0) / 10.0  # 0..1
    pop = min(1.0, (c.popularity or 0.0) / 80.0)  # 0..1
    return 0.6 * vote + 0.4 * pop


def _genre_overlap_score(c: tmdb.MovieCandidate, genre_weights: dict[int, float]) -> float:
    if not c.genre_ids or not genre_weights:
        return 0.0
    return sum(genre_weights.get(g, 0.0) for g in c.genre_ids)


def _is_diverse_enough(
    candidate: tmdb.MovieCandidate,
    chosen: list[tmdb.MovieCandidate],
) -> bool:
    """
    Простая диверсификация:
    - не брать фильм с полностью теми же genre_ids как уже выбранные
    """
    if not chosen:
        return True
    if not candidate.genre_ids:
        return True

    cand_set = set(candidate.genre_ids)
    for ch in chosen:
        if not ch.genre_ids:
            continue
        if cand_set == set(ch.genre_ids):
            return False
    return True


async def _fetch_candidates_for_seed(seed_tmdb_id: int, sem: asyncio.Semaphore) -> list[tmdb.MovieCandidate]:
    async with sem:
        # 1 страница similar + 1 страница recommendations
        try:
            sim_task = asyncio.create_task(tmdb.get_similar(seed_tmdb_id, page=1))
            rec_task = asyncio.create_task(tmdb.get_recommendations(seed_tmdb_id, page=1))
            sim, recs = await asyncio.gather(sim_task, rec_task)
            return (sim or []) + (recs or [])
        except tmdb.TMDBError:
            return []
        
from app.integrations import tmdb
from app.integrations.tmdb import MovieCandidate, TMDBError


async def _build_genre_preferences(session: AsyncSession, seed_tmdb_ids: list[int]) -> dict[int, float]:
    counts: dict[int, int] = {}
    for tmdb_id in seed_tmdb_ids:
        try:
            payload = await tmdb.get_movie_details_payload(session, tmdb_id)
        except (TMDBError, KeyError, Exception):
            # TMDB мог вернуть 404/ошибку, а в тестах stub может не иметь ключа
            continue

        genres = payload.get("genres", [])
        if isinstance(genres, list):
            for g in genres:
                if isinstance(g, dict) and isinstance(g.get("id"), int):
                    gid = int(g["id"])
                    counts[gid] = counts.get(gid, 0) + 1

    return _normalize_weights(counts)



def _dedupe_candidates(cands: list[tmdb.MovieCandidate]) -> dict[int, tmdb.MovieCandidate]:
    """
    Дедуп по tmdb_id. Если встретились разные варианты — оставим тот, у которого выше quality.
    """
    by_id: dict[int, tmdb.MovieCandidate] = {}
    for c in cands:
        if not c.tmdb_id:
            continue
        if c.tmdb_id not in by_id:
            by_id[c.tmdb_id] = c
        else:
            if _quality_score(c) > _quality_score(by_id[c.tmdb_id]):
                by_id[c.tmdb_id] = c
    return by_id


def _pick_safe(
    candidates: list[tmdb.MovieCandidate],
    genre_weights: dict[int, float],
) -> Optional[RecPick]:
    best: Optional[RecPick] = None
    for c in candidates:
        g = _genre_overlap_score(c, genre_weights)
        q = _quality_score(c)
        score = 0.75 * g + 0.25 * q
        if best is None or score > best.score:
            best = RecPick(c.tmdb_id, "safe", score, reason=f"genre_match={g:.3f}, quality={q:.3f}")
    return best


def _pick_adjacent(
    candidates: list[tmdb.MovieCandidate],
    genre_weights: dict[int, float],
    safe: tmdb.MovieCandidate,
) -> Optional[RecPick]:
    """
    Adjacent = всё ещё подходит (есть совпадение по вкус-генрам),
    но отличается: год/язык/набор жанров.
    """
    best: Optional[RecPick] = None
    safe_g = set(safe.genre_ids or [])
    safe_year = safe.year
    safe_lang = safe.original_language

    for c in candidates:
        if c.tmdb_id == safe.tmdb_id:
            continue

        g = _genre_overlap_score(c, genre_weights)
        q = _quality_score(c)

        # нужен хотя бы некоторый overlap
        if g < 0.12:
            continue

        diversity_bonus = 0.0

        # другой язык — бонус
        if safe_lang and c.original_language and c.original_language != safe_lang:
            diversity_bonus += 0.15

        # год далеко — бонус
        if safe_year and c.year and abs(c.year - safe_year) >= 10:
            diversity_bonus += 0.12

        # не полностью те же жанры — бонус
        c_set = set(c.genre_ids or [])
        if c_set and safe_g and c_set != safe_g:
            diversity_bonus += 0.10

        score = 0.60 * g + 0.30 * q + diversity_bonus
        if best is None or score > best.score:
            best = RecPick(
                c.tmdb_id,
                "adjacent",
                score,
                reason=f"genre_match={g:.3f}, quality={q:.3f}, bonus={diversity_bonus:.2f}",
            )
    return best


def _pick_wildcard(
    candidates: list[tmdb.MovieCandidate],
    genre_weights: dict[int, float],
    chosen: list[tmdb.MovieCandidate],
) -> Optional[RecPick]:
    """
    Wildcard = качество высокое, overlap по вкус-генрам небольшой.
    """
    best: Optional[RecPick] = None
    for c in candidates:
        if any(c.tmdb_id == ch.tmdb_id for ch in chosen):
            continue

        g = _genre_overlap_score(c, genre_weights)
        q = _quality_score(c)

        # хотим меньше совпадения по вкус-жанрам, но не ноль всегда
        if g > 0.18:
            continue

        diversity_bonus = 0.0
        if _is_diverse_enough(c, chosen):
            diversity_bonus += 0.12

        score = 0.20 * g + 0.70 * q + diversity_bonus
        if best is None or score > best.score:
            best = RecPick(
                c.tmdb_id,
                "wildcard",
                score,
                reason=f"genre_match={g:.3f}, quality={q:.3f}, bonus={diversity_bonus:.2f}",
            )
    return best


async def _genre_weights_from_profile(session: AsyncSession, user_id: int) -> dict[int, float]:
    profile = (await session.execute(select(TasteProfile).where(TasteProfile.user_id == user_id))).scalar_one_or_none()
    if profile is None:
        return {}
    weights = profile.weights_json or {}
    likes = weights.get("likes", {})
    genres = likes.get("genres", [])
    out: dict[int, float] = {}
    if isinstance(genres, list):
        for g in genres:
            if not isinstance(g, dict):
                continue
            gid = g.get("id")
            score = g.get("score")
            if isinstance(gid, int) and isinstance(score, (int, float)):
                out[int(gid)] = float(score)
    return out


async def recommend_v0(
    session: AsyncSession,
    user_id: int,
    count: int = 3,
    recent_days: int = 60,
    seeds_limit: int = 40,
) -> list[RecPick]:
    """
    Возвращает список RecPick (tmdb_id + стратегия).
    Без векторки: только метаданные и эвристики.
    """
    # 1) seeds = любимые фильмы пользователя
    seed_tmdb_ids = await get_top_rated_tmdb_ids(session, user_id, min_rating=4.0, limit=seeds_limit)
    if len(seed_tmdb_ids) < 10:
        seed_tmdb_ids = await get_fallback_top_tmdb_ids(session, user_id, limit=seeds_limit)

    if not seed_tmdb_ids:
        return []

    # 2) множество просмотренного и недавних рекомендаций
    watched = await get_watched_tmdb_ids(session, user_id)
    recent_recs = await get_recent_recommended_tmdb_ids(session, user_id, days=recent_days)

    # 3) жанровые предпочтения
    genre_weights = await _genre_weights_from_profile(session, user_id)
    if not genre_weights:
        genre_weights = await _build_genre_preferences(session, seed_tmdb_ids[: min(len(seed_tmdb_ids), 50)])

    # 4) собрать пул кандидатов similar/recommendations
    sem = asyncio.Semaphore(8)
    tasks = [
        asyncio.create_task(_fetch_candidates_for_seed(tmdb_id, sem))
        for tmdb_id in seed_tmdb_ids[: min(len(seed_tmdb_ids), 30)]
    ]
    chunks = await asyncio.gather(*tasks)
    pool = [c for chunk in chunks for c in chunk]

    # 5) дедуп
    by_id = _dedupe_candidates(pool)

    # 6) фильтры
    filtered: list[tmdb.MovieCandidate] = []
    seed_set = set(seed_tmdb_ids)
    for tmdb_id, c in by_id.items():
        if tmdb_id in watched:
            continue
        if tmdb_id in recent_recs:
            continue
        if tmdb_id in seed_set:
            continue
        filtered.append(c)

    if not filtered:
        return []

    # 7) выбираем safe/adjacent/wildcard
    safe_pick = _pick_safe(filtered, genre_weights)
    if safe_pick is None:
        return []

    safe_cand = next((c for c in filtered if c.tmdb_id == safe_pick.tmdb_id), None)
    if safe_cand is None:
        return []

    adjacent_pick = _pick_adjacent(filtered, genre_weights, safe_cand)
    chosen_candidates = [safe_cand]
    picks: list[RecPick] = [safe_pick]

    if adjacent_pick:
        adjacent_cand = next((c for c in filtered if c.tmdb_id == adjacent_pick.tmdb_id), None)
        if adjacent_cand:
            picks.append(adjacent_pick)
            chosen_candidates.append(adjacent_cand)

    wildcard_pick = _pick_wildcard(filtered, genre_weights, chosen_candidates)
    if wildcard_pick:
        picks.append(wildcard_pick)

    # 8) если count > 3 — добиваем “диверсифицированными топами”
    if count > len(picks):
        ranked = sorted(
            filtered,
            key=lambda c: (0.75 * _genre_overlap_score(c, genre_weights) + 0.25 * _quality_score(c)),
            reverse=True,
        )
        chosen_ids = {p.tmdb_id for p in picks}
        for c in ranked:
            if len(picks) >= count:
                break
            if c.tmdb_id in chosen_ids:
                continue
            if not _is_diverse_enough(c, [ch for ch in chosen_candidates]):
                continue
            picks.append(RecPick(c.tmdb_id, "safe", 0.0, "extra_diverse"))
            chosen_ids.add(c.tmdb_id)
            chosen_candidates.append(c)

    return picks[:count]
