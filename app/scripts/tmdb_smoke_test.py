import asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.integrations.tmdb import search_movie, get_movie_details, get_movie_keywords


async def main() -> None:
    query = "Alien"
    year = 1979

    candidates = await search_movie(query=query, year=year)
    if not candidates:
        raise RuntimeError("No candidates found. Check TMDB key / query.")

    # Обычно первый кандидат — нужный, но можно дополнительно фильтровать по year
    best = None
    for c in candidates:
        if c.year == year:
            best = c
            break
    best = best or candidates[0]

    print(f"Best candidate: tmdb_id={best.tmdb_id}, title={best.title}, year={best.year}")

    async with AsyncSessionLocal() as session:  # type: AsyncSession
        details = await get_movie_details(session, best.tmdb_id)
        keywords = await get_movie_keywords(session, best.tmdb_id)

    print("Details:")
    print(f"  title: {details.title}")
    print(f"  year: {details.year}")
    print(f"  runtime: {details.runtime}")
    print(f"  genres: {details.genres}")
    print(f"  overview: {(details.overview or '')[:180]}...")

    print("Keywords (first 15):", keywords[:15])


if __name__ == "__main__":
    asyncio.run(main())
