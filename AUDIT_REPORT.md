# WhatToWatch Repository Audit Report
## Comprehensive Code Review & Refactoring Recommendations

**Date**: December 31, 2025  
**Reviewer**: Senior Software Engineer  
**Repository**: Uvlazhnitel/WhatToWatch  
**Language**: Python  
**Framework**: Telegram Bot (Aiogram), FastAPI, SQLAlchemy, PostgreSQL with pgvector

---

## Executive Summary

WhatToWatch is a Telegram bot-based movie recommendation system that uses:
- **TMDB API** for movie data
- **PostgreSQL with pgvector** for embeddings storage
- **OpenAI API** for text generation and embeddings
- **Vector-based recommendations** combined with collaborative filtering

**Current State**: The codebase is functional but has significant issues that will impede long-term maintenance, onboarding, and scaling.

**Lines of Code**: ~3,843 Python LOC across 59 files  
**Test Coverage**: Minimal (~498 LOC of tests for ~3,843 LOC of application code)

---

## 1. Architecture & Design

### 🔴 HIGH PRIORITY ISSUES

#### 1.1 Missing Dependency Management
**Problem**: No `requirements.txt`, `pyproject.toml`, or `Pipfile` exists.  
**Impact**: 
- Cannot install dependencies
- No version pinning → reproducibility issues
- Onboarding impossible without guessing packages
- CI/CD cannot be configured

**Evidence**:
```bash
$ find . -name "requirements*.txt" -o -name "pyproject.toml" -o -name "setup.py"
# No results
```

**Required Dependencies** (inferred from imports):
- aiogram (Telegram bot framework)
- fastapi
- sqlalchemy[asyncio]
- asyncpg
- psycopg (for sync operations)
- pgvector
- httpx
- openai
- pydantic-settings
- alembic
- pytest
- pytest-asyncio

**Fix**:
```bash
# Create requirements.txt with pinned versions
aiogram==3.14.0
fastapi==0.115.0
uvicorn[standard]==0.31.0
sqlalchemy[asyncio]==2.0.36
asyncpg==0.30.0
psycopg[binary]==3.2.3
pgvector==0.3.5
httpx==0.27.2
openai==1.54.3
pydantic-settings==2.6.1
alembic==1.13.3
pytest==8.3.3
pytest-asyncio==0.24.0
```

#### 1.2 Empty Dockerfile
**Problem**: `Dockerfile` exists but is completely empty (0 bytes).  
**Impact**: Cannot containerize application, breaks deployment.

**Fix**: Create proper multi-stage Dockerfile:
```dockerfile
FROM python:3.12-slim as builder

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM python:3.12-slim
WORKDIR /app
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY . .

ENV PYTHONUNBUFFERED=1
CMD ["python", "-m", "app.bot.run"]
```

#### 1.3 Inadequate README
**Problem**: `README.md` only contains duplicate title "# WhatToWatch" (3 lines).  
**Impact**: Zero documentation for setup, usage, architecture, or contribution.

**Fix**: Create comprehensive README with:
- Project description and features
- Architecture diagram
- Setup instructions
- Environment configuration
- Running the bot/API
- Testing guide
- Contributing guidelines

#### 1.4 Missing CI/CD Configuration
**Problem**: No `.github/workflows/` directory or CI configuration.  
**Impact**: 
- No automated testing
- No linting enforcement
- No deployment automation
- Quality degradation over time

**Fix**: Add GitHub Actions workflows for:
- Linting (ruff, black, mypy)
- Testing (pytest)
- Security scanning (bandit, safety)
- Dependency updates (dependabot)

#### 1.5 Migration History Issues
**Problem**: Multiple duplicate migrations for `command_rate_limits`:
- `9422d49813ae_add_command_rate_limits.py`
- `5e0353c68b30_add_command_rate_limits.py`
- `421de244c013_add_command_rate_limits.py`
- `f999b47ff238_ensure_command_rate_limits_exists.py`
- Plus a merge migration `10684b2d1e3b_merge_heads.py`

