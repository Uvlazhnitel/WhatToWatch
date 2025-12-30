from __future__ import annotations

import argparse
import asyncio
import csv
import json
import re
from dataclasses import dataclass
from datetime import datetime, date
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.db.models import User, WatchedFilm
from app.integrations.tmdb import (
    search_movie,
    get_movie_details,
    MovieCandidate,
    TMDBError,
)

# ----------------------------
# Helpers: parsing / normalize
# ----------------------------

_HALF_SYMBOL = "½"


def normalize_title(s: str) -> str:
    """
    Нормализация заголовка для сравнения:
    - lower
    - убираем пунктуацию
    - схлопываем пробелы
    """
    s = s.strip().lower()
    s = re.sub(r"[’'`]", "", s)
    s = re.sub(r"[^a-z0-9а-яё\s]", " ", s, flags=re.IGNORECASE)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def parse_year(value: Any) -> Optional[int]:
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    if s.isdigit() and len(s) == 4:
        y = int(s)
        if 1870 <= y <= 2100:
            return y
    return None


def parse_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None

    # Частые форматы:
    # 2024-01-31
    # 31/01/2024
    # 01/31/2024
    # 31.01.2024
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d.%m.%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass

    # Иногда бывает "2024-01-31 00:00:00"
    try:
        return datetime.fromisoformat(s).date()
    except ValueError:
        return None


def parse_rating(value: Any) -> Optional[float]:
    """
    Letterboxd обычно 0..5, шаг 0.5.
    Поддержим варианты:
    - "4.5"
    - "4"
    - "4½"
    - ""
    """
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None

    # "4½"
    if _HALF_SYMBOL in s:
        s = s.replace(_HALF_SYMBOL, ".5")

    # Иногда rating может быть "4.0" — ок
    try:
        r = float(s)
    except ValueError:
        return None

    # Нормализуем к шагу 0.5 (аккуратно)
    # Например 3.7 -> 3.5, 3.8 -> 4.0
    r = round(r * 2) / 2.0

    if 0.0 <= r <= 5.0:
        return r
    return None


def pick_first(row: dict[str, Any], possible_keys: list[str]) -> Optional[str]:
    """
    Ищем колонку по нескольким вариантам названий (case-insensitive).
    """
    lower_map = {k.lower().strip(): k for k in row.keys()}
    for key in possible_keys:
        actual = lower_map.get(key.lower())
        if actual is not None:
            val = row.get(actual)
            if val is None:
                return None
            s = str(val).strip()
            return s if s else None
    return None


# ----------------------------
# Candidate selection logic
# ----------------------------

@dataclass(frozen=True)
class SelectionResult:
    chosen: Optional[MovieCandidate]
    confidence: float
    reason: str
    top_candidates: list[MovieCandidate]


def score_candidate(c: MovieCandidate, want_title: str, want_year: Optional[int]) -> float:
    """
    Простая, но рабочая эвристика:
    - точное совпадение нормализованного title => большой бонус
    - совпадение года => большой бонус
    - популярность/vote_average => маленький бонус (чтобы вытягивать очевидные варианты)
    """
    score = 0.0
    if normalize_title(c.title) == normalize_title(want_title):
        score += 5.0
    else:
        # частичное совпадение
        if normalize_title(want_title) in normalize_title(c.title) or normalize_title(c.title) in normalize_title(want_title):
            score += 2.0

    if want_year is not None and c.year is not None:
        if c.year == want_year:
            score += 4.0
        elif abs(c.year - want_year) == 1:
            score += 1.5

    if c.vote_average is not None:
        score += min(1.0, c.vote_average / 10.0)  # 0..1
    if c.popularity is not None:
        score += min(1.0, c.popularity / 100.0)   # 0..1

    return score


def choose_best_candidate(
    candidates: list[MovieCandidate],
    want_title: str,
    want_year: Optional[int],
) -> SelectionResult:
    if not candidates:
        return SelectionResult(chosen=None, confidence=0.0, reason="no_candidates", top_candidates=[])

    scored = [(c, score_candidate(c, want_title, want_year)) for c in candidates]
    scored.sort(key=lambda x: x[1], reverse=True)

    top_candidates = [c for c, _ in scored[:5]]
    best, best_score = scored[0]
    second_score = scored[1][1] if len(scored) > 1 else -999.0

    # Уверенность: разница между первым и вторым + "насколько высокий" сам score
    margin = best_score - second_score
    confidence = 0.0

    # Если есть строгое совпадение title+year — почти всегда ок
    strict_match = (
        normalize_title(best.title) == normalize_title(want_title)
        and (want_year is None or best.year == want_year)
    )

    if strict_match and best_score >= 8.5:
        confidence = 0.95
        return SelectionResult(best, confidence, "strict_title_year_match", top_candidates)

    if best_score >= 8.0 and margin >= 2.5:
        confidence = 0.85
        return SelectionResult(best, confidence, "high_score_and_margin", top_candidates)

    if best_score >= 7.0 and margin >= 3.5:
        confidence = 0.75
        return SelectionResult(best, confidence, "ok_score_big_margin", top_candidates)

    # Иначе считаем неоднозначным
    confidence = max(0.2, min(0.7, best_score / 10.0))
    return SelectionResult(None, confidence, "ambiguous", top_candidates)


