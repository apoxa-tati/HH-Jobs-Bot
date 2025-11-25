import asyncio
import logging

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

from bot.config import settings  # Импортируем настройки


# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Создаем диспетчер
dp = Dispatcher()

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer("Привет! Я бот для работы с HH.ru 🚀\n\n"
                        "Доступные команды:\n"
                        "/start - начать работу\n"
                        "/help - помощь\n"
                        "/search - поиск вакансий")

@dp.message(Command("help"))
async def help_handler(message: types.Message):
    await message.answer("Я помогу вам с поиском работы на HH.ru!\n\n"
                        "Функции:\n"
                        "• Поиск вакансий\n"
                        "• Отслеживание новых вакансий\n"
                        "• Рекомендации по резюме")

@dp.message(Command("search"))
async def search_handler(message: types.Message):
    await message.answer("🔍 Функция поиска вакансий!\n\n"
                        "Введите профессию для поиска:\n"
                        "Например: 'python разработчик'")

@dp.message()
async def text_handler(message: types.Message):
    text = message.text.lower()
    
    if text in ['привет', 'hello', 'hi']:
        await message.answer("Привет! 👋 Как я могу помочь с поиском работы?")
    elif text.startswith('/'):
        await message.answer(f"Команда {message.text} не найдена. Используйте /help")
    else:
        await message.answer(f"Вы сказали: '{message.text}'\n"
                            "Используйте /help для списка команд")

async def main():
    if not settings.bot_token:
        logger.error("❌ TG_BOT_API_KEY не найден в .env файле!")
        return
    
    bot = Bot(token=settings.bot_token)
    
    logger.info("Бот запускается...")
    
    try:
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Ошибка: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())