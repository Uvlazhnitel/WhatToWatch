import os
import pytest
import pytest_asyncio

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from tests._alembic import alembic_upgrade_head
from tests.fakes.tmdb_stub import DETAILS, KEYWORDS, RECOMMENDATIONS, SIMILAR

import app.integrations.tmdb as tmdb  # важно: патчим модуль, а не "from ... import ..."
from pathlib import Path

def _load_env_file(path: str = ".env.test") -> None:
    p = Path(path)
    if not p.exists():
        return
    for raw in p.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        os.environ.setdefault(k, v)

_load_env_file(".env.test")

def _env_first(*keys: str) -> str | None:
    for k in keys:
        v = os.getenv(k)
        if v:
            return v
    return None


# Подхватываем URL'ы из .env.test (ты их export'ишь перед pytest)
TEST_DB_SYNC = _env_first("TEST_DB_SYNC", "DATABASE_URL_SYNC", "DB_SYNC_URL", "DATABASE_URL")
TEST_DB_ASYNC = _env_first("TEST_DB_ASYNC", "DATABASE_URL_ASYNC", "DB_ASYNC_URL")

if not TEST_DB_SYNC:
    raise RuntimeError(
        "Test DB sync url is not set. Put it into .env.test as TEST_DB_SYNC or DATABASE_URL_SYNC."
    )

# Если ASYNC не задан — аккуратно деривим из sync URL
if not TEST_DB_ASYNC:
    TEST_DB_ASYNC = (
        TEST_DB_SYNC.replace("postgresql+psycopg://", "postgresql+asyncpg://")
        .replace("postgresql://", "postgresql+asyncpg://")
    )


@pytest.fixture(scope="session", autouse=True)
def _migrate_test_db():
    # накатываем миграции один раз на тестовую БД
    alembic_upgrade_head(TEST_DB_SYNC)


@pytest_asyncio.fixture(scope="session")
async def async_engine():
    # NullPool = не переиспользуем asyncpg connections между тестами/лупами,
    # это сильно снижает шанс "Future attached to a different loop"
    engine = create_async_engine(TEST_DB_ASYNC, poolclass=NullPool, future=True)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture()
async def session(async_engine):
    # 1) одна connection на тест
    # 2) outer transaction
    # 3) nested transaction (SAVEPOINT) — чтобы session.commit() не "закрывал" outer
    async with async_engine.connect() as conn:
        await conn.begin()
        await conn.begin_nested()

        s = AsyncSession(bind=conn, expire_on_commit=False)

        @event.listens_for(s.sync_session, "after_transaction_end")
        def _restart_savepoint(sess, trans):
            # после commit/rollback nested-транзакции поднимаем новый savepoint
            if trans.nested and not trans._parent.nested:
                conn.sync_connection.begin_nested()

        try:
            yield s
        finally:
            await s.close()
            # откатываем outer transaction — чистая БД на следующий тест
            await conn.rollback()


@pytest.fixture(autouse=True)
def _stub_tmdb(monkeypatch):
    # Заглушаем TMDB, чтобы не было сети и 404
    async def fake_get_movie_details_payload(session, tmdb_id: int):
        return DETAILS[tmdb_id]

    async def fake_get_movie_keywords_payload(session, tmdb_id: int):
        return KEYWORDS.get(tmdb_id, {"id": tmdb_id, "keywords": []})

    async def fake_get_movie_similar_payload(session, tmdb_id: int):
        return SIMILAR.get(tmdb_id, {"page": 1, "results": []})

    async def fake_get_movie_recommendations_payload(session, tmdb_id: int):
        return RECOMMENDATIONS.get(tmdb_id, {"page": 1, "results": []})

    monkeypatch.setattr(tmdb, "get_movie_details_payload", fake_get_movie_details_payload)
    monkeypatch.setattr(tmdb, "get_movie_keywords_payload", fake_get_movie_keywords_payload)
    monkeypatch.setattr(tmdb, "get_movie_similar_payload", fake_get_movie_similar_payload)
    monkeypatch.setattr(tmdb, "get_movie_recommendations_payload", fake_get_movie_recommendations_payload)