# ----------------------------
# DB helpers
# ----------------------------

async def get_or_create_user(session: AsyncSession, telegram_id: int) -> User:
    user = (await session.execute(select(User).where(User.telegram_id == telegram_id))).scalar_one_or_none()
    if user is None:
        user = User(telegram_id=telegram_id)
        session.add(user)
        await session.commit()
        await session.refresh(user)
    return user


async def watched_exists(session: AsyncSession, user_id: int, tmdb_id: int, watched_date: Optional[date]) -> bool:
    """
    Дедуп на уровне кода:
    - если есть запись с тем же user_id+tmdb_id и той же watched_date (или обе None)
    """
    stmt = select(WatchedFilm.id).where(
        WatchedFilm.user_id == user_id,
        WatchedFilm.tmdb_id == tmdb_id,
    )
    if watched_date is None:
        stmt = stmt.where(WatchedFilm.watched_date.is_(None))
    else:
        stmt = stmt.where(WatchedFilm.watched_date == watched_date)

    existing = (await session.execute(stmt)).scalar_one_or_none()
    return existing is not None


async def insert_watched(
    session: AsyncSession,
    user_id: int,
    tmdb_id: int,
    title: str,
    year: Optional[int],
    rating: Optional[float],
    review: Optional[str],
    watched_date: Optional[date],
    source: str = "letterboxd",
) -> None:
    if await watched_exists(session, user_id, tmdb_id, watched_date):
        return

    wf = WatchedFilm(
        user_id=user_id,
        tmdb_id=tmdb_id,
        title=title,
        year=year,
        your_rating=rating,
        your_review=review,
        watched_date=watched_date,
        source=source,
    )
    session.add(wf)
    await session.commit()


# ----------------------------
# CSV Import
# ----------------------------

def extract_fields(row: dict[str, Any]) -> tuple[Optional[str], Optional[int], Optional[float], Optional[str], Optional[date]]:
    """
    Пытаемся поддержать разные заголовки:
    - title: Name / Film Name / Title
    - year: Year
    - rating: Rating
    - review: Review / Rewatch? (нет) / Comment
    - watched_date: Watched Date / Date / Diary Date
    """
    title = pick_first(row, ["Name", "Film Name", "Title", "Film", "Movie", "Movie Title"])
    year = parse_year(pick_first(row, ["Year", "Release Year"]))
    rating = parse_rating(pick_first(row, ["Rating", "Your Rating", "Stars"]))
    review = pick_first(row, ["Review", "Your Review", "Comment", "Notes", "Text"])
    watched_date = parse_date(pick_first(row, ["Watched Date", "Date", "Diary Date", "Watched", "Watched On"]))
    return title, year, rating, review, watched_date


def write_unresolved_header(path: Path) -> None:
    if path.exists():
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "row_index",
                "title",
                "year",
                "watched_date",
                "rating",
                "review",
                "reason",
                "candidates_json",
                "chosen_tmdb_id",
            ],
        )
        w.writeheader()


def append_unresolved(path: Path, record: dict[str, Any]) -> None:
    write_unresolved_header(path)
    with path.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(record.keys()))
        w.writerow(record)


