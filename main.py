import asyncio
from datetime import datetime
import logging
import os

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
import aiohttp
from dotenv import load_dotenv
from supabase import create_client


# Загружаем переменные из .env
load_dotenv()

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация Supabase
supabase_url = os.getenv('SUPABASE_URL')
supabase_key = os.getenv('SUPABASE_KEY')

# Временное хранилище в памяти (на случай проблем с Supabase)
class TempStorage:
    def __init__(self):
        self.users = {}
        self.search_settings = {}
    
    async def save_user_temp(self, telegram_id: int, **data):
        try:
            self.users[telegram_id] = {
                **data,
                'created_at': datetime.utcnow().isoformat()
            }
            logger.info(f"✅ Пользователь {telegram_id} сохранен во временное хранилище")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка временного сохранения: {e}")
            return False
    
    async def get_user_temp(self, telegram_id: int):
        return self.users.get(telegram_id)
    
    async def save_search_settings_temp(self, user_id: int, settings: dict):
        try:
            self.search_settings[user_id] = settings
            logger.info(f"✅ Настройки поиска для {user_id} сохранены во временное хранилище")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения настроек: {e}")
            return False
    
    async def get_search_settings_temp(self, user_id: int):
        return self.search_settings.get(user_id)

temp_storage = TempStorage()

# Пытаемся подключиться к Supabase
supabase = None
try:
    if supabase_url and supabase_key:
        supabase = create_client(supabase_url, supabase_key)
        logger.info("✅ Supabase клиент успешно создан")
    else:
        logger.warning("⚠️ SUPABASE_URL или SUPABASE_KEY не найдены, используем временное хранилище")
except Exception as e:
    logger.error(f"❌ Ошибка создания Supabase клиента: {e}")
    logger.warning("⚠️ Используем временное хранилище вместо Supabase")

# Создаем диспетчер с хранилищем
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Состояния для регистрации пользователя
class RegistrationStates(StatesGroup):
    waiting_for_full_name = State()
    waiting_for_city = State()
    waiting_for_position = State()
    waiting_for_skills = State()
    waiting_for_resume = State()

# Состояния для настройки поиска
class SearchSettingsStates(StatesGroup):
    waiting_for_position = State()
    waiting_for_city = State()
    waiting_for_salary = State()

class DatabaseService:
    @staticmethod
    async def save_user(telegram_id: int, full_name: str, city: str = None, 
                       desired_position: str = None, skills: str = None, resume: str = None):
        """Сохраняем/обновляем пользователя в Supabase"""
        try:
            if not supabase:
                logger.warning("Supabase не доступен, используем временное хранилище")
                return await temp_storage.save_user_temp(
                    telegram_id, 
                    full_name=full_name, 
                    city=city, 
                    desired_position=desired_position, 
                    skills=skills, 
                    resume=resume
                )
            
            logger.info(f"🔄 Сохранение пользователя {telegram_id} в Supabase")
            
            # Проверяем, есть ли уже пользователь
            existing = supabase.table('users')\
                .select('*')\
                .eq('telegram_id', telegram_id)\
                .execute()
            
            user_data = {
                'telegram_id': telegram_id,
                'full_name': full_name,
                'city': city,
                'desired_position': desired_position,
                'skills': skills,
                'resume': resume,
                'updated_at': datetime.utcnow().isoformat()
            }
            
            if existing.data:
                logger.info(f"📝 Обновление существующего пользователя {telegram_id}")
                result = supabase.table('users')\
                    .update(user_data)\
                    .eq('telegram_id', telegram_id)\
                    .execute()
            else:
                logger.info(f"🆕 Создание нового пользователя {telegram_id}")
                user_data['created_at'] = datetime.utcnow().isoformat()
                result = supabase.table('users')\
                    .insert(user_data)\
                    .execute()
            
            logger.info(f"✅ Пользователь {telegram_id} успешно сохранен в Supabase")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения пользователя в Supabase: {e}")
            logger.warning("🔄 Пробуем сохранить во временное хранилище")
            return await temp_storage.save_user_temp(
                telegram_id, 
                full_name=full_name, 
                city=city, 
                desired_position=desired_position, 
                skills=skills, 
                resume=resume
            )

    @staticmethod
    async def get_user(telegram_id: int):
        """Получаем пользователя из Supabase или временного хранилища"""
        try:
            if supabase:
                result = supabase.table('users')\
                    .select('*')\
                    .eq('telegram_id', telegram_id)\
                    .execute()
                
                if result.data:
                    logger.info(f"✅ Пользователь {telegram_id} найден в Supabase")
                    return result.data[0]
            
            # Если не нашли в Supabase, ищем во временном хранилище
            user = await temp_storage.get_user_temp(telegram_id)
            if user:
                logger.info(f"✅ Пользователь {telegram_id} найден во временном хранилище")
            else:
                logger.info(f"❌ Пользователь {telegram_id} не найден")
                
            return user
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения пользователя: {e}")
            return await temp_storage.get_user_temp(telegram_id)

    @staticmethod
    async def save_search_settings(user_id: int, settings: dict):
        """Сохраняем настройки поиска"""
        try:
            if not supabase:
                return await temp_storage.save_search_settings_temp(user_id, settings)
            
            existing = supabase.table('search_settings')\
                .select('*')\
                .eq('user_id', user_id)\
                .execute()
            
            settings_data = {
                'user_id': user_id,
                'position': settings.get('position'),
                'city': settings.get('city'),
                'min_salary': settings.get('min_salary'),
                'updated_at': datetime.utcnow().isoformat()
            }
            
            if existing.data:
                result = supabase.table('search_settings')\
                    .update(settings_data)\
                    .eq('user_id', user_id)\
                    .execute()
            else:
                settings_data['created_at'] = datetime.utcnow().isoformat()
                result = supabase.table('search_settings')\
                    .insert(settings_data)\
                    .execute()
            
            logger.info(f"✅ Настройки поиска для {user_id} сохранены в Supabase")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения настроек в Supabase: {e}")
            return await temp_storage.save_search_settings_temp(user_id, settings)

    @staticmethod
    async def get_search_settings(user_id: int):
        """Получаем настройки поиска"""
        try:
            if supabase:
                result = supabase.table('search_settings')\
                    .select('*')\
                    .eq('user_id', user_id)\
                    .execute()
                
                if result.data:
                    return result.data[0]
            
            return await temp_storage.get_search_settings_temp(user_id)
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения настроек: {e}")
            return await temp_storage.get_search_settings_temp(user_id)

