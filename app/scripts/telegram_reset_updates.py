import os
import asyncio
from aiogram import Bot

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

async def main():
    if not TOKEN:
        raise SystemExit("TELEGRAM_BOT_TOKEN not set")
    bot = Bot(token=TOKEN)
    # на всякий случай удаляем webhook
    await bot.delete_webhook(drop_pending_updates=True)
    await bot.session.close()
    print("✅ webhook deleted + pending updates dropped")

asyncio.run(main())