**Impact**: Confusing migration history, potential deployment issues.

**Fix**: Clean up migration history:
1. Squash duplicate migrations
2. Document why merges occurred
3. Add migration validation in CI

#### 1.6 Inconsistent Configuration
**Problem**: `.env.example` is missing OpenAI configuration that exists in `app/core/config.py`.

**Evidence**:
```python
# In config.py but NOT in .env.example:
openai_api_key: str
openai_embed_model: str = "text-embedding-3-small"
openai_embed_dimensions: int = 1536
openai_timeout_secs: int = 30
openai_text_model: str = "gpt-4o-mini"
openai_text_temperature: float = 0.35
openai_text_max_output_tokens: int = 350
```

**Fix**: Update `.env.example` to include all configuration options with documentation.

### 🟡 MEDIUM PRIORITY ISSUES

#### 1.7 Monolithic Router File
**Problem**: `app/bot/router.py` is 609 lines with multiple concerns:
- Command handlers
- Callback handlers
- State management
- Business logic
- Repository calls
- LLM integration

**Impact**: Hard to maintain, test, and understand.

**Fix**: Split into separate modules:
```
app/bot/
  handlers/
    commands.py     # /start, /cancel, /review, /recommend
    callbacks.py    # Button click handlers
    messages.py     # Text message handling
  flows/
    review_flow.py  # Review creation flow
    recommend_flow.py  # Recommendation flow
  router.py         # Main router assembly
```

#### 1.8 Missing Error Handling Strategy
**Problem**: Inconsistent error handling across the codebase:
- Some places catch `TMDBError`, others don't
- No global error handler for the bot
- No logging of errors
- No user-friendly error messages

**Example from router.py**:
```python
try:
    candidates = await search_movie(query=title, year=year)
except TMDBError as e:
    await message.answer(f"TMDB ошибка: {e}")  # Exposes internal errors
    return
```

**Fix**: 
1. Create error hierarchy
2. Add global error handler
3. Log all errors with context
4. Return user-friendly messages

#### 1.9 Separation of Concerns Violations
**Problem**: Business logic mixed with infrastructure:
- `_save_review()` in `router.py` does DB operations, taste profile updates, AND LLM jobs
- Repositories sometimes contain business logic
- No clear service layer

**Fix**: Introduce service layer:
```
app/services/
  review_service.py     # Existing but underutilized
  recommendation_service.py
  taste_profile_service.py
  embedding_service.py
```

---

## 2. Code Quality

### 🔴 HIGH PRIORITY ISSUES

#### 2.1 No Type Checking Configuration
**Problem**: No `mypy.ini` or type checking in development process.  
**Impact**: Type hints exist but are not validated, leading to runtime errors.

**Fix**: Add `mypy.ini`:
```ini
[mypy]
python_version = 3.12
strict = True
warn_return_any = True
warn_unused_configs = True
disallow_untyped_defs = True
```

#### 2.2 No Linting Configuration
**Problem**: No `.flake8`, `.pylintrc`, or `ruff.toml`.  
**Impact**: Inconsistent code style, potential bugs go undetected.

**Fix**: Add `ruff.toml`:
```toml
[tool.ruff]
line-length = 120
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP", "B", "C4"]
ignore = ["E501"]  # Line too long (handled by formatter)
```

#### 2.3 Duplicate Imports
**Problem**: Multiple files import same modules redundantly.

**Example from `app/bot/router.py`**:
```python
from app.db.models import TasteProfile  # Line 15
# ... 11 lines later
from app.db.models import TasteProfile, WatchedFilm, TextEmbedding  # Line 26
```

**Example from `app/recommender/v0.py`**:
```python
import app.integrations.tmdb as tmdb  # Line 19
# ... 65 lines later
from app.integrations import tmdb  # Line 85
from app.integrations.tmdb import MovieCandidate, TMDBError  # Line 86
```

**Impact**: Confusing, harder to maintain, suggests rushed development.

**Fix**: Clean up imports at the top of each file.

