from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import TMDBError
from app.db.models import TmdbMovieDetailsCache, TmdbMovieKeywordsCache


CACHE_TTL_DAYS = 30


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _expires_at(ttl_days: int = CACHE_TTL_DAYS) -> datetime:
    return _utcnow() + timedelta(days=ttl_days)


def _safe_int(value: Any) -> Optional[int]:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _extract_year(release_date: Optional[str]) -> Optional[int]:
    # TMDB отдаёт release_date как "YYYY-MM-DD"
    if not release_date:
        return None
    if len(release_date) >= 4 and release_date[:4].isdigit():
        return int(release_date[:4])
    return None


@dataclass(frozen=True)
class MovieCandidate:
    tmdb_id: int
    title: str
    year: Optional[int]
    popularity: float | None = None
    vote_average: float | None = None
    genre_ids: list[int] | None = None
    original_language: str | None = None


@dataclass(frozen=True)
class MovieDetails:
    tmdb_id: int
    title: str
    year: Optional[int]
    runtime: Optional[int]
    genres: list[str]
    overview: str | None


async def _tmdb_get(path: str, params: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    """
    Низкоуровневый GET к TMDB.
    Использует v3 API key (query param api_key).
    """
    if not settings.tmdb_api_key or settings.tmdb_api_key == "PUT_YOUR_TMDB_KEY_HERE":
        raise TMDBError("TMDB_API_KEY is not set. Put it into .env")

    final_params = dict(params or {})
    final_params["api_key"] = settings.tmdb_api_key
    final_params.setdefault("language", settings.tmdb_language)

    timeout = httpx.Timeout(10.0, connect=10.0)
    async with httpx.AsyncClient(base_url=settings.tmdb_base_url, timeout=timeout) as client:
        try:
            resp = await client.get(path, params=final_params)
        except httpx.HTTPError as e:
            raise TMDBError(f"TMDB network error: {e!r}") from e

    if resp.status_code == 401:
        raise TMDBError("TMDB 401 Unauthorized: check TMDB_API_KEY")
    if resp.status_code == 404:
        raise TMDBError(f"TMDB 404 Not Found: {path}")
    if resp.status_code >= 400:
        raise TMDBError(f"TMDB HTTP {resp.status_code}: {resp.text[:300]}")

    try:
        data = resp.json()
    except ValueError as e:
        raise TMDBError("TMDB invalid JSON response") from e

    if not isinstance(data, dict):
        raise TMDBError("TMDB response is not a JSON object")

    return data


# -------------------------
# Public functions
# -------------------------

async def search_movie(
    query: str,
    year: Optional[int] = None,
    page: int = 1,
    include_adult: bool = False,
) -> list[MovieCandidate]:
    """
    Поиск фильма по названию (и опционально году).
    Возвращает список кандидатов с tmdb_id, title, year.
    """
    params: dict[str, Any] = {
        "query": query,
        "page": page,
        "include_adult": include_adult,
    }
    if year is not None:
        params["year"] = year

    data = await _tmdb_get("/search/movie", params=params)
    results = data.get("results", [])

    candidates: list[MovieCandidate] = []
    if isinstance(results, list):
        for r in results:
            if not isinstance(r, dict):
                continue
            tmdb_id = _safe_int(r.get("id"))
            title = r.get("title") or r.get("original_title")
            if not tmdb_id or not title:
                continue

            y = _extract_year(r.get("release_date"))
            genre_ids_raw = r.get("genre_ids")
            genre_ids: list[int] | None = None
            if isinstance(genre_ids_raw, list):
                genre_ids = []
                for g in genre_ids_raw:
                    try:
                        genre_ids.append(int(g))
                    except Exception:
                        pass

            candidates.append(
                MovieCandidate(
                    tmdb_id=tmdb_id,
                    title=str(title),
                    year=y,
                    popularity=float(r.get("popularity")) if r.get("popularity") is not None else None,
                    vote_average=float(r.get("vote_average")) if r.get("vote_average") is not None else None,
                    genre_ids=genre_ids,
                    original_language=str(r.get("original_language")) if r.get("original_language") else None,
                )
            )

    return candidates


async def get_movie_details(session: AsyncSession, tmdb_id: int) -> MovieDetails:
    """
    Детали фильма: title/year/runtime/genres/overview.
    Сначала читаем кеш из БД, иначе идём в TMDB и обновляем кеш.
    """
    cached = await _get_cached(session, TmdbMovieDetailsCache, tmdb_id)
    if cached is None:
        data = await _tmdb_get(f"/movie/{tmdb_id}")
        await _upsert_cache(session, TmdbMovieDetailsCache, tmdb_id, data)
    else:
        data = cached

    title = data.get("title") or data.get("original_title") or ""
    year = _extract_year(data.get("release_date"))
    runtime = _safe_int(data.get("runtime"))
    overview = data.get("overview")
    genres_raw = data.get("genres", [])
    genres: list[str] = []
    if isinstance(genres_raw, list):
        for g in genres_raw:
            if isinstance(g, dict) and g.get("name"):
                genres.append(str(g["name"]))

    return MovieDetails(
        tmdb_id=tmdb_id,
        title=str(title),
        year=year,
        runtime=runtime,
        genres=genres,
        overview=str(overview) if overview is not None else None,
    )


async def get_movie_keywords(session: AsyncSession, tmdb_id: int) -> list[str]:
    """
    Keywords фильма (список строк).
    Кешируем в БД.
    """
    cached = await _get_cached(session, TmdbMovieKeywordsCache, tmdb_id)
    if cached is None:
        data = await _tmdb_get(f"/movie/{tmdb_id}/keywords")
        await _upsert_cache(session, TmdbMovieKeywordsCache, tmdb_id, data)
    else:
        data = cached

    keywords_raw = data.get("keywords", [])
    keywords: list[str] = []
    if isinstance(keywords_raw, list):
        for k in keywords_raw:
            if isinstance(k, dict) and k.get("name"):
                keywords.append(str(k["name"]))
    return keywords


async def get_similar(tmdb_id: int, page: int = 1) -> list[MovieCandidate]:
    """
    Похожие фильмы (без кеша — можно добавить позже).
    """
    data = await _tmdb_get(f"/movie/{tmdb_id}/similar", params={"page": page})
    return _parse_candidate_list(data.get("results", []))


async def get_recommendations(tmdb_id: int, page: int = 1) -> list[MovieCandidate]:
    """
    Рекомендации TMDB (без кеша — можно добавить позже).
    """
    data = await _tmdb_get(f"/movie/{tmdb_id}/recommendations", params={"page": page})
    return _parse_candidate_list(data.get("results", []))


# -------------------------
# Cache helpers (DB)
# -------------------------

async def _get_cached(session: AsyncSession, model: Any, tmdb_id: int) -> Optional[dict[str, Any]]:
    """
    Возвращает payload из кеша, если не протух.
    """
    now = _utcnow()
    stmt = select(model).where(model.tmdb_id == tmdb_id)
    row = (await session.execute(stmt)).scalar_one_or_none()
    if row is None:
        return None
    if row.expires_at <= now:
        return None
    return row.payload


async def _upsert_cache(session: AsyncSession, model: Any, tmdb_id: int, payload: dict[str, Any]) -> None:
    """
    Upsert кеша по tmdb_id.
    """
    expires = _expires_at()
    stmt = insert(model).values(
        tmdb_id=tmdb_id,
        payload=payload,
        fetched_at=_utcnow(),
        expires_at=expires,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[model.tmdb_id],
        set_={
            "payload": payload,
            "fetched_at": _utcnow(),
            "expires_at": expires,
        },
    )
    await session.execute(stmt)
    await session.commit()


def _parse_candidate_list(results: Any) -> list[MovieCandidate]:
    candidates: list[MovieCandidate] = []
    if not isinstance(results, list):
        return candidates

    for r in results:
        if not isinstance(r, dict):
            continue
        tmdb_id = _safe_int(r.get("id"))
        title = r.get("title") or r.get("original_title")
        if not tmdb_id or not title:
            continue

        y = _extract_year(r.get("release_date"))
        genre_ids_raw = r.get("genre_ids")
        genre_ids: list[int] | None = None
        if isinstance(genre_ids_raw, list):
            genre_ids = []
            for g in genre_ids_raw:
                try:
                    genre_ids.append(int(g))
                except Exception:
                    pass

        candidates.append(
            MovieCandidate(
                tmdb_id=tmdb_id,
                title=str(title),
                year=y,
                popularity=float(r.get("popularity")) if r.get("popularity") is not None else None,
                vote_average=float(r.get("vote_average")) if r.get("vote_average") is not None else None,
                genre_ids=genre_ids,
                original_language=str(r.get("original_language")) if r.get("original_language") else None,
            )
        )
    return candidates

async def get_trending_movies(time_window: str = "day", page: int = 1) -> list[MovieCandidate]:

    if time_window not in ("day", "week"):
        time_window = "day"
    data = await _tmdb_get(f"/trending/movie/{time_window}", params={"page": page})
    return _parse_candidate_list(data.get("results", []))

async def get_movie_details_payload(session: AsyncSession, tmdb_id: int) -> dict[str, Any]:
    cached = await _get_cached(session, TmdbMovieDetailsCache, tmdb_id)
    if cached is None:
        data = await _tmdb_get(f"/movie/{tmdb_id}")
        await _upsert_cache(session, TmdbMovieDetailsCache, tmdb_id, data)
        return data
    return cached

async def get_movie_keywords_payload(session, tmdb_id: int) -> dict:
    # session оставляем в сигнатуре для совместимости (и будущего кеша),
    # но здесь можно напрямую сходить в TMDB (в тестах будет замокано).
    return await _tmdb_get(f"/movie/{tmdb_id}/keywords")


async def get_movie_similar_payload(session, tmdb_id: int) -> dict:
    # тесты ожидают сигнатуру (session, tmdb_id) без page
    return await _tmdb_get(f"/movie/{tmdb_id}/similar", params={"page": 1})


async def get_movie_recommendations_payload(session, tmdb_id: int) -> dict:
    return await _tmdb_get(f"/movie/{tmdb_id}/recommendations", params={"page": 1})
