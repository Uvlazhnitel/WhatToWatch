"""Unit tests for custom exceptions."""

import pytest

from app.core.exceptions import (
    WhatToWatchError,
    ValidationError,
    RateLimitError,
    InsufficientDataError,
)


class TestWhatToWatchError:
    """Tests for base exception."""

    def test_basic_error(self):
        """Test basic error creation."""
        error = WhatToWatchError("Internal error")
        assert str(error) == "Internal error"
        assert error.user_message == "Internal error"

    def test_error_with_user_message(self):
        """Test error with separate user message."""
        error = WhatToWatchError("Internal error", user_message="User friendly message")
        assert str(error) == "Internal error"
        assert error.user_message == "User friendly message"


class TestRateLimitError:
    """Tests for rate limit error."""

    def test_rate_limit_error(self):
        """Test rate limit error with retry time."""
        error = RateLimitError(retry_after=30)
        assert error.retry_after == 30
        assert "30 seconds" in error.user_message


class TestInsufficientDataError:
    """Tests for insufficient data error."""

    def test_insufficient_data_error(self):
        """Test insufficient data error with counts."""
        error = InsufficientDataError("Not enough ratings", required=10, actual=3)
        assert error.required == 10
        assert error.actual == 3
        assert "10" in error.user_message
        assert "3" in error.user_message
