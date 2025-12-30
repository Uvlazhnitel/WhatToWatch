from __future__ import annotations

import asyncio
import logging
from aiogram.exceptions import TelegramNetworkError, TelegramRetryAfter

logger = logging.getLogger(__name__)


async def safe_answer(message, text: str, **kwargs) -> None:
    """
    Надёжная отправка сообщений.
    - не валит обработчик при сетевом сбое
    - делает несколько ретраев
    """
    max_attempts = 3
    delay = 1.0

    for attempt in range(1, max_attempts + 1):
        try:
            await message.answer(text, **kwargs)
            return
        except TelegramRetryAfter as e:
            wait_for = int(getattr(e, "retry_after", 2))
            logger.warning("TelegramRetryAfter: wait %s sec", wait_for)
            await asyncio.sleep(wait_for)
        except TelegramNetworkError as e:
            logger.warning("TelegramNetworkError on send (attempt %s/%s): %s", attempt, max_attempts, e)
            if attempt == max_attempts:
                return
            await asyncio.sleep(delay)
            delay *= 2
        except Exception as e:
            # на всякий
            logger.exception("Unexpected error in safe_answer: %s", e)
            return
