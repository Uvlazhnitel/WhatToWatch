from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ParsedRating:
    rating: float
    rest_text: str


def parse_rating_from_text(text: str) -> Optional[ParsedRating]:
    """
    Поддерживаем:
    - "4/5 текст"
    - "4.5/5 текст"
    - "4.5 текст"
    - "4 текст"
    - "4,5 текст"
    Возвращаем rating и оставшийся текст (без начального рейтинга).
    """
    t = text.strip()
    if not t:
        return None

    # 1) 4.5/5 или 4/5
    m = re.match(r"^\s*(\d(?:[.,]\d)?)\s*/\s*5\s*(.*)$", t)
    if m:
        raw = m.group(1).replace(",", ".")
        rating = float(raw)
        if 0 <= rating <= 5:
            return ParsedRating(rating=round(rating * 2) / 2.0, rest_text=m.group(2).strip())

    # 2) просто число в начале
    m = re.match(r"^\s*(\d(?:[.,]\d)?)\s+(.*)$", t)
    if m:
        raw = m.group(1).replace(",", ".")
        rating = float(raw)
        if 0 <= rating <= 5:
            return ParsedRating(rating=round(rating * 2) / 2.0, rest_text=m.group(2).strip())

    # 3) только число
    m = re.match(r"^\s*(\d(?:[.,]\d)?)\s*$", t)
    if m:
        raw = m.group(1).replace(",", ".")
        rating = float(raw)
        if 0 <= rating <= 5:
            return ParsedRating(rating=round(rating * 2) / 2.0, rest_text="")

    return None


def parse_title_and_year(text: str) -> tuple[str, int | None]:
    """
    Поддерживаем:
    - Alien 1979
    - Alien (1979)
    - Alien
    """
    t = text.strip()
    # (1979)
    m = re.match(r"^(.*)\((\d{4})\)\s*$", t)
    if m:
        title = m.group(1).strip()
        year = int(m.group(2))
        return title, year

    # ... 1979
    m = re.match(r"^(.*)\s+(\d{4})\s*$", t)
    if m:
        title = m.group(1).strip()
        year = int(m.group(2))
        return title, year

    return t, None
