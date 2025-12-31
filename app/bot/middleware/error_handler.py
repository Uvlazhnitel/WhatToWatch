"""Bot middleware for error handling."""

import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update

from app.core.exceptions import WhatToWatchError, RateLimitError, ValidationError

logger = logging.getLogger(__name__)


class ErrorHandlerMiddleware(BaseMiddleware):
    """
    Middleware to handle errors globally in the bot.
    
    Logs all errors and sends user-friendly messages to users.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        try:
            return await handler(event, data)
        except RateLimitError as e:
            logger.warning(f"Rate limit hit: {e}", exc_info=True)
            if isinstance(event, Update) and event.message:
                await event.message.answer(e.user_message)
        except ValidationError as e:
            logger.info(f"Validation error: {e}")
            if isinstance(event, Update) and event.message:
                await event.message.answer(f"❌ {e.user_message}")
        except WhatToWatchError as e:
            logger.error(f"Application error: {e}", exc_info=True)
            if isinstance(event, Update) and event.message:
                await event.message.answer(
                    e.user_message if e.user_message else "Произошла ошибка. Попробуйте позже."
                )
        except Exception as e:
            logger.error(f"Unexpected error: {e}", exc_info=True)
            if isinstance(event, Update) and event.message:
                await event.message.answer(
                    "Произошла неожиданная ошибка. Попробуйте позже или обратитесь к администратору."
                )
