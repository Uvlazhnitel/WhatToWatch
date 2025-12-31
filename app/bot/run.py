import asyncio
import logging

from aiogram import Bot, Dispatcher

from app.core.config import settings
from app.bot.router import router
from app.core.logging import setup_logging
from app.bot.middleware import ErrorHandlerMiddleware
from aiogram.client.session.aiohttp import AiohttpSession

setup_logging()
logger = logging.getLogger(__name__)


async def main() -> None:
    logger.info("Starting WhatToWatch bot...")
    
    session = AiohttpSession(timeout=60)
    bot = Bot(token=settings.telegram_bot_token, session=session)
    dp = Dispatcher()
    
    # Add error handler middleware
    dp.message.middleware(ErrorHandlerMiddleware())
    dp.callback_query.middleware(ErrorHandlerMiddleware())
    
    dp.include_router(router)
    
    logger.info("Bot started successfully. Polling for updates...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
