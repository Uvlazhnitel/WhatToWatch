from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import TasteProfile, WatchedFilm
from app.db.repositories.recs_sources import (
    get_top_rated_tmdb_ids,
    get_fallback_top_tmdb_ids,
    get_watched_tmdb_ids,
    get_recent_recommended_tmdb_ids as get_recent_recommended_tmdb_ids_set,  # set-версия
)
from app.db.repositories.recs_context import get_recent_recommended_tmdb_ids, get_recent_watched_tmdb_ids
from app.db.repositories.embeddings import get_film_meta_embeddings, get_review_embeddings_by_watched_ids
from app.db.repositories.taste_profile import set_avoids_json
from app.integrations.tmdb import (
    get_similar,
    get_recommendations,
    get_movie_details_payload,
    MovieCandidate,
    TMDBError,
)
from app.recommender.vector_math import cosine_similarity, weighted_average

logger = logging.getLogger("recommender.v1")


@dataclass(frozen=True)
class V1CandidateScore:
    tmdb_id: int
    base_score: float
    sim_like: float
    sim_dislike: float
    novelty: float
    repeat_penalty: float
    soft_avoid_penalty: float
    triggered_avoid_ids: list[str]
    debug: str


@dataclass(frozen=True)
class RecPickV1:
    tmdb_id: int
    strategy: str
    score: float
    debug: str
    triggered_avoid_ids: list[str]


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _decade_from_release_date(release_date: str | None) -> int | None:
    if not release_date or not isinstance(release_date, str) or len(release_date) < 4:
        return None
    if not release_date[:4].isdigit():
        return None
    y = int(release_date[:4])
    return (y // 10) * 10


def _extract_genre_ids(payload: dict) -> list[int]:
    genres = payload.get("genres", [])
    out: list[int] = []
    if isinstance(genres, list):
        for g in genres:
            if isinstance(g, dict) and isinstance(g.get("id"), int):
                out.append(int(g["id"]))
    return out


def _build_text_for_soft_avoid(payload: dict) -> str:
    """
    Не тянем content_text из БД — собираем текст прямо из TMDB payload:
    overview + title + genres + keywords (если есть).
    """
    parts: list[str] = []
    title = payload.get("title") or payload.get("original_title") or ""
    overview = payload.get("overview") or ""
    if isinstance(title, str) and title:
        parts.append(title)
    if isinstance(overview, str) and overview:
        parts.append(overview)

    # genres: list[dict{id,name}]
    genres = payload.get("genres", [])
    if isinstance(genres, list):
        gnames = []
        for g in genres:
            if isinstance(g, dict) and isinstance(g.get("name"), str):
                gnames.append(g["name"])
        if gnames:
            parts.append("genres: " + ", ".join(gnames))

    # keywords: может быть list[str] или list[dict{name}]
    keywords = payload.get("keywords", [])
    if isinstance(keywords, list):
        knames = []
        for k in keywords:
            if isinstance(k, str):
                knames.append(k)
            elif isinstance(k, dict) and isinstance(k.get("name"), str):
                knames.append(k["name"])
        if knames:
            parts.append("keywords: " + ", ".join(knames[:25]))

    return "\n".join(parts)


def _soft_avoid_penalty(content_text: str, avoids_json: dict) -> tuple[float, list[str]]:
    """
    penalty по ключевым словам.
    avoids_json["patterns"] -> list[ {id, confidence, weight(<0), cooldown_days, last_triggered, keywords[]} ]
    """
    if not avoids_json or not isinstance(avoids_json, dict):
        return 0.0, []

    patterns = avoids_json.get("patterns", [])
    if not isinstance(patterns, list) or not patterns or not content_text:
        return 0.0, []

    now = datetime.now(timezone.utc)
    text = content_text.lower()

    total_penalty = 0.0
    triggered: list[str] = []

    for p in patterns:
        if not isinstance(p, dict):
            continue

        pid = str(p.get("id", "")).strip()
        conf = float(p.get("confidence", 0.0) or 0.0)
        weight = float(p.get("weight", 0.0) or 0.0)  # ожидаем отрицательный
        cooldown_days = int(p.get("cooldown_days", 14) or 14)

        if not pid:
            continue
        if conf < 0.6:
            continue
        if weight >= 0:
            continue

        last = p.get("last_triggered")
        if isinstance(last, str) and last:
            try:
                last_dt = datetime.fromisoformat(last.replace("Z", "+00:00"))
                if now - last_dt < timedelta(days=cooldown_days):
                    continue
            except Exception:
                pass

        keywords = p.get("keywords", [])
        if not isinstance(keywords, list) or not keywords:
            continue

        hit = False
        for kw in keywords:
            if not isinstance(kw, str):
                continue
            kw_norm = kw.strip().lower()
            if not kw_norm:
                continue
            if kw_norm in text:
                hit = True
                break

        if hit:
            total_penalty += (-weight)  # делаем положительный penalty
            triggered.append(pid)

    return total_penalty, triggered


def _assign_strategy(sim_like: float, novelty: float) -> str:
    if sim_like >= 0.45:
        return "safe"
    if sim_like >= 0.30 or novelty >=70:
        return "adjacent"
    return "wildcard"

def _mmr_select(
    scored: list[V1CandidateScore],
    vecs: dict[int, list[float]],
    k: int,
    lambda_relevance: float = 0.75,
) -> list[V1CandidateScore]:
    if not scored:
        return []

    remaining = scored[:]
    remaining.sort(key=lambda x: x.base_score, reverse=True)

    selected: list[V1CandidateScore] = []
    selected_ids: set[int] = set()

    while remaining and len(selected) < k:
        if not selected:
            best = remaining.pop(0)
            selected.append(best)
            selected_ids.add(best.tmdb_id)
            continue

        best_idx = None
        best_mmr = None

        for idx, cand in enumerate(remaining):
            v = vecs.get(cand.tmdb_id)
            if not v:
                redundancy = 0.2
            else:
                redundancy = 0.0
                for s in selected:
                    sv = vecs.get(s.tmdb_id)
                    if not sv:
                        continue
                    redundancy = max(redundancy, max(0.0, cosine_similarity(v, sv)))

            mmr = lambda_relevance * cand.base_score - (1.0 - lambda_relevance) * redundancy
            if best_mmr is None or mmr > best_mmr:
                best_mmr = mmr
                best_idx = idx

        if best_idx is None:
            break

        best = remaining.pop(best_idx)
        if best.tmdb_id in selected_ids:
            continue

        selected.append(best)
        selected_ids.add(best.tmdb_id)

    return selected


async def _fetch_candidates_pool(seed_tmdb_ids: list[int]) -> list[MovieCandidate]:
    sem = asyncio.Semaphore(8)

    async def one(seed: int) -> list[MovieCandidate]:
        async with sem:
            try:
                sim_task = asyncio.create_task(get_similar(seed, page=1))
                rec_task = asyncio.create_task(get_recommendations(seed, page=1))
                sim, recs = await asyncio.gather(sim_task, rec_task)
                return (sim or []) + (recs or [])
            except TMDBError:
                return []

    tasks = [asyncio.create_task(one(s)) for s in seed_tmdb_ids]
    chunks = await asyncio.gather(*tasks)
    return [c for ch in chunks for c in ch]


def _dedupe_pool(pool: list[MovieCandidate]) -> dict[int, MovieCandidate]:
    by_id: dict[int, MovieCandidate] = {}
    for c in pool:
        if not c.tmdb_id:
            continue
        if c.tmdb_id not in by_id:
            by_id[c.tmdb_id] = c
        else:
            cur = by_id[c.tmdb_id]
            cur_q = (cur.vote_average or 0) + (cur.popularity or 0) / 100
            new_q = (c.vote_average or 0) + (c.popularity or 0) / 100
            if new_q > cur_q:
                by_id[c.tmdb_id] = c
    return by_id


async def _build_like_dislike_vectors(
    session: AsyncSession,
    user_id: int,
    like_thr: float = 4.0,
    dislike_thr: float = 2.5,
    max_films: int = 200,
) -> tuple[list[float] | None, list[float] | None]:
    """
    Берём фильмы с оценками:
    - likes: rating >= like_thr
    - dislikes: rating <= dislike_thr

    Предпочтение:
    - review embeddings (если они keyed по tmdb_id)
    - иначе film_meta embeddings
    """
    stmt = (
        select(WatchedFilm.tmdb_id, WatchedFilm.your_rating)
        .where(WatchedFilm.user_id == user_id)
        .where(WatchedFilm.your_rating.is_not(None))
        .order_by(WatchedFilm.watched_date.desc().nullslast(), WatchedFilm.id.desc())
        .limit(max_films)
    )
    rows = (await session.execute(stmt)).all()

    liked_tmdb_ids = [int(tid) for (tid, r) in rows if tid is not None and float(r) >= like_thr]
    disliked_tmdb_ids = [int(tid) for (tid, r) in rows if tid is not None and float(r) <= dislike_thr]

    # review embeddings (если source_id=tmdb_id)
    review_like = await get_review_embeddings_by_watched_ids(session, user_id, liked_tmdb_ids)
    review_dislike = await get_review_embeddings_by_watched_ids(session, user_id, disliked_tmdb_ids)

    film_like = await get_film_meta_embeddings(session, user_id, liked_tmdb_ids)
    film_dislike = await get_film_meta_embeddings(session, user_id, disliked_tmdb_ids)

    like_vectors: list[tuple[list[float], float]] = []
    for tid in liked_tmdb_ids:
        emb = review_like.get(tid)
        if emb is not None:
            like_vectors.append((list(emb), 1.25))
    for tid in liked_tmdb_ids:
        emb = film_like.get(tid)
        if emb is not None:
            like_vectors.append((list(emb), 1.0))

    dislike_vectors: list[tuple[list[float], float]] = []
    for tid in disliked_tmdb_ids:
        emb = review_dislike.get(tid)
        if emb is not None:
            dislike_vectors.append((list(emb), 1.25))
    for tid in disliked_tmdb_ids:
        emb = film_dislike.get(tid)
        if emb is not None:
            dislike_vectors.append((list(emb), 1.0))

    like_vec = weighted_average(like_vectors)
    dislike_vec = weighted_average(dislike_vectors)
    return like_vec, dislike_vec


async def _repeat_context_counts(
    session: AsyncSession,
    tmdb_ids: list[int],
) -> tuple[dict[int, int], dict[int, int]]:
    genre_counts: dict[int, int] = {}
    decade_counts: dict[int, int] = {}

    for tid in tmdb_ids:
        payload = await get_movie_details_payload(session, tid)
        for gid in _extract_genre_ids(payload):
            genre_counts[gid] = genre_counts.get(gid, 0) + 1
        dec = _decade_from_release_date(payload.get("release_date"))
        if dec is not None:
            decade_counts[dec] = decade_counts.get(dec, 0) + 1

    return genre_counts, decade_counts


def _repeat_penalty_for_candidate(
    cand_payload: dict,
    genre_counts: dict[int, int],
    decade_counts: dict[int, int],
    total_context: int,
) -> float:
    if total_context <= 0:
        return 0.0

    penalty = 0.0
    gids = _extract_genre_ids(cand_payload)
    for gid in gids[:4]:
        freq = genre_counts.get(gid, 0) / total_context
        penalty += 0.20 * freq

    dec = _decade_from_release_date(cand_payload.get("release_date"))
    if dec is not None:
        freq = decade_counts.get(dec, 0) / total_context
        penalty += 0.12 * freq

    return _clamp(penalty, 0.0, 0.5)


async def recommend_v1(
    session: AsyncSession,
    user_id: int,
    count: int = 5,
    recent_days: int = 60,
    seeds_limit: int = 40,
) -> list[RecPickV1]:
    # 1) seeds
    seed_tmdb_ids = await get_top_rated_tmdb_ids(session, user_id, min_rating=4.0, limit=seeds_limit)
    if len(seed_tmdb_ids) < 10:
        seed_tmdb_ids = await get_fallback_top_tmdb_ids(session, user_id, limit=seeds_limit)
    if not seed_tmdb_ids:
        return []

    logger.info("v1 seeds=%d", len(seed_tmdb_ids))

    # 2) фильтры: watched + recent recs
    watched = await get_watched_tmdb_ids(session, user_id)
    recent_recs_set = await get_recent_recommended_tmdb_ids_set(session, user_id, days=recent_days)

    # 3) пул кандидатов из similar/recommendations
    pool = await _fetch_candidates_pool(seed_tmdb_ids[: min(30, len(seed_tmdb_ids))])
    by_id = _dedupe_pool(pool)

    # 4) фильтрация
    candidates: list[MovieCandidate] = []
    seed_set = set(seed_tmdb_ids)
    for tid, c in by_id.items():
        if tid in watched:
            continue
        if tid in recent_recs_set:
            continue
        if tid in seed_set:
            continue
        candidates.append(c)

    if not candidates:
        return []

    candidate_ids = [c.tmdb_id for c in candidates]

    # 5) вектора кандидатов (film_meta)
    emb_map = await get_film_meta_embeddings(session, user_id, candidate_ids)
    logger.info(
        "v1 candidate_ids=%d embeddings_found=%d (user_id=%d)",
        len(candidate_ids),
        len(emb_map),
        user_id,
    )

    cand_vecs: dict[int, list[float]] = {int(tid): list(vec) for tid, vec in emb_map.items()}

    # Если эмбеддингов мало — лучше не выдавать “пустую” v1
    min_needed = max(10, count * 2)
    if len(cand_vecs) < min_needed:
        logger.warning("v1 fallback: not enough candidate embeddings (%d < %d)", len(cand_vecs), min_needed)
        return []

    # 6) like/dislike vectors
    like_vec, dislike_vec = await _build_like_dislike_vectors(session, user_id)

    # 7) novelty: сравнение с недавними рекомендациями
    recent_ids = await get_recent_recommended_tmdb_ids(session, user_id, days=recent_days, limit=150)
    recent_emb_map = await get_film_meta_embeddings(session, user_id, recent_ids)
    recent_vecs = [list(v) for v in recent_emb_map.values()]

    # 8) repeat context: последние рекомендации + просмотры
    context_ids: list[int] = []
    context_ids += recent_ids[:60]
    context_ids += (await get_recent_watched_tmdb_ids(session, user_id, limit=40))
    context_ids = list(dict.fromkeys(context_ids))[:80]

    genre_counts, decade_counts = await _repeat_context_counts(session, context_ids)
    total_context = max(1, len(context_ids))

    # 9) avoids_json
    profile = (await session.execute(select(TasteProfile).where(TasteProfile.user_id == user_id))).scalar_one_or_none()
    avoids_json = (profile.avoids_json if profile else {}) or {}

    # 10) scoring
    scored: list[V1CandidateScore] = []
    for c in candidates:
        tid = c.tmdb_id
        vec = cand_vecs.get(tid)
        if not vec:
            continue  # нет вектора => пропускаем в v1

        sim_like = cosine_similarity(vec, like_vec) if like_vec else 0.0
        sim_dislike = cosine_similarity(vec, dislike_vec) if dislike_vec else 0.0

        # novelty = 1 - max_sim_to_recent
        max_sim_recent = 0.0
        if recent_vecs:
            for rv in recent_vecs:
                max_sim_recent = max(max_sim_recent, max(0.0, cosine_similarity(vec, rv)))
        novelty = _clamp(1.0 - max_sim_recent, 0.0, 1.0)

        # детали кандидата одним payload (используем и для repeat, и для soft-avoid текста)
        cand_payload = await get_movie_details_payload(session, tid)

        repeat_pen = _repeat_penalty_for_candidate(cand_payload, genre_counts, decade_counts, total_context)

        content_text = _build_text_for_soft_avoid(cand_payload)
        soft_pen, triggered_ids = _soft_avoid_penalty(content_text, avoids_json)

        base = (
            1.0 * sim_like
            - 0.7 * sim_dislike
            + 0.2 * novelty
            - repeat_pen
            - soft_pen
        )

        debug = f"like={sim_like:.3f} dislike={sim_dislike:.3f} nov={novelty:.2f} rep={repeat_pen:.2f} avoid={soft_pen:.2f}"
        scored.append(
            V1CandidateScore(
                tmdb_id=tid,
                base_score=base,
                sim_like=sim_like,
                sim_dislike=sim_dislike,
                novelty=novelty,
                repeat_penalty=repeat_pen,
                soft_avoid_penalty=soft_pen,
                triggered_avoid_ids=triggered_ids,
                debug=debug,
            )
        )

    if not scored:
        return []

    # 11) MMR
    selected = _mmr_select(scored, cand_vecs, k=count, lambda_relevance=0.75)

    # 12) update last_triggered для avoids
    if profile and isinstance(avoids_json, dict) and "patterns" in avoids_json:
        now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        pats = avoids_json.get("patterns", [])
        if isinstance(pats, list) and pats:
            chosen_triggered = {pid for s in selected for pid in s.triggered_avoid_ids}
            if chosen_triggered:
                for p in pats:
                    if isinstance(p, dict) and str(p.get("id")) in chosen_triggered:
                        p["last_triggered"] = now_iso
                avoids_json["patterns"] = pats
                await set_avoids_json(session, user_id, avoids_json)

    # 13) стратегия
    picks: list[RecPickV1] = []
    for s in selected:
        strategy = _assign_strategy(s.sim_like, s.novelty)
        picks.append(
            RecPickV1(
                tmdb_id=s.tmdb_id,
                strategy=strategy,
                score=s.base_score,
                debug=s.debug,
                triggered_avoid_ids=s.triggered_avoid_ids,
            )
        )

    return picks
