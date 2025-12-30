import asyncio

from aiogram import Bot, Dispatcher

from app.core.config import settings
from app.bot.router import router
from app.core.logging import setup_logging
setup_logging()


async def main() -> None:
    bot = Bot(token=settings.telegram_bot_token)
    dp = Dispatcher()
    dp.include_router(router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
