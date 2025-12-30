"""
Embedding Text Builders

Functions to construct text representations for embedding generation.
These functions format data into natural language text that can be embedded
to capture semantic meaning.

Two main builders:
- build_review_text: Formats user reviews with ratings
- build_film_meta_text: Formats movie metadata (title, genres, keywords, overview)

The generated text is optimized for semantic similarity search, focusing on
the aspects that matter most for recommendations.
"""

from __future__ import annotations

from app.integrations.tmdb import get_movie_details, get_movie_keywords


async def build_review_text(title: str, year: int | None, rating: float | None, review: str | None) -> str:
    parts = []
    parts.append(f"Movie: {title} ({year})" if year else f"Movie: {title}")
    if rating is not None:
        parts.append(f"User rating: {rating}/5")
    if review and review.strip():
        parts.append("User review:\n" + review.strip())
    return "\n".join(parts).strip()


async def build_film_meta_text(session, tmdb_id: int) -> str:
    details = await get_movie_details(session, tmdb_id)
    keywords = await get_movie_keywords(session, tmdb_id)

    parts = []
    parts.append(f"Title: {details.title} ({details.year})" if details.year else f"Title: {details.title}")
    if details.genres:
        parts.append("Genres: " + ", ".join(details.genres))
    if keywords:
        parts.append("Keywords: " + ", ".join(keywords[:20]))
    if details.runtime:
        parts.append(f"Runtime: {details.runtime} min")
    if details.overview:
        parts.append("Overview:\n" + details.overview.strip())

    return "\n".join(parts).strip()