#### 2.4 Magic Numbers and Strings
**Problem**: Hard-coded values throughout codebase without constants.

**Examples**:
```python
# In router.py line 124
allowed, retry = await check_and_touch(session, user.id, "recommend", interval_seconds=60)

# In tmdb.py line 16
CACHE_TTL_DAYS = 30  # Good!

# In router.py line 262
count=3,  # Should be constant
recent_days=60,  # Should be constant
seeds_limit=40,  # Should be constant
```

**Fix**: Create constants module:
```python
# app/core/constants.py
RECOMMEND_RATE_LIMIT_SECONDS = 60
DEFAULT_RECOMMENDATION_COUNT = 3
RECENT_RECOMMENDATIONS_DAYS = 60
SEED_MOVIES_LIMIT = 40
```

#### 2.5 Long Functions
**Problem**: Several functions exceed 100 lines.

**Examples**:
- `cmd_recommend()` in `router.py`: ~140 lines
- `_save_review()` in `router.py`: ~105 lines
- `recommend_v1()` in `recommender/v1.py`: ~260 lines

**Impact**: Hard to test, understand, and maintain.

**Fix**: Extract smaller functions following Single Responsibility Principle.

### 🟡 MEDIUM PRIORITY ISSUES

#### 2.6 Inconsistent Naming Conventions
**Problem**: Mixed naming styles:
- `get_or_create_user` (snake_case with underscore separator)
- `upsert_watched` (database operation verb)
- `set_item_status` (setter verb)
- `check_and_touch` (multiple operations)

**Fix**: Establish naming conventions:
- Queries: `get_`, `find_`, `list_`
- Mutations: `create_`, `update_`, `delete_`, `upsert_`
- Combinations: Split into separate functions

#### 2.7 Missing Docstrings
**Problem**: Most functions lack docstrings.

**Evidence**: Only ~10% of functions have docstrings explaining parameters, return values, and side effects.

**Fix**: Add comprehensive docstrings:
```python
async def create_recommendation(
    session: AsyncSession, 
    user_id: int, 
    context: dict
) -> AgentRecommendation:
    """
    Create a new recommendation record for a user.
    
    Args:
        session: Active database session
        user_id: ID of the user receiving recommendations
        context: Metadata about the recommendation (mode, count, etc.)
        
    Returns:
        Created AgentRecommendation instance with ID populated
        
    Raises:
        SQLAlchemyError: If database operation fails
    """
```

#### 2.8 Commented-Out Code
**Problem**: Russian comments mixed with code, some English.

**Example from `models.py`**:
```python
# 0..5, допускаем шаг 0.5 (Numeric(2,1) подходит: 0.0..9.9, но мы ограничим CHECK)
your_rating: Mapped[Optional[float]] = mapped_column(Numeric(2, 1), nullable=True)
```

**Fix**: 
1. Decide on comment language (English recommended for international team)
2. Remove obvious comments
3. Keep only necessary explanations

#### 2.9 Complex Boolean Expressions
**Problem**: Difficult to read conditional logic.

**Example from `v1.py`**:
```python
if not release_date or not isinstance(release_date, str) or len(release_date) < 4:
    return None
if not release_date[:4].isdigit():
    return None
```

**Fix**: Extract to named functions:
```python
def is_valid_release_date(release_date: str | None) -> bool:
    if not release_date or not isinstance(release_date, str):
        return False
    if len(release_date) < 4:
        return False
    return release_date[:4].isdigit()
```

---

## 3. Missing or Redundant Elements

### 🔴 HIGH PRIORITY MISSING

#### 3.1 Requirements File
Already covered in 1.1 - **CRITICAL**

#### 3.2 Proper Dockerfile
Already covered in 1.2 - **CRITICAL**

#### 3.3 README Documentation
Already covered in 1.3 - **CRITICAL**

#### 3.4 CI/CD Pipeline
Already covered in 1.4 - **CRITICAL**

#### 3.5 Environment Validation
**Problem**: No validation that required environment variables are set before app starts.