class HHService:
    @staticmethod
    async def search_vacancies(search_params: dict):
        """Поиск вакансий через HH API с фильтрами"""
        url = "https://api.hh.ru/vacancies"
        
        params = {
            'text': search_params.get('position', ''),
            'area': await HHService.get_area_id(search_params.get('city', 'Москва')),
            'per_page': 5,
            'page': 0
        }
        
        if search_params.get('min_salary'):
            params['salary'] = search_params['min_salary']
            # Исправляем: передаем 1 вместо True
            params['only_with_salary'] = 1
        
        try:
            logger.info(f"🔍 Поиск вакансий с параметрами: {params}")
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        vacancies = data.get('items', [])
                        logger.info(f"✅ Найдено вакансий: {len(vacancies)}")
                        return vacancies
                    else:
                        logger.error(f"❌ Ошибка HH API: {response.status}")
                        return []
        except Exception as e:
            logger.error(f"❌ Ошибка при поиске вакансий: {e}")
            return []

    @staticmethod
    async def get_area_id(city_name: str) -> int:
        area_map = {
            'москва': 1, 'санкт-петербург': 2, 'екатеринбург': 3,
            'новосибирск': 4, 'казань': 88, 'нижний новгород': 66,
        }
        return area_map.get(city_name.lower(), 1)

    @staticmethod
    def format_vacancy(vacancy):
        title = vacancy.get('name', 'Без названия')
        company = vacancy.get('employer', {}).get('name', 'Не указано')
        salary = vacancy.get('salary')
        
        if salary:
            salary_from = salary.get('from')
            salary_to = salary.get('to')
            currency = salary.get('currency', 'RUR')
            salary_text = f"{salary_from or ''}-{salary_to or ''} {currency}"
        else:
            salary_text = "Не указана"
            
        url = vacancy.get('alternate_url', '#')
        
        return (f"🏢 {title}\n"
                f"📊 Компания: {company}\n"
                f"💰 Зарплата: {salary_text}\n"
                f"🔗 {url}")

