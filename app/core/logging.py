"""
Logging Configuration

Configures application-wide logging with appropriate levels and formats.
Suppresses verbose output from third-party libraries while maintaining
visibility of application logs.
"""

from __future__ import annotations

import logging
import os
import sys


def setup_logging() -> None:
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
        stream=sys.stdout,
    )

    # подавим шум
    logging.getLogger("aiogram").setLevel(logging.INFO)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