**Fix**: Add validation in `config.py`:
```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url_async: str
    database_url_sync: str
    tmdb_api_key: str
    telegram_bot_token: str
    openai_api_key: str
    
    @model_validator(mode='after')
    def validate_required_fields(self) -> 'Settings':
        if self.tmdb_api_key == "your_tmdb_api_key_here":
            raise ValueError("TMDB_API_KEY must be set")
        if self.telegram_bot_token == "your_bot_token_here":
            raise ValueError("TELEGRAM_BOT_TOKEN must be set")
        return self
```

#### 3.6 Logging Configuration
**Problem**: `app/core/logging.py` exists but is not used anywhere.

**Fix**: Configure structured logging and use throughout application:
```python
import logging
import sys

def setup_logging(level: str = "INFO"):
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)]
    )
```

#### 3.7 Health Check Endpoints
**Problem**: API has no health check or readiness endpoints.

**Fix**: Add to `app/api/main.py`:
```python
@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/ready")
async def ready():
    # Check database connection
    return {"status": "ready", "database": "connected"}
```

### 🟡 MEDIUM PRIORITY MISSING

#### 3.8 Database Seed Data
**Problem**: No seed data for development/testing.

**Fix**: Add `scripts/seed_data.py` for local development.

#### 3.9 Migration Testing
**Problem**: No tests validating migrations work both up and down.

**Fix**: Add migration tests in `tests/test_migrations.py`.

#### 3.10 API Documentation
**Problem**: FastAPI is present but not configured with docs.

**Fix**: Configure OpenAPI docs in `main.py`:
```python
app = FastAPI(
    title="WhatToWatch API",
    description="Movie recommendation service",
    version="1.0.0"
)
```

### 🟢 LOW PRIORITY REDUNDANT

#### 3.11 Duplicate Migration Files
Already covered in 1.5

#### 3.12 Unused Scripts
**Problem**: `scripts/snapshot_db.sh.save` looks like a backup file.

**Fix**: Delete `.save` files and add to `.gitignore`.

#### 3.13 Test Directory Spacing Issue
**Problem**: `tests/` has directory named `' fakes'` (with leading space).

**Evidence**:
```bash
$ ls -la tests/
drwxrwxr-x 2 runner runner 4096 Dec 31 00:26 ' fakes'
drwxrwxr-x 2 runner runner 4096 Dec 31 00:26  fakes
```

**Impact**: Two directories for fakes, causing confusion.

**Fix**: Remove the directory with leading space.

---

## 4. Refactoring Opportunities

### 🔴 HIGH PRIORITY REFACTORING

#### 4.1 Extract Service Layer
**Current**: Business logic scattered across handlers and repositories.

**Refactor**:
```python
# app/services/recommendation_service.py
class RecommendationService:
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def generate_recommendations(
        self,
        user_id: int,
        count: int = 3,
        strategy: str = "v1"
    ) -> list[RecPick]:
        # All recommendation logic here
        pass
```

**Benefits**:
- Testable in isolation
- Reusable across bot and API
- Clear separation of concerns

#### 4.2 Split Monolithic Router
Already covered in 1.7

**Refactor Steps**:
1. Extract command handlers to `handlers/commands.py`
2. Extract callback handlers to `handlers/callbacks.py`
3. Extract flow logic to `flows/`
4. Keep router.py as simple orchestrator

#### 4.3 Create Configuration Object Pattern
**Current**: Settings imported directly everywhere.

**Refactor**:
```python
# app/core/config.py
class AppConfig:
    def __init__(self):
        self.settings = Settings()
        self.validate()
    
    def validate(self):
        # All validation logic
        pass
    
    @property
    def is_production(self) -> bool:
        return os.getenv("ENV") == "production"

config = AppConfig()
```

#### 4.4 Standardize Error Handling
**Current**: Inconsistent try/catch blocks everywhere.

**Refactor**:
```python
# app/core/exceptions.py
class WhatToWatchError(Exception):
    """Base exception"""
    
class TMDBError(WhatToWatchError):
    """TMDB API errors"""
    
class ValidationError(WhatToWatchError):
    """User input validation errors"""

# app/bot/middleware/error_handler.py
async def error_handler(update, exception):
    logger.error(f"Error processing {update}", exc_info=exception)
    # Send user-friendly message
```