async def perform_vacancy_search(user_id: int, settings: dict, message: types.Message):
    """Функция для выполнения поиска вакансий и отправки результатов"""
    await message.answer("🔍 Ищу вакансии по вашим настройкам...")
    
    vacancies = await HHService.search_vacancies(settings)
    
    if vacancies:
        response = f"📋 Найдено вакансий: {len(vacancies)}\n\n"
        for i, vacancy in enumerate(vacancies, 1):
            response += f"{i}. {HHService.format_vacancy(vacancy)}\n\n"
        
        # Разбиваем длинные сообщения на части
        if len(response) > 4000:
            parts = [response[i:i+4000] for i in range(0, len(response), 4000)]
            for part in parts:
                await message.answer(part)
        else:
            await message.answer(response)
    else:
        await message.answer(
            "😔 По вашим настройкам ничего не найдено\n"
            "Попробуйте изменить параметры: /search"
        )

@dp.message(Command("start"))
async def start_handler(message: types.Message, state: FSMContext):
    user = await DatabaseService.get_user(message.from_user.id)
    
    if user:
        await message.answer(
            f"С возвращением, {user.get('full_name', 'друг')}! 👋\n\n"
            f"Используйте:\n"
            f"/search - настройки поиска\n"
            f"/find - поиск вакансий\n"
            f"/profile - ваш профиль\n"
            f"/help - помощь"
        )
    else:
        await message.answer(
            "👋 Добро пожаловать в HH Bot!\n\n"
            "Давайте зарегистрируем ваш профиль. Как вас зовут?\n"
            "(Фамилия и имя)"
        )
        await state.set_state(RegistrationStates.waiting_for_full_name)

@dp.message(RegistrationStates.waiting_for_full_name)
async def process_full_name(message: types.Message, state: FSMContext):
    await state.update_data(full_name=message.text)
    await message.answer("Отлично! В каком городе ищете работу?")
    await state.set_state(RegistrationStates.waiting_for_city)

@dp.message(RegistrationStates.waiting_for_city)
async def process_city(message: types.Message, state: FSMContext):
    await state.update_data(city=message.text)
    await message.answer("Какую должность вы ищете?\n(например: Python разработчик)")
    await state.set_state(RegistrationStates.waiting_for_position)

@dp.message(RegistrationStates.waiting_for_position)
async def process_position(message: types.Message, state: FSMContext):
    await state.update_data(desired_position=message.text)
    await message.answer(
        "Перечислите ваши ключевые навыки:\n"
        "(например: Python, Django, PostgreSQL, Docker)"
    )
    await state.set_state(RegistrationStates.waiting_for_skills)

@dp.message(RegistrationStates.waiting_for_skills)
async def process_skills(message: types.Message, state: FSMContext):
    await state.update_data(skills=message.text)
    await message.answer(
        "Напишите краткое резюме о себе:\n"
        "(опыт работы, образование, достижения)"
    )
    await state.set_state(RegistrationStates.waiting_for_resume)

@dp.message(RegistrationStates.waiting_for_resume)
async def process_resume(message: types.Message, state: FSMContext):
    try:
        user_data = await state.get_data()
        user_data['resume'] = message.text
        
        logger.info(f"🔄 Сохранение пользователя {message.from_user.id}")
        
        success = await DatabaseService.save_user(
            telegram_id=message.from_user.id,
            full_name=user_data['full_name'],
            city=user_data['city'],
            desired_position=user_data['desired_position'],
            skills=user_data['skills'],
            resume=user_data['resume']
        )
        
        if success:
            await message.answer(
                f"✅ Регистрация завершена!\n\n"
                f"📋 Ваш профиль:\n"
                f"👤 {user_data['full_name']}\n"
                f"🏙️ {user_data['city']}\n"
                f"💼 {user_data['desired_position']}\n"
                f"🛠️ Навыки: {user_data['skills']}\n\n"
                f"Теперь настройте поиск вакансий: /search"
            )
        else:
            await message.answer(
                "❌ Не удалось сохранить профиль.\n"
                "Но вы можете продолжить работу!\n"
                "Используйте /search для настройки поиска"
            )
        
        await state.clear()
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка в process_resume: {e}")
        await message.answer(
            "❌ Произошла непредвиденная ошибка.\n"
            "Попробуйте снова: /start\n\n"
            "Или используйте /search для настройки поиска"
        )
        await state.clear()

@dp.message(Command("profile"))
async def profile_handler(message: types.Message):
    user = await DatabaseService.get_user(message.from_user.id)
    
    if not user:
        await message.answer("❌ У вас нет профиля. Зарегистрируйтесь: /start")
        return
    
    await message.answer(
        f"📋 Ваш профиль:\n\n"
        f"👤 Имя: {user.get('full_name', 'Не указано')}\n"
        f"🏙️ Город: {user.get('city', 'Не указан')}\n"
        f"💼 Должность: {user.get('desired_position', 'Не указана')}\n"
        f"🛠️ Навыки: {user.get('skills', 'Не указаны')}\n"
        f"📄 Резюме: {user.get('resume', 'Не указано')}\n\n"
        f"Настроить поиск: /search"
    )

