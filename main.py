import asyncio
from datetime import datetime, timedelta
import logging
import os

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
import aiohttp
from dotenv import load_dotenv
from supabase import Client, create_client


# Загружаем переменные из .env
load_dotenv()

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация Supabase
supabase_url = os.getenv('SUPABASE_URL')
supabase_key = os.getenv('SUPABASE_KEY')
supabase: Client = create_client(supabase_url, supabase_key)

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
    waiting_for_employment = State()
    waiting_for_experience = State()
    waiting_for_company_type = State()
    waiting_for_freshness = State()

class DatabaseService:
    @staticmethod
    async def save_user(telegram_id: int, full_name: str, city: str = None, 
                       desired_position: str = None, skills: str = None, resume: str = None):
        """Сохраняем/обновляем пользователя в Supabase"""
        try:
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
                # Обновляем существующего пользователя
                result = supabase.table('users')\
                    .update(user_data)\
                    .eq('telegram_id', telegram_id)\
                    .execute()
            else:
                # Создаем нового пользователя
                user_data['created_at'] = datetime.utcnow().isoformat()
                result = supabase.table('users')\
                    .insert(user_data)\
                    .execute()
            
            return True
        except Exception as e:
            logger.error(f"Error saving user: {e}")
            return False

    @staticmethod
    async def get_user(telegram_id: int):
        """Получаем пользователя из Supabase"""
        try:
            result = supabase.table('users')\
                .select('*')\
                .eq('telegram_id', telegram_id)\
                .execute()
            
            if result.data:
                return result.data[0]
            return None
        except Exception as e:
            logger.error(f"Error getting user: {e}")
            return None

    @staticmethod
    async def save_search_settings(user_id: int, settings: dict):
        """Сохраняем настройки поиска в Supabase"""
        try:
            # Проверяем, есть ли уже настройки для этого пользователя
            existing = supabase.table('search_settings')\
                .select('*')\
                .eq('user_id', user_id)\
                .execute()
            
            settings_data = {
                'user_id': user_id,
                'position': settings.get('position'),
                'city': settings.get('city'),
                'min_salary': settings.get('min_salary'),
                'employment_type': settings.get('employment_type'),
                'experience': settings.get('experience'),
                'company_type': settings.get('company_type', 'any'),
                'fresh_only': settings.get('fresh_only', True),
                'updated_at': datetime.utcnow().isoformat()
            }
            
            if existing.data:
                # Обновляем существующие настройки
                result = supabase.table('search_settings')\
                    .update(settings_data)\
                    .eq('user_id', user_id)\
                    .execute()
            else:
                # Создаем новые настройки
                settings_data['created_at'] = datetime.utcnow().isoformat()
                result = supabase.table('search_settings')\
                    .insert(settings_data)\
                    .execute()
            
            return True
        except Exception as e:
            logger.error(f"Error saving search settings: {e}")
            return False

    @staticmethod
    async def get_search_settings(user_id: int):
        """Получаем настройки поиска из Supabase"""
        try:
            result = supabase.table('search_settings')\
                .select('*')\
                .eq('user_id', user_id)\
                .execute()
            
            if result.data:
                return result.data[0]
            return None
        except Exception as e:
            logger.error(f"Error getting search settings: {e}")
            return None