def load_overrides(path: Optional[Path]) -> dict[tuple[str, Optional[int]], int]:
    """
    overrides CSV формат:
    title,year,tmdb_id
    """
    if path is None or not path.exists():
        return {}

    mapping: dict[tuple[str, Optional[int]], int] = {}
    with path.open("r", newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            t = (row.get("title") or "").strip()
            y = parse_year(row.get("year"))
            tmdb = row.get("tmdb_id")
            if not t or not tmdb:
                continue
            try:
                tmdb_id = int(tmdb)
            except ValueError:
                continue
            mapping[(normalize_title(t), y)] = tmdb_id
    return mapping


async def import_csv(
    csv_path: Path,
    telegram_id: int,
    unresolved_out: Path,
    overrides_path: Optional[Path],
    limit: Optional[int],
    sleep_s: float,
    dry_run: bool,
) -> None:
    overrides = load_overrides(overrides_path)

    async with AsyncSessionLocal() as session:
        user = await get_or_create_user(session, telegram_id)
        user_id = user.id

    # Кеш поиска, чтобы не бомбить TMDB одинаковыми запросами
    search_cache: dict[tuple[str, Optional[int]], list[MovieCandidate]] = {}

    imported = 0
    unresolved = 0
    processed = 0

    with csv_path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for idx, row in enumerate(reader, start=1):
            if limit is not None and processed >= limit:
                break
            processed += 1

            title, year, rating, review, watched_date = extract_fields(row)

            if not title:
                # Нечего импортировать
                continue

            # 1) Overrides (ручная карта) — абсолютный приоритет
            override_key = (normalize_title(title), year)
            if override_key in overrides:
                chosen_tmdb_id = overrides[override_key]
                confidence = 1.0
                reason = "override"
                top_candidates = []
            else:
                # 2) TMDB search
                cache_key = (title, year)
                if cache_key in search_cache:
                    candidates = search_cache[cache_key]
                else:
                    try:
                        candidates = await search_movie(query=title, year=year)
                    except TMDBError as e:
                        append_unresolved(
                            unresolved_out,
                            {
                                "row_index": idx,
                                "title": title,
                                "year": year or "",
                                "watched_date": watched_date.isoformat() if watched_date else "",
                                "rating": rating if rating is not None else "",
                                "review": (review or "")[:2000],
                                "reason": f"tmdb_error:{str(e)}",
                                "candidates_json": "[]",
                                "chosen_tmdb_id": "",
                            },
                        )
                        unresolved += 1
                        continue

                    search_cache[cache_key] = candidates

                sel = choose_best_candidate(candidates, title, year)
                if sel.chosen is None:
                    append_unresolved(
                        unresolved_out,
                        {
                            "row_index": idx,
                            "title": title,
                            "year": year or "",
                            "watched_date": watched_date.isoformat() if watched_date else "",
                            "rating": rating if rating is not None else "",
                            "review": (review or "")[:2000],
                            "reason": sel.reason,
                            "candidates_json": json.dumps([c.__dict__ for c in sel.top_candidates], ensure_ascii=False),
                            "chosen_tmdb_id": "",
                        },
                    )
                    unresolved += 1
                    continue

                chosen_tmdb_id = sel.chosen.tmdb_id
                confidence = sel.confidence
                reason = sel.reason
                top_candidates = sel.top_candidates

            # 3) Подтянуть канонические details (кешируется таблицей из этапа 3)
            if dry_run:
                print(f"[DRY RUN] row={idx} -> tmdb_id={chosen_tmdb_id} title='{title}' year={year} conf={confidence:.2f} reason={reason}")
                imported += 1
                continue

            async with AsyncSessionLocal() as session:
                details = await get_movie_details(session, chosen_tmdb_id)

                # 4) Insert watched film (dedupe)
                await insert_watched(
                    session=session,
                    user_id=user_id,
                    tmdb_id=chosen_tmdb_id,
                    title=details.title or title,
                    year=details.year or year,
                    rating=rating,
                    review=review,
                    watched_date=watched_date,
                    source="letterboxd",
                )

            imported += 1

            # 5) Небольшая пауза, чтобы не упереться в лимиты TMDB
            if sleep_s > 0:
                await asyncio.sleep(sleep_s)

            if imported % 50 == 0:
                print(f"Progress: processed={processed}, imported={imported}, unresolved={unresolved}")

    print("\n=== Import finished ===")
    print(f"Processed:  {processed}")
    print(f"Imported:   {imported}")
    print(f"Unresolved: {unresolved}")
    if unresolved > 0:
        print(f"Unresolved saved to: {unresolved_out}")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Import Letterboxd CSV into watched_films with TMDB matching.")
    p.add_argument("--csv", required=True, help="Path to Letterboxd CSV (e.g. diary.csv)")
    p.add_argument("--telegram-id", required=True, type=int, help="Your Telegram numeric id (used to find/create user)")
    p.add_argument("--unresolved-out", default="unresolved.csv", help="Where to save unresolved rows")
    p.add_argument("--overrides", default=None, help="Optional overrides CSV: title,year,tmdb_id")
    p.add_argument("--limit", type=int, default=None, help="Limit rows for testing")
    p.add_argument("--sleep", type=float, default=0.15, help="Sleep between TMDB calls (seconds)")
    p.add_argument("--dry-run", action="store_true", help="Do not write to DB, only print what would happen")
    return p.parse_args()


async def main() -> None:
    args = parse_args()
    csv_path = Path(args.csv).expanduser().resolve()
    if not csv_path.exists():
        raise SystemExit(f"CSV not found: {csv_path}")

    unresolved_out = Path(args.unresolved_out).expanduser().resolve()
    overrides_path = Path(args.overrides).expanduser().resolve() if args.overrides else None

    await import_csv(
        csv_path=csv_path,
        telegram_id=args.telegram_id,
        unresolved_out=unresolved_out,
        overrides_path=overrides_path,
        limit=args.limit,
        sleep_s=args.sleep,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    asyncio.run(main())
