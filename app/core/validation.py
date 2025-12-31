"""
Input validation utilities.

This module provides validation functions for user inputs to ensure
data quality and security.
"""

from app.core.constants import (
    MAX_REVIEW_LENGTH,
    MAX_RATING,
    MIN_RATING,
    MAX_MOVIE_QUERY_LENGTH,
    MAX_AVOID_PATTERN_LENGTH,
)
from app.core.exceptions import ValidationError


def validate_review_text(text: str | None) -> str | None:
    """
    Validate review text length.

    Args:
        text: Review text to validate

    Returns:
        Validated review text or None if input is None

    Raises:
        ValidationError: If review is too long
    """
    if text is None:
        return None

    text = text.strip()
    if not text:
        return None

    if len(text) > MAX_REVIEW_LENGTH:
        raise ValidationError(
            f"Review is too long ({len(text)} chars)",
            user_message=f"Отзыв слишком длинный (максимум {MAX_REVIEW_LENGTH} символов)",
        )

    return text


def validate_rating(rating: float | None) -> float | None:
    """
    Validate rating value.

    Args:
        rating: Rating value to validate

    Returns:
        Validated rating or None if input is None

    Raises:
        ValidationError: If rating is out of range
    """
    if rating is None:
        return None

    if not MIN_RATING <= rating <= MAX_RATING:
        raise ValidationError(
            f"Rating {rating} is out of range",
            user_message=f"Оценка должна быть от {MIN_RATING} до {MAX_RATING}",
        )

    return rating


def validate_movie_query(query: str) -> str:
    """
    Validate movie search query.

    Args:
        query: Search query to validate

    Returns:
        Validated query

    Raises:
        ValidationError: If query is invalid
    """
    query = query.strip()

    if not query:
        raise ValidationError(
            "Empty movie query", user_message="Название фильма не может быть пустым"
        )

    if len(query) > MAX_MOVIE_QUERY_LENGTH:
        raise ValidationError(
            f"Movie query too long ({len(query)} chars)",
            user_message=f"Запрос слишком длинный (максимум {MAX_MOVIE_QUERY_LENGTH} символов)",
        )

    return query


def validate_avoid_pattern(pattern: str) -> str:
    """
    Validate avoidance pattern text.

    Args:
        pattern: Pattern text to validate

    Returns:
        Validated pattern

    Raises:
        ValidationError: If pattern is invalid
    """
    pattern = pattern.strip()

    if not pattern:
        raise ValidationError(
            "Empty avoid pattern", user_message="Описание темы не может быть пустым"
        )

    if len(pattern) > MAX_AVOID_PATTERN_LENGTH:
        raise ValidationError(
            f"Avoid pattern too long ({len(pattern)} chars)",
            user_message=f"Описание слишком длинное (максимум {MAX_AVOID_PATTERN_LENGTH} символов)",
        )

    return pattern


def validate_count(count: int, min_val: int = 1, max_val: int = 20) -> int:
    """
    Validate count parameter.

    Args:
        count: Count value to validate
        min_val: Minimum allowed value
        max_val: Maximum allowed value

    Returns:
        Validated count

    Raises:
        ValidationError: If count is out of range
    """
    if not min_val <= count <= max_val:
        raise ValidationError(
            f"Count {count} is out of range [{min_val}, {max_val}]",
            user_message=f"Количество должно быть от {min_val} до {max_val}",
        )

    return count
