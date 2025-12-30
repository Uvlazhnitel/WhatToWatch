from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, UTC
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import WatchedFilm
from app.db.repositories.taste_profile import upsert_taste_profile
from app.integrations.tmdb import get_movie_details_payload


@dataclass(frozen=True)
class RatedMovie:
    tmdb_id: int
    rating: float


def _decade_from_year(year: int | None) -> int | None:
    if not year:
        return None
    return (year // 10) * 10


def _top_items(counts: dict[Any, int], top_n: int = 8) -> list[dict]:
    total = sum(counts.values()) or 1
    items = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:top_n]
    return [{"key": k, "count": v, "score": round(v / total, 4)} for k, v in items]


def _format_decade(dec: int) -> str:
    return f"{dec}-е"


def _build_summary(weights: dict) -> str:
    likes = weights.get("likes", {})
    dislikes = weights.get("dislikes", {})

    liked_genres = [g.get("name") for g in likes.get("genres", []) if g.get("name")]
    disliked_genres = [g.get("name") for g in dislikes.get("genres", []) if g.get("name")]

    liked_decades = [d.get("decade") for d in likes.get("decades", []) if d.get("decade") is not None]
    liked_countries = [c.get("name") for c in likes.get("countries", []) if c.get("name")]

    parts = []
    if liked_genres:
        parts.append("Тебе чаще нравится (жанры): " + ", ".join(liked_genres[:5]))
    if liked_decades:
        parts.append("Любимые десятилетия: " + ", ".join(_format_decade(int(d)) for d in liked_decades[:4]))
    if liked_countries:
        parts.append("Часто заходят страны: " + ", ".join(liked_countries[:4]))

    if disliked_genres:
        parts.append("Чаще не заходит (жанры): " + ", ".join(disliked_genres[:5]))

    if not parts:
        return "Пока мало данных для профиля вкуса. Добавь ещё оценок и рецензий 🙂"

    return "\n".join(parts)


async def update_taste_profile_v0(
    session: AsyncSession,
    user_id: int,
    like_threshold: float = 4.0,
    dislike_threshold: float = 2.5,
    max_rated_films: int = 250,
    sources: tuple[str, ...] = ("letterboxd", "agent", "manual"),
) -> None:
    stmt = (
        select(WatchedFilm.tmdb_id, WatchedFilm.your_rating)
        .where(WatchedFilm.user_id == user_id)
        .where(WatchedFilm.your_rating.is_not(None))
        .where(WatchedFilm.source.in_(sources))
        .order_by(WatchedFilm.watched_date.desc().nullslast(), WatchedFilm.id.desc())
        .limit(max_rated_films)
    )
    rows = (await session.execute(stmt)).all()

    rated: list[RatedMovie] = []
    for tmdb_id, rating in rows:
        if tmdb_id is None or rating is None:
            continue
        rated.append(RatedMovie(int(tmdb_id), float(rating)))

    liked = [r for r in rated if r.rating >= like_threshold]
    disliked = [r for r in rated if r.rating <= dislike_threshold]

    # 2) Подтянуть детали (кешируются) — параллельно и с ограничением
    sem = asyncio.Semaphore(8)

    async def load_payload(tmdb_id: int) -> dict[str, Any]:
        async with sem:
            return await get_movie_details_payload(session, tmdb_id)

    # Чтобы не качать лишнее, берём только из liked/disliked
    need_ids = list({r.tmdb_id for r in liked + disliked})
    payloads: dict[int, dict[str, Any]] = {}

    tasks = [asyncio.create_task(load_payload(tid)) for tid in need_ids]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    for tmdb_id, res in zip(need_ids, results):
        if isinstance(res, Exception):
            continue
        payloads[tmdb_id] = res

    # 3) Считаем статистику
    liked_genres: dict[int, int] = {}
    disliked_genres: dict[int, int] = {}
    liked_decades: dict[int, int] = {}
    liked_countries: dict[str, dict[str, int]] = {}  # code -> {name,count}

    genre_names: dict[int, str] = {}

    def ingest_genres(target: dict[int, int], payload: dict[str, Any]) -> None:
        genres = payload.get("genres", [])
        if not isinstance(genres, list):
            return
        for g in genres:
            if not isinstance(g, dict):
                continue
            gid = g.get("id")
            name = g.get("name")
            if isinstance(gid, int):
                target[gid] = target.get(gid, 0) + 1
                if isinstance(name, str) and name:
                    genre_names[gid] = name

    def ingest_liked_extra(payload: dict[str, Any]) -> None:
        # decade
        release_date = payload.get("release_date")
        year = None
        if isinstance(release_date, str) and len(release_date) >= 4 and release_date[:4].isdigit():
            year = int(release_date[:4])
        dec = _decade_from_year(year)
        if dec is not None:
            liked_decades[dec] = liked_decades.get(dec, 0) + 1

        # countries
        countries = payload.get("production_countries", [])
        if isinstance(countries, list):
            for c in countries:
                if not isinstance(c, dict):
                    continue
                code = c.get("iso_3166_1")
                name = c.get("name")
                if isinstance(code, str) and code:
                    if code not in liked_countries:
                        liked_countries[code] = {"name": name if isinstance(name, str) else code, "count": 0}
                    liked_countries[code]["count"] += 1

    for r in liked:
        payload = payloads.get(r.tmdb_id)
        if not payload:
            continue
        ingest_genres(liked_genres, payload)
        ingest_liked_extra(payload)

    for r in disliked:
        payload = payloads.get(r.tmdb_id)
        if not payload:
            continue
        ingest_genres(disliked_genres, payload)

    # 4) Собираем weights_json
    liked_genres_top = _top_items(liked_genres, top_n=10)
    disliked_genres_top = _top_items(disliked_genres, top_n=10)
    liked_decades_top = _top_items(liked_decades, top_n=8)

    # страны
    countries_list = sorted(liked_countries.items(), key=lambda kv: kv[1]["count"], reverse=True)[:8]
    liked_countries_top = [
        {"code": code, "name": meta["name"], "count": meta["count"], "score": round(meta["count"] / (sum(v["count"] for v in liked_countries.values()) or 1), 4)}
        for code, meta in countries_list
    ]

    # Подменим key->id/name для жанров
    def hydrate_genre(items: list[dict]) -> list[dict]:
        out = []
        for it in items:
            gid = it["key"]
            out.append({"id": gid, "name": genre_names.get(gid, str(gid)), "count": it["count"], "score": it["score"]})
        return out

    def hydrate_decade(items: list[dict]) -> list[dict]:
        return [{"decade": it["key"], "count": it["count"], "score": it["score"]} for it in items]

    weights_json = {
        "version": "v0",
        "computed_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "thresholds": {"like": like_threshold, "dislike": dislike_threshold},
        "source": {"rated_films_used": len(rated), "liked": len(liked), "disliked": len(disliked)},
        "likes": {
            "genres": hydrate_genre(liked_genres_top),
            "decades": hydrate_decade(liked_decades_top),
            "countries": liked_countries_top,
        },
        "dislikes": {
            "genres": hydrate_genre(disliked_genres_top),
        },
    }

    summary_text = _build_summary(weights_json)

    await upsert_taste_profile(
        session=session,
        user_id=user_id,
        summary_text=summary_text,
        weights_json=weights_json,
        avoids_json={}, 
    )

    