### 🟡 MEDIUM PRIORITY REFACTORING

#### 4.5 Repository Pattern Cleanup
**Current**: Repositories mix concerns and have inconsistent APIs.

**Refactor**:
- Make all repositories inherit from base repository
- Standardize method names
- Move business logic to services

#### 4.6 Extract Constants
Already covered in 2.4

#### 4.7 Simplify Recommender Logic
**Current**: `recommend_v1()` is 260+ lines with complex scoring logic.

**Refactor**:
```python
class RecommenderV1:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.scorer = CandidateScorer()
        self.diversifier = CandidateDiversifier()
    
    async def recommend(self, user_id: int, count: int) -> list[RecPick]:
        candidates = await self._get_candidates(user_id)
        scored = await self.scorer.score(candidates)
        diversified = self.diversifier.diversify(scored, count)
        return diversified
```

#### 4.8 Async Context Manager for Sessions
**Current**: Manual session management everywhere.

**Refactor**:
```python
# app/db/session.py
from contextlib import asynccontextmanager

@asynccontextmanager
async def get_session():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

# Usage
async with get_session() as session:
    user = await get_or_create_user(session, telegram_id)
```

---

## 5. Reliability & Safety

### 🔴 HIGH PRIORITY ISSUES

#### 5.1 No Rate Limiting on External APIs
**Problem**: No rate limiting for TMDB or OpenAI calls.

**Impact**: 
- Could hit API limits
- Cost overruns on OpenAI
- Potential bans from TMDB

**Fix**: Add rate limiting with tenacity:
```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10)
)
async def _tmdb_get(path: str, params: dict) -> dict:
    # Implementation
```

#### 5.2 No Database Connection Pool Configuration
**Problem**: Using defaults for connection pooling.

**Fix**: Configure in `session.py`:
```python
engine = create_async_engine(
    settings.database_url_async,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=3600
)
```

#### 5.3 No Timeout Configuration
**Problem**: Only TMDB has timeout (10s), no timeouts elsewhere.

**Fix**: Add timeouts to all async operations:
- Database queries: 30s
- OpenAI calls: 60s (specified in config but not enforced)
- Bot handlers: 55s (Telegram has 60s limit)

#### 5.4 Unsafe SQL in Some Places
**Problem**: While most code uses SQLAlchemy ORM properly, there are potential SQL injection points.

**Evidence**: Check all raw SQL queries and text() usages.

**Fix**: Audit all queries, use parameterized queries.

#### 5.5 No Secrets Management
**Problem**: Secrets in `.env` file with no rotation strategy.

**Fix**: 
1. Use secrets manager (AWS Secrets Manager, HashiCorp Vault)
2. Never commit `.env`
3. Document secret rotation process

### 🟡 MEDIUM PRIORITY ISSUES

#### 5.6 Missing Input Validation
**Problem**: User inputs not validated before processing.

**Example**:
```python
# In router.py - no validation on text length
review_text = message.text.strip()  # Could be megabytes
```

**Fix**: Add validators:
```python
MAX_REVIEW_LENGTH = 5000

def validate_review(text: str) -> str:
    if len(text) > MAX_REVIEW_LENGTH:
        raise ValidationError(f"Review too long (max {MAX_REVIEW_LENGTH})")
    return text
```

#### 5.7 No Graceful Shutdown
**Problem**: No cleanup on application shutdown.

**Fix**: Add signal handlers:
```python
import signal

async def shutdown(signal, loop):
    logger.info(f"Received exit signal {signal.name}")
    # Close database connections
    # Cancel background tasks
    # etc.
```

#### 5.8 Embedding Job Queue Has No Dead Letter Queue
**Problem**: Failed embeddings jobs retry indefinitely or are lost.

