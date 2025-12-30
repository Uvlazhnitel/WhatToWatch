import asyncio
import os

from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message as AiogramMessage


load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set in .env")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher() 

@dp.message(CommandStart())
async def start_handler(message: AiogramMessage):  # Use AiogramMessage here
    await message.answer("Привет! Я живой ✅ Напиши /recommend позже 🙂")

@dp.message(F.text)
async def echo_handler(message: AiogramMessage):  # Use AiogramMessage here
    await message.answer("Понял. Для начала попробуй /start 🙂")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())