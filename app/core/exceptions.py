"""
Custom exception hierarchy for the WhatToWatch application.

This module defines all custom exceptions to provide better error handling
and more informative error messages throughout the application.
"""


class WhatToWatchError(Exception):
    """Base exception for all WhatToWatch errors."""

    def __init__(self, message: str, user_message: str | None = None):
        """
        Initialize exception.

        Args:
            message: Internal error message for logging
            user_message: User-friendly message for display (optional)
        """
        super().__init__(message)
        self.user_message = user_message or message


class ConfigurationError(WhatToWatchError):
    """Raised when application configuration is invalid."""

    pass


class ValidationError(WhatToWatchError):
    """Raised when user input validation fails."""

    pass


class TMDBError(WhatToWatchError):
    """Raised when TMDB API operations fail."""

    pass


class OpenAIError(WhatToWatchError):
    """Raised when OpenAI API operations fail."""

    pass


class DatabaseError(WhatToWatchError):
    """Raised when database operations fail."""

    pass


class UserNotFoundError(WhatToWatchError):
    """Raised when a user is not found."""

    pass


class MovieNotFoundError(WhatToWatchError):
    """Raised when a movie is not found."""

    pass


class InsufficientDataError(WhatToWatchError):
    """Raised when there's insufficient data for an operation."""

    def __init__(self, message: str, required: int, actual: int):
        super().__init__(
            message, user_message=f"Need at least {required} items, but only have {actual}"
        )
        self.required = required
        self.actual = actual


class RateLimitError(WhatToWatchError):
    """Raised when rate limit is exceeded."""

    def __init__(self, retry_after: int):
        super().__init__(
            f"Rate limit exceeded, retry after {retry_after} seconds",
            user_message=f"Please wait {retry_after} seconds before trying again",
        )
        self.retry_after = retry_after


class EmbeddingError(WhatToWatchError):
    """Raised when embedding operations fail."""

    pass


class RecommendationError(WhatToWatchError):
    """Raised when recommendation generation fails."""

    pass