**Fix**: Add max retries and dead letter handling:
```python
# In models.py
max_attempts: Mapped[int] = mapped_column(Integer, default=3)

# In embedding_worker.py
if job.attempts >= job.max_attempts:
    await move_to_dead_letter_queue(job)
```

---

## 6. Testing

### 🔴 HIGH PRIORITY ISSUES

#### 6.1 Extremely Low Test Coverage
**Problem**: 
- Only 6 test files
- ~498 lines of tests vs ~3,843 lines of code
- No unit tests for individual functions
- Only integration tests

**Current Test Files**:
- `test_feedback_status.py` (50 lines)
- `test_no_recent_repeats.py` (41 lines)
- `test_pending_review_long_text.py` (36 lines)
- `test_rate_limit_concurrency.py` (102 lines)
- `test_recommendation_item_concurrency.py` (111 lines)
- `test_recommendations_filters.py` (31 lines)

**Fix**: Add comprehensive test suite:
```
tests/
  unit/
    test_models.py
    test_repositories/
    test_services/
    test_recommender/
  integration/
    test_bot_handlers.py
    test_recommendation_flow.py
  e2e/
    test_full_recommendation_flow.py
```

**Target Coverage**: Minimum 80% line coverage

#### 6.2 No Mocking Strategy
**Problem**: Tests use real database and stub TMDB, inconsistent approach.

**Fix**: 
- Unit tests: Mock all external dependencies
- Integration tests: Use test database
- E2E tests: Use test database + stubs

#### 6.3 Tests Are Hard to Run
**Problem**: 
- Requires manual database setup
- Script `create_test_db.sh` requires Docker
- No documentation on running tests

**Fix**: 
1. Add test instructions to README
2. Add pytest fixtures that auto-create test DB
3. Add `make test` command

#### 6.4 No CI Testing
Already covered in 1.4

### 🟡 MEDIUM PRIORITY ISSUES

#### 6.5 Missing Test Categories
- No tests for error conditions
- No tests for edge cases (empty lists, None values)
- No tests for concurrent operations (except 2)
- No performance tests

#### 6.6 Test Data Management
**Problem**: Test data hardcoded in `tests/fakes/tmdb_stub.py`.

**Fix**: Use factories or fixtures:
```python
# tests/factories.py
from factory import Factory, Faker

class UserFactory(Factory):
    class Meta:
        model = User
    
    telegram_id = Faker('random_int', min=1000000, max=9999999)
    timezone = "Europe/Riga"
```

#### 6.7 No Load Testing
**Problem**: Unknown performance characteristics under load.

**Fix**: Add load tests with Locust or similar:
```python
# tests/load/locustfile.py
from locust import HttpUser, task

class BotUser(HttpUser):
    @task
    def recommend(self):
        self.client.post("/api/recommend", json={"user_id": 123})
```

---

## 7. Performance & Scalability

### 🟡 MEDIUM PRIORITY ISSUES

#### 7.1 N+1 Query Problem
**Problem**: Multiple places fetch data in loops without eager loading.

**Example from `router.py`**:
```python
for i, p in enumerate(picks_v1, start=1):
    details = await get_movie_details(session, p.tmdb_id)  # N queries
    keywords = await get_movie_keywords(session, p.tmdb_id)  # N more queries
```

**Fix**: Batch fetch or eager load:
```python
# Fetch all at once
tmdb_ids = [p.tmdb_id for p in picks_v1]
details_map = await get_movie_details_batch(session, tmdb_ids)
keywords_map = await get_movie_keywords_batch(session, tmdb_ids)
```

#### 7.2 No Caching Strategy Beyond DB
**Problem**: TMDB cache in database but no in-memory cache.

**Fix**: Add Redis or in-memory LRU cache:
```python
from functools import lru_cache

@lru_cache(maxsize=1000)
def get_cached_movie_details(tmdb_id: int) -> dict:
    # Check memory → Check DB → Fetch from TMDB
```

#### 7.3 Sequential Operations That Could Be Parallel
**Problem**: Multiple independent async operations done sequentially.