@dp.message(Command("search"))
async def search_settings_handler(message: types.Message, state: FSMContext):
    await message.answer(
        "🔍 Настройка поиска вакансий\n\n"
        "Какую должность вы ищете?\n"
        "Например: Тестировщик"
    )
    await state.set_state(SearchSettingsStates.waiting_for_position)

@dp.message(SearchSettingsStates.waiting_for_position)
async def process_search_position(message: types.Message, state: FSMContext):
    await state.update_data(position=message.text)
    await message.answer("В каком городе ищете работу?\nНапример: Санкт-Петербург")
    await state.set_state(SearchSettingsStates.waiting_for_city)

@dp.message(SearchSettingsStates.waiting_for_city)
async def process_search_city(message: types.Message, state: FSMContext):
    await state.update_data(city=message.text)
    await message.answer(
        "Укажите минимальную зарплату (руб):\n"
        "Или напишите 0, если не важно"
    )
    await state.set_state(SearchSettingsStates.waiting_for_salary)

@dp.message(SearchSettingsStates.waiting_for_salary)
async def process_search_salary(message: types.Message, state: FSMContext):
    try:
        salary = int(message.text)
        await state.update_data(min_salary=salary if salary > 0 else None)
        
        # Сохраняем базовые настройки
        search_data = await state.get_data()
        await DatabaseService.save_search_settings(message.from_user.id, search_data)
        
        await message.answer(
            "✅ Базовые настройки сохранены!\n\n"
            "🔍 Начинаю поиск вакансий..."
        )
        
        # АВТОМАТИЧЕСКИ ЗАПУСКАЕМ ПОИСК ВАКАНСИЙ ПОСЛЕ СОХРАНЕНИЯ ВСЕХ ДАННЫХ
        await perform_vacancy_search(message.from_user.id, search_data, message)
        
        await state.clear()
    except ValueError:
        await message.answer("Пожалуйста, введите число для зарплаты:")

@dp.message(Command("find"))
async def search_handler(message: types.Message):
    settings = await DatabaseService.get_search_settings(message.from_user.id)
    
    if not settings:
        await message.answer(
            "❌ У вас нет сохраненных настроек поиска.\n"
            "Сначала настройте параметры: /search"
        )
        return
    
    # Запускаем поиск вакансий по сохраненным настройкам
    await perform_vacancy_search(message.from_user.id, settings, message)

@dp.message(Command("help"))
async def help_handler(message: types.Message):
    await message.answer(
        "🤖 Помощь по боту:\n\n"
        "Основные команды:\n"
        "/start - регистрация/профиль\n"
        "/profile - мой профиль\n"
        "/search - настройки поиска (автоматически запускает поиск)\n"
        "/find - поиск вакансий по сохраненным настройкам\n"
        "/help - помощь\n\n"
        "Бот найдет для вас актуальные вакансии с hh.ru!"
    )

@dp.message()
async def text_handler(message: types.Message):
    text = message.text.lower()
    
    if text in ['привет', 'hello', 'hi']:
        await message.answer("Привет! 👋 Используйте /start для начала работы")
    elif any(word in text for word in ['ваканси', 'работа', 'поиск']):
        await message.answer("Используйте /search для настройки поиска")
    elif text.startswith('/'):
        await message.answer(f"Команда {message.text} не найдена. Используйте /help")
    else:
        await message.answer(
            "Не понял ваш запрос 🤔\n"
            "Используйте /help для списка команд"
        )

async def set_bot_commands(bot: Bot):
    """Устанавливаем команды бота для меню"""
    commands = [
        types.BotCommand(command="start", description="Начать работу"),
        types.BotCommand(command="search", description="Настройки поиска"),
        types.BotCommand(command="find", description="Поиск вакансий"),
        types.BotCommand(command="profile", description="Мой профиль"),
        types.BotCommand(command="help", description="Помощь"),
    ]
    await bot.set_my_commands(commands)

async def main():
    bot_token = os.getenv('TG_BOT_API_KEY')
    
    if not bot_token:
        logger.error("❌ TG_BOT_API_KEY не найден в .env файле!")
        return
    
    bot = Bot(token=bot_token)
    
    # Устанавливаем команды бота
    await set_bot_commands(bot)
    
    logger.info("🚀 Бот запускается...")
    
    try:
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())