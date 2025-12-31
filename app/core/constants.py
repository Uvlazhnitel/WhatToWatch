"""
Application-wide constants.

This module contains constants used throughout the application to avoid
magic numbers and strings scattered in the codebase.
"""

# Rate Limiting
RECOMMEND_RATE_LIMIT_SECONDS = 60

# Recommendation Defaults
DEFAULT_RECOMMENDATION_COUNT = 3
DEFAULT_RECENT_DAYS = 60
DEFAULT_SEEDS_LIMIT = 40

# Embeddings
DEFAULT_EMBED_MODEL = "text-embedding-3-small"
DEFAULT_EMBED_DIMENSIONS = 1536

# Review Validation
MAX_REVIEW_LENGTH = 5000
MAX_RATING = 5.0
MIN_RATING = 0.0

# TMDB Cache
TMDB_CACHE_TTL_DAYS = 30

# User Input Limits
MAX_MOVIE_QUERY_LENGTH = 200
MAX_AVOID_PATTERN_LENGTH = 100

# Background Jobs
MAX_EMBEDDING_JOB_ATTEMPTS = 3
EMBEDDING_JOB_BATCH_SIZE = 10

# Taste Profile
TASTE_PROFILE_REFRESH_INTERVAL = 10  # Refresh summary every N reviews

# Recommendation Strategies
STRATEGY_SAFE = "safe"
STRATEGY_ADJACENT = "adjacent"
STRATEGY_WILDCARD = "wildcard"

# Item Statuses
STATUS_SUGGESTED = "suggested"
STATUS_WATCHED = "watched"
STATUS_SKIPPED = "skipped"

# Source Types
SOURCE_LETTERBOXD = "letterboxd"
SOURCE_AGENT = "agent"
SOURCE_MANUAL = "manual"

# Pending Action Types
PENDING_MOVIE_QUERY = "awaiting_movie_query"
PENDING_MOVIE_PICK = "awaiting_movie_pick"
PENDING_REVIEW = "awaiting_review"
PENDING_RATING = "awaiting_rating"