**Example**:
```python
details = await get_movie_details(session, tmdb_id)
keywords = await get_movie_keywords(session, tmdb_id)
```

**Fix**:
```python
details, keywords = await asyncio.gather(
    get_movie_details(session, tmdb_id),
    get_movie_keywords(session, tmdb_id)
)
```

#### 7.4 Large Embedding Vectors in Memory
**Problem**: Loading all embeddings for comparisons.

**Impact**: High memory usage with many users.

**Fix**: 
1. Use database vector similarity search (pgvector already available)
2. Only load top-K most similar vectors

#### 7.5 No Pagination on Lists
**Problem**: Some queries could return large result sets.

**Fix**: Add pagination helpers:
```python
def paginate(query, page: int = 1, per_page: int = 20):
    return query.offset((page - 1) * per_page).limit(per_page)
```

---

## 8. Developer Experience

### 🔴 HIGH PRIORITY ISSUES

#### 8.1 No Setup Instructions
Already covered in 1.3

#### 8.2 No Development Scripts
**Problem**: No `Makefile` or scripts for common tasks.

**Fix**: Add `Makefile`:
```makefile
.PHONY: install test lint run-bot run-api migrate

install:
	pip install -r requirements.txt
	
test:
	pytest tests/ -v

lint:
	ruff check app/
	black --check app/

format:
	ruff check --fix app/
	black app/

run-bot:
	python -m app.bot.run

run-api:
	uvicorn app.api.main:app --reload

migrate:
	alembic upgrade head
```

#### 8.3 No Contribution Guidelines
**Problem**: No `CONTRIBUTING.md` explaining how to contribute.

**Fix**: Add contribution guide with:
- Code style
- Testing requirements
- PR process
- Commit message format

### 🟡 MEDIUM PRIORITY ISSUES

#### 8.4 Incomplete `.gitignore`
**Problem**: `.gitignore` has duplicates and missing entries.

**Evidence**: Lines 183-206 duplicate earlier sections.

**Fix**: Clean up and add:
```
# IDE
.idea/
.vscode/
*.swp

# Test
.coverage
htmlcov/

# Alembic
alembic.ini.backup
```

#### 8.5 No Pre-commit Hooks
**Problem**: No enforcement of code quality before commit.

**Fix**: Add `.pre-commit-config.yaml`:
```yaml
repos:
  - repo: https://github.com/psf/black
    rev: 23.12.0
    hooks:
      - id: black
  - repo: https://github.com/charliermarsh/ruff-pre-commit
    rev: v0.1.8
    hooks:
      - id: ruff
```

#### 8.6 No Debug Mode
**Problem**: No easy way to run in debug mode.

**Fix**: Add debug configuration:
```python
# config.py
debug: bool = False
log_level: str = "INFO"
```

---

## Prioritized Issue Summary

### 🔴 CRITICAL (Must Fix Before Production)
1. ✅ Add `requirements.txt` with pinned versions
2. ✅ Create proper `Dockerfile`
3. ✅ Write comprehensive `README.md`
4. ✅ Add CI/CD pipeline (GitHub Actions)
5. ✅ Fix duplicate migrations
6. ✅ Add environment variable validation
7. ✅ Configure logging throughout app
8. ✅ Add rate limiting for external APIs
9. ✅ Increase test coverage to minimum 50%

### 🟡 HIGH (Should Fix Soon)
10. Split monolithic `router.py` into modules
11. Add service layer for business logic
12. Standardize error handling
13. Add type checking (mypy)
14. Add linting (ruff)
15. Fix N+1 query problems
16. Add health check endpoints
17. Document API with OpenAPI
18. Add input validation

### 🟢 MEDIUM (Good to Have)
19. Extract configuration patterns
20. Refactor recommender into classes
21. Add caching strategy
22. Parallelize independent operations
23. Add load testing
24. Create development scripts (Makefile)
25. Add pre-commit hooks
26. Improve test organization

---

## Refactoring Roadmap

### Phase 1: Foundation (Week 1)
**Goal**: Make project runnable and testable

