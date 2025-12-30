from __future__ import annotations

import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool, text
from alembic import context
from dotenv import load_dotenv

# загрузим .env, чтобы взять DATABASE_URL_SYNC
load_dotenv()

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Импортируем metadata моделей
from app.db.base import Base  # noqa: E402
from app.db import models  # noqa: F401,E402  (важно: чтобы модели зарегистрировались в Base.metadata)

target_metadata = Base.metadata


def get_sync_database_url() -> str:
    url = os.getenv("DATABASE_URL_SYNC")
    if not url:
        raise RuntimeError("DATABASE_URL_SYNC is not set in .env")
    return url


def run_migrations_offline() -> None:
    url = get_sync_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = get_sync_database_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        future=True,
    )

    with connectable.connect() as connection:
        # гарантируем pgvector extension (на всякий случай)
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        connection.commit()

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
