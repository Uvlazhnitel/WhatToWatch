from __future__ import annotations

import os
from alembic.config import Config
from alembic import command


def alembic_upgrade_head(database_url_sync: str) -> None:
    cfg = Config("alembic.ini")
    # переопределяем URL именно для тестов
    cfg.set_main_option("sqlalchemy.url", database_url_sync)
    command.upgrade(cfg, "head")