1. **Day 1-2**: Add missing files
   - Create `requirements.txt`
   - Write `README.md`
   - Create proper `Dockerfile`
   - Update `.env.example`

2. **Day 3-4**: Setup CI/CD
   - Add GitHub Actions workflows
   - Configure linting (ruff, black)
   - Configure type checking (mypy)
   - Add test workflow

3. **Day 5**: Clean up
   - Remove duplicate migrations
   - Fix test directory spacing issue
   - Update `.gitignore`
   - Add logging configuration

### Phase 2: Code Quality (Week 2)
**Goal**: Improve maintainability

4. **Day 1-2**: Refactor router
   - Split into handlers/commands.py
   - Split into handlers/callbacks.py
   - Extract flows/review_flow.py
   - Extract flows/recommend_flow.py

5. **Day 3-4**: Add service layer
   - Create base service class
   - Implement RecommendationService
   - Implement ReviewService
   - Move business logic from router

6. **Day 5**: Error handling
   - Create exception hierarchy
   - Add global error handler
   - Add error logging
   - User-friendly error messages

### Phase 3: Testing (Week 3)
**Goal**: Increase confidence in code

7. **Day 1-2**: Unit tests
   - Test repositories
   - Test services
   - Test recommender logic
   - Target 50% coverage

8. **Day 3-4**: Integration tests
   - Test bot handlers
   - Test recommendation flow
   - Test review flow
   - Target 70% coverage

9. **Day 5**: Documentation
   - Add docstrings to all functions
   - Document architecture
   - Add contribution guidelines
   - Update README with examples

### Phase 4: Performance (Week 4)
**Goal**: Optimize for scale

10. **Day 1-2**: Database optimization
    - Fix N+1 queries
    - Add indexes where needed
    - Configure connection pooling
    - Add query timeout

11. **Day 3-4**: Caching
    - Add in-memory cache
    - Optimize TMDB cache usage
    - Add pgvector optimizations

12. **Day 5**: Monitoring
    - Add metrics collection
    - Add performance logging
    - Add health checks
    - Document performance characteristics

### Phase 5: Production Readiness (Week 5)
**Goal**: Deploy safely

13. **Day 1-2**: Security
    - Add secrets management
    - Audit all SQL queries
    - Add input validation
    - Security scanning in CI

14. **Day 3-4**: Reliability
    - Add rate limiting
    - Add retry logic
    - Graceful shutdown
    - Dead letter queue for jobs

15. **Day 5**: Documentation & Training
    - Operations runbook
    - Incident response plan
    - Team training
    - Launch checklist

---

## Recommendations Summary

### Immediate Actions (This Sprint)
1. Create `requirements.txt` - 30 minutes
2. Write basic `README.md` - 1 hour
3. Create `Dockerfile` - 1 hour
4. Add GitHub Actions for testing - 2 hours
5. Configure logging - 1 hour

### Next Sprint
6. Split router.py - 1 day
7. Add service layer - 2 days
8. Increase test coverage to 50% - 2 days

### Following Sprints
9. Performance optimizations
10. Production hardening
11. Documentation completion

---

## Conclusion

The WhatToWatch project has a solid foundation with modern technologies (async Python, SQLAlchemy, pgvector, LLM integration), but lacks essential infrastructure and practices for long-term maintenance:

**Strengths**:
- Good use of async/await
- Proper database schema with migrations
- Vector search capability
- Modular structure (separate recommenders, repositories)

**Critical Weaknesses**:
- No dependency management (cannot install)
- No CI/CD (no quality gates)
- Minimal tests (~13% coverage estimate)
- Missing documentation
- Monolithic handlers
- No logging or monitoring

**Risk Level**: **HIGH** - Cannot be deployed to production in current state

**Time to Production Ready**: **4-5 weeks** following the roadmap above

**Recommended First Steps**:
1. Add `requirements.txt` (today)
2. Write `README.md` (today)
3. Add basic CI with tests (this week)
4. Split router.py (next week)
5. Increase test coverage (ongoing)

---

**Next Review**: After Phase 1 completion (1 week)
