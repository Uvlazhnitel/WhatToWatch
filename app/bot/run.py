"""
Telegram Bot Runner

Main entry point for the WhatToWatch Telegram bot.
Initializes logging, creates the bot instance, and starts polling for updates.

Run with:
    python -m app.bot.run
"""

import asyncio

from aiogram import Bot, Dispatcher

from app.core.config import settings
from app.bot.router import router
from app.core.logging import setup_logging
from aiogram.client.session.aiohttp import AiohttpSession

setup_logging()


async def main() -> None:
    session = AiohttpSession(timeout=60) 
    bot = Bot(token=settings.telegram_bot_token, session=session)
    dp = Dispatcher()
    dp.include_router(router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