class HHService:
    @staticmethod
    async def search_vacancies(search_params: dict):
        """Поиск вакансий через HH API с фильтрами"""
        url = "https://api.hh.ru/vacancies"
        
        # Базовые параметры
        params = {
            'text': search_params.get('position', ''),
            'area': await HHService.get_area_id(search_params.get('city', 'Москва')),
            'per_page': 10,
            'page': 0
        }
        
        # Фильтр по зарплате
        if search_params.get('min_salary'):
            params['salary'] = search_params['min_salary']
            params['only_with_salary'] = True
        
        # Фильтр по типу занятости
        employment_map = {
            'full': 'full',
            'part': 'part', 
            'remote': 'remote'
        }
        if search_params.get('employment_type') in employment_map:
            params['employment'] = employment_map[search_params['employment_type']]
        
        # Фильтр по опыту
        experience_map = {
            'no_exp': 'noExperience',
            '1-3': 'between1And3',
            '3-6': 'between3And6',
            '6+': 'moreThan6'
        }
        if search_params.get('experience') in experience_map:
            params['experience'] = experience_map[search_params['experience']]
        
        # Фильтр по свежести (1-3 дня)
        if search_params.get('fresh_only', True):
            date_from = (datetime.now() - timedelta(days=3)).strftime('%Y-%m-%d')
            params['date_from'] = date_from
        
        # Фильтр по типу компании
        if search_params.get('company_type') == 'direct':
            params['employer_type'] = 'direct'
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get('items', [])
                    else:
                        logger.error(f"HH API error: {response.status}")
                        return []
        except Exception as e:
            logger.error(f"Error fetching vacancies: {e}")
            return []

    @staticmethod
    async def get_area_id(city_name: str) -> int:
        """Получение ID города для HH API"""
        area_map = {
            'москва': 1,
            'санкт-петербург': 2,
            'екатеринбург': 3,
            'новосибирск': 4,
            'казань': 88,
            'нижний новгород': 66,
            'красноярск': 54,
            'челябинск': 104,
            'самара': 78,
            'уфа': 99,
            'ростов-на-дону': 76,
            'краснодар': 53,
            'омск': 68,
            'воронеж': 26,
            'пермь': 72,
            'волгоград': 24
        }
        return area_map.get(city_name.lower(), 1)

    @staticmethod
    def format_vacancy(vacancy):
        """Форматирование вакансии для отправки"""
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
        published = vacancy.get('published_at', '')[:10]
        
        return (f"🏢 {title}\n"
                f"📊 Компания: {company}\n"
                f"💰 Зарплата: {salary_text}\n"
                f"📅 Опубликована: {published}\n"
                f"🔗 {url}")

@dp.message(Command("start"))
async def start_handler(message: types.Message, state: FSMContext):
    """Начало регистрации пользователя"""
    user = await DatabaseService.get_user(message.from_user.id)
    
    if user:
        await message.answer(
            f"С возвращением, {user.get('full_name', 'друг')}! 👋\n\n"
            f"Ваш профиль уже настроен.\n"
            f"Посмотреть настройки: /profile\n"
            f"Настроить поиск: /search_settings\n"
            f"Найти вакансии: /search"
        )
    else:
        await message.answer(
            "👋 Добро пожаловать в HH Bot!\n\n"
            "Я помогу вам найти работу на hh.ru с персонализированными рекомендациями.\n\n"
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
        "(например: Python, Django, PostgreSQL, Docker)\n\n"
        "Можно через запятую или списком"
    )
    await state.set_state(RegistrationStates.waiting_for_skills)

@dp.message(RegistrationStates.waiting_for_skills)
async def process_skills(message: types.Message, state: FSMContext):
    await state.update_data(skills=message.text)
    await message.answer(
        "Напишите краткое резюме о себе:\n"
        "(опыт работы, образование, достижения)\n\n"
        "Это поможет мне генерировать адаптированные сопроводительные письма"
    )
    await state.set_state(RegistrationStates.waiting_for_resume)

