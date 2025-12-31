"""Unit tests for constants."""

from app.core import constants


class TestConstants:
    """Test that constants are defined and have expected types."""

    def test_rate_limiting_constants(self):
        """Test rate limiting constants."""
        assert isinstance(constants.RECOMMEND_RATE_LIMIT_SECONDS, int)
        assert constants.RECOMMEND_RATE_LIMIT_SECONDS > 0

    def test_recommendation_constants(self):
        """Test recommendation-related constants."""
        assert isinstance(constants.DEFAULT_RECOMMENDATION_COUNT, int)
        assert constants.DEFAULT_RECOMMENDATION_COUNT > 0
        assert isinstance(constants.DEFAULT_RECENT_DAYS, int)
        assert isinstance(constants.DEFAULT_SEEDS_LIMIT, int)

    def test_validation_constants(self):
        """Test validation constants."""
        assert isinstance(constants.MAX_REVIEW_LENGTH, int)
        assert constants.MAX_REVIEW_LENGTH > 0
        assert isinstance(constants.MAX_RATING, float)
        assert isinstance(constants.MIN_RATING, float)
        assert constants.MIN_RATING < constants.MAX_RATING

    def test_strategy_constants(self):
        """Test strategy constants are strings."""
        assert isinstance(constants.STRATEGY_SAFE, str)
        assert isinstance(constants.STRATEGY_ADJACENT, str)
        assert isinstance(constants.STRATEGY_WILDCARD, str)

    def test_status_constants(self):
        """Test status constants are strings."""
        assert isinstance(constants.STATUS_SUGGESTED, str)
        assert isinstance(constants.STATUS_WATCHED, str)
        assert isinstance(constants.STATUS_SKIPPED, str)
