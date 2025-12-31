"""Unit tests for input validation."""

import pytest

from app.core.validation import (
    validate_review_text,
    validate_rating,
    validate_movie_query,
    validate_avoid_pattern,
    validate_count,
)
from app.core.exceptions import ValidationError


class TestValidateReviewText:
    """Tests for review text validation."""

    def test_valid_review(self):
        """Test that valid review text passes."""
        text = "Great movie! Highly recommended."
        assert validate_review_text(text) == text

    def test_none_review(self):
        """Test that None is accepted."""
        assert validate_review_text(None) is None

    def test_empty_review(self):
        """Test that empty review returns None."""
        assert validate_review_text("") is None
        assert validate_review_text("   ") is None

    def test_too_long_review(self):
        """Test that overly long review raises error."""
        long_text = "x" * 6000
        with pytest.raises(ValidationError) as exc_info:
            validate_review_text(long_text)
        assert "слишком длинный" in exc_info.value.user_message


class TestValidateRating:
    """Tests for rating validation."""

    def test_valid_ratings(self):
        """Test that valid ratings pass."""
        assert validate_rating(0.0) == 0.0
        assert validate_rating(2.5) == 2.5
        assert validate_rating(5.0) == 5.0

    def test_none_rating(self):
        """Test that None is accepted."""
        assert validate_rating(None) is None

    def test_negative_rating(self):
        """Test that negative rating raises error."""
        with pytest.raises(ValidationError):
            validate_rating(-1.0)

    def test_too_high_rating(self):
        """Test that rating above max raises error."""
        with pytest.raises(ValidationError):
            validate_rating(6.0)


class TestValidateMovieQuery:
    """Tests for movie query validation."""

    def test_valid_query(self):
        """Test that valid query passes."""
        assert validate_movie_query("Alien") == "Alien"
        assert validate_movie_query("  Alien 1979  ") == "Alien 1979"

    def test_empty_query(self):
        """Test that empty query raises error."""
        with pytest.raises(ValidationError):
            validate_movie_query("")
        with pytest.raises(ValidationError):
            validate_movie_query("   ")

    def test_too_long_query(self):
        """Test that overly long query raises error."""
        long_query = "x" * 250
        with pytest.raises(ValidationError):
            validate_movie_query(long_query)


class TestValidateAvoidPattern:
    """Tests for avoid pattern validation."""

    def test_valid_pattern(self):
        """Test that valid pattern passes."""
        assert validate_avoid_pattern("horror movies") == "horror movies"

    def test_empty_pattern(self):
        """Test that empty pattern raises error."""
        with pytest.raises(ValidationError):
            validate_avoid_pattern("")

    def test_too_long_pattern(self):
        """Test that overly long pattern raises error."""
        long_pattern = "x" * 150
        with pytest.raises(ValidationError):
            validate_avoid_pattern(long_pattern)


class TestValidateCount:
    """Tests for count validation."""

    def test_valid_count(self):
        """Test that valid count passes."""
        assert validate_count(5) == 5

    def test_count_at_boundaries(self):
        """Test count at min and max boundaries."""
        assert validate_count(1) == 1
        assert validate_count(20) == 20

    def test_count_below_min(self):
        """Test that count below min raises error."""
        with pytest.raises(ValidationError):
            validate_count(0)

    def test_count_above_max(self):
        """Test that count above max raises error."""
        with pytest.raises(ValidationError):
            validate_count(25)

    def test_custom_bounds(self):
        """Test custom min/max bounds."""
        assert validate_count(5, min_val=1, max_val=10) == 5
        with pytest.raises(ValidationError):
            validate_count(15, min_val=1, max_val=10)