@dp.message(RegistrationStates.waiting_for_resume)
async def process_resume(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    
    # Сохраняем пользователя в базу
    success = await DatabaseService.save_user(
        telegram_id=message.from_user.id,
        full_name=user_data['full_name'],
        city=user_data['city'],
        desired_position=user_data['desired_position'],
        skills=user_data['skills'],
        resume=message.text
    )
    
    if success:
        await message.answer(
            f"✅ Регистрация завершена!\n\n"
            f"📋 Ваш профиль:\n"
            f"👤 {user_data['full_name']}\n"
            f"🏙️ {user_data['city']}\n"
            f"💼 {user_data['desired_position']}\n"
            f"🛠️ Навыки: {user_data['skills']}\n\n"
            f"Теперь настройте поиск вакансий: /search_settings\n"
            f"Или посмотрите ваш профиль: /profile"
        )
    else:
        await message.answer("❌ Ошибка сохранения профиля. Попробуйте снова: /start")
    
    await state.clear()

@dp.message(Command("profile"))
async def profile_handler(message: types.Message):
    """Показываем профиль пользователя"""
    user = await DatabaseService.get_user(message.from_user.id)
    
    if not user:
        await message.answer("❌ У вас нет профиля. Зарегистрируйтесь: /start")
        return
    
    await message.answer(
        f"📋 Ваш профиль:\n\n"
        f"👤 Имя: {user.get('full_name', 'Не указано')}\n"
        f"🏙️ Город: {user.get('city', 'Не указан')}\n"
        f"💼 Желаемая должность: {user.get('desired_position', 'Не указана')}\n"
        f"🛠️ Навыки: {user.get('skills', 'Не указаны')}\n"
        f"📄 Резюме: {user.get('resume', 'Не указано')[:200]}...\n\n"
        f"Изменить настройки поиска: /search_settings\n"
        f"Найти вакансии: /search"
    )

@dp.message(Command("help"))
async def help_handler(message: types.Message):
    await message.answer(
        "Я помогу вам с поиском работы на HH.ru!\n\n"
        "Функции:\n"
        "• Персонализированный поиск вакансий\n"
        "• Ежедневные уведомления\n"
        "• Настройка фильтров\n\n"
        "Основные команды:\n"
        "/start - регистрация/профиль\n"
        "/profile - мой профиль\n"
        "/search_settings - настройки поиска\n"
        "/search - поиск по настройкам\n"
        "/my_settings - мои настройки поиска"
    )

@dp.message(Command("my_settings"))
async def my_settings_handler(message: types.Message):
    """Показываем текущие настройки пользователя"""
    settings = await DatabaseService.get_search_settings(message.from_user.id)
    
    if not settings:
        await message.answer("❌ У вас нет сохраненных настроек поиска.\n"
                           "Используйте /search_settings для настройки")
        return
    
    employment_text = {
        'full': 'Полная занятость',
        'part': 'Частичная занятость', 
        'remote': 'Удаленная работа'
    }.get(settings['employment_type'], 'Не указано')
    
    experience_text = {
        'no_exp': 'Нет опыта',
        '1-3': '1-3 года',
        '3-6': '3-6 лет',
        '6+': 'Более 6 лет'
    }.get(settings['experience'], 'Не указано')
    
    await message.answer(
        f"⚙️ Ваши настройки поиска:\n\n"
        f"💼 Должность: {settings.get('position', 'Не указана')}\n"
        f"🏙️ Город: {settings.get('city', 'Не указан')}\n"
        f"💰 Зарплата от: {settings.get('min_salary', 'Не важно')} руб\n"
        f"🕒 Тип занятости: {employment_text}\n"
        f"👨‍💻 Опыт: {experience_text}\n"
        f"🏢 Тип компании: {settings.get('company_type', 'Любой')}\n"
        f"🕐 Свежие вакансии: {'Да' if settings.get('fresh_only') else 'Нет'}\n\n"
        f"Изменить настройки: /search_settings\n"
        f"Найти вакансии: /search"
    )

# ... (остальной код search_settings и search такой же как в предыдущем сообщении)
# [Здесь должен быть код для search_settings и search из предыдущего сообщения]

async def main():
    bot_token = os.getenv('TG_BOT_API_KEY')
    
    if not bot_token:
        logger.error("❌ TG_BOT_API_KEY не найден в .env файле!")
        return
    
    if not supabase_url or not supabase_key:
        logger.error("❌ SUPABASE_URL или SUPABASE_KEY не найдены в .env файле!")
        return
    
    bot = Bot(token=bot_token)
    logger.info("Бот запускается...")
    
    try:
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Ошибка: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())