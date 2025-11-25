from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from aiogram.filters import Command
from bot.db import db, User, VacancyFilter, Vacancy, UserVacancyInteraction
from bot.services import HHApiService, format_hh_vacancy, LLMService
import asyncpg


router = Router()


@router.message(Command("start"))
async def start_handler(message: Message):
    """Обработчик команды /start - регистрация пользователя"""
    telegram_id = message.from_user.id
    full_name = message.from_user.full_name

    # Подключение к базе данных
    conn = await db.get_connection()
    connection = await conn.acquire()

    try:
        # Проверяем, существует ли пользователь
        existing_user = await User.get_by_telegram_id(connection, telegram_id)

        if existing_user:
            # Пользователь уже существует
            await message.answer(
                f"Привет, {full_name}! Вы уже зарегистрированы в системе.\n"
                f"Для настройки поиска вакансий используйте команду /search_settings\n"
                f"Для просмотра вакансий используйте команду /vacancies"
            )
        else:
            # Создаем нового пользователя
            user = User(telegram_id=telegram_id, fio=full_name)
            await user.save(connection)

            await message.answer(
                f"Привет, {full_name}! Добро пожаловать в бот для поиска вакансий на HH.ru!\n\n"
                f"Для начала настройте параметры поиска вакансий с помощью команды /search_settings\n\n"
                f"Доступные команды:\n"
                f"/search_settings - Настройка фильтров поиска\n"
                f"/vacancies - Просмотр вакансий\n"
                f"/my_profile - Просмотр и редактирование профиля"
            )
    except Exception as e:
        await message.answer("Произошла ошибка при регистрации. Пожалуйста, попробуйте позже.")
        print(f"Ошибка при обработке команды /start: {e}")
    finally:
        await conn.release()


@router.message(Command("my_profile"))
async def profile_handler(message: Message):
    """Обработчик команды /my_profile - просмотр профиля пользователя"""
    telegram_id = message.from_user.id

    # Подключение к базе данных
    conn = await db.get_connection()
    connection = await conn.acquire()

    try:
        user = await User.get_by_telegram_id(connection, telegram_id)

        if user:
            profile_text = f"Ваш профиль:\n\n"
            profile_text += f"Имя: {user.fio or 'Не указано'}\n"
            profile_text += f"Город: {user.city or 'Не указан'}\n"
            profile_text += f"Желаемая должность: {user.desired_position or 'Не указана'}\n"
            profile_text += f"Навыки: {user.skills or 'Не указаны'}\n"
            profile_text += f"Базовое резюме: {user.base_resume or 'Отсутствует'}\n\n"
            profile_text += f"Для редактирования профиля используйте команду /edit_profile"

            await message.answer(profile_text)
        else:
            await message.answer("Вы не зарегистрированы. Используйте команду /start для регистрации.")
    except Exception as e:
        await message.answer("Произошла ошибка при получении профиля. Пожалуйста, попробуйте позже.")
        print(f"Ошибка при обработке команды /my_profile: {e}")
    finally:
        await conn.release()


@router.message(Command("search_settings"))
async def search_settings_handler(message: Message):
    """Обработчик команды /search_settings - настройка фильтров поиска"""
    telegram_id = message.from_user.id

    # Подключение к базе данных
    conn = await db.get_connection()
    connection = await conn.acquire()

    try:
        # Получаем текущие фильтры пользователя
        current_filter = await VacancyFilter.get_by_telegram_id(connection, telegram_id)

        if current_filter:
            settings_text = f"Ваши текущие настройки поиска:\n\n"
            settings_text += f"Желаемая должность: {current_filter.desired_position or 'Не указана'}\n"
            settings_text += f"Город: {current_filter.city or 'Не указан'}\n"
            settings_text += f"Минимальная зарплата: {current_filter.min_salary or 'Не указана'}\n"
            settings_text += f"Свежесть вакансий: {current_filter.freshness_days} дней\n"
            settings_text += f"Тип занятости: {current_filter.employment_type or 'Любой'}\n"
            settings_text += f"Опыт работы: {current_filter.experience or 'Любой'}\n"
            settings_text += f"Только прямые работодатели: {'Да' if current_filter.direct_employers_only else 'Нет'}\n"
            settings_text += f"Только ТОП-компании: {'Да' if current_filter.top_companies_only else 'Нет'}\n\n"
            settings_text += f"Для изменения настроек используйте следующие команды:\n"
            settings_text += f"/set_position [название должности] - Установить желаемую должность\n"
            settings_text += f"/set_city [название города] - Установить город\n"
            settings_text += f"/set_min_salary [число] - Установить минимальную зарплату\n"
        else:
            settings_text = f"Вы не установили настройки поиска.\n\n"
            settings_text += f"Для установки настроек используйте следующие команды:\n"
            settings_text += f"/set_position [название должности] - Установить желаемую должность\n"
            settings_text += f"/set_city [название города] - Установить город\n"
            settings_text += f"/set_min_salary [число] - Установить минимальную зарплату\n\n"
            settings_text += f"Пример: /set_position Python разработчик"

        await message.answer(settings_text)
    except Exception as e:
        await message.answer("Произошла ошибка при получении настроек поиска. Пожалуйста, попробуйте позже.")
        print(f"Ошибка при обработке команды /search_settings: {e}")
    finally:
        await conn.release()


@router.message(Command("set_position"))
async def set_position_handler(message: Message):
    """Обработчик команды /set_position - установка желаемой должности"""
    telegram_id = message.from_user.id
    command_args = message.text.split(maxsplit=1)

    if len(command_args) < 2:
        await message.answer("Пожалуйста, укажите желаемую должность. Пример: /set_position Python разработчик")
        return

    desired_position = command_args[1]

    # Подключение к базе данных
    conn = await db.get_connection()
    connection = await conn.acquire()

    try:
        # Получаем или создаем фильтр вакансий для пользователя
        current_filter = await VacancyFilter.get_by_telegram_id(connection, telegram_id)

        if current_filter:
            # Обновляем существующий фильтр
            current_filter.desired_position = desired_position
        else:
            # Создаем новый фильтр
            current_filter = VacancyFilter(telegram_id=telegram_id, desired_position=desired_position)

        await current_filter.save(connection)
        await message.answer(f"Ваша желаемая должность установлена как: {desired_position}")
    except Exception as e:
        await message.answer("Произошла ошибка при сохранении должности. Пожалуйста, попробуйте позже.")
        print(f"Ошибка при обработке команды /set_position: {e}")
    finally:
        await conn.release()


@router.message(Command("set_city"))
async def set_city_handler(message: Message):
    """Обработчик команды /set_city - установка города"""
    telegram_id = message.from_user.id
    command_args = message.text.split(maxsplit=1)

    if len(command_args) < 2:
        await message.answer("Пожалуйста, укажите город. Пример: /set_city Москва")
        return

    city = command_args[1]

    # Подключение к базе данных
    conn = await db.get_connection()
    connection = await conn.acquire()

    try:
        # Получаем или создаем фильтр вакансий для пользователя
        current_filter = await VacancyFilter.get_by_telegram_id(connection, telegram_id)

        if current_filter:
            # Обновляем существующий фильтр
            current_filter.city = city
        else:
            # Создаем новый фильтр
            current_filter = VacancyFilter(telegram_id=telegram_id, city=city)

        await current_filter.save(connection)
        await message.answer(f"Ваш город установлен как: {city}")
    except Exception as e:
        await message.answer("Произошла ошибка при сохранении города. Пожалуйста, попробуйте позже.")
        print(f"Ошибка при обработке команды /set_city: {e}")
    finally:
        await conn.release()


@router.message(Command("set_min_salary"))
async def set_min_salary_handler(message: Message):
    """Обработчик команды /set_min_salary - установка минимальной зарплаты"""
    telegram_id = message.from_user.id
    command_args = message.text.split(maxsplit=1)

    if len(command_args) < 2:
        await message.answer("Пожалуйста, укажите минимальную зарплату. Пример: /set_min_salary 100000")
        return

    try:
        min_salary = int(command_args[1])
        if min_salary < 0:
            await message.answer("Минимальная зарплата не может быть отрицательной.")
            return
    except ValueError:
        await message.answer("Пожалуйста, укажите корректное число для минимальной зарплаты.")
        return

    # Подключение к базе данных
    conn = await db.get_connection()
    connection = await conn.acquire()

    try:
        # Получаем или создаем фильтр вакансий для пользователя
        current_filter = await VacancyFilter.get_by_telegram_id(connection, telegram_id)

        if current_filter:
            # Обновляем существующий фильтр
            current_filter.min_salary = min_salary
        else:
            # Создаем новый фильтр
            current_filter = VacancyFilter(telegram_id=telegram_id, min_salary=min_salary)

        await current_filter.save(connection)
        await message.answer(f"Ваша минимальная зарплата установлена как: {min_salary}")
    except Exception as e:
        await message.answer("Произошла ошибка при сохранении минимальной зарплаты. Пожалуйста, попробуйте позже.")
        print(f"Ошибка при обработке команды /set_min_salary: {e}")
    finally:
        await conn.release()


@router.message(Command("set_llm_base_url"))
async def set_llm_base_url_handler(message: Message):
    """Обработчик команды /set_llm_base_url - установка URL LLM API"""
    telegram_id = message.from_user.id
    command_args = message.text.split(maxsplit=1)

    if len(command_args) < 2:
        await message.answer("Пожалуйста, укажите URL LLM API. Пример: /set_llm_base_url https://api.openai.com/v1")
        return

    base_url = command_args[1]

    # Подключение к базе данных
    conn = await db.get_connection()
    connection = await conn.acquire()

    try:
        # Получаем пользователя
        user = await User.get_by_telegram_id(connection, telegram_id)

        if user:
            # Обновляем настройки LLM
            user.llm_base_url = base_url
            await user.save(connection)
            await message.answer(f"URL LLM API установлен как: {base_url}")
        else:
            await message.answer("Сначала зарегистрируйтесь, используя команду /start")
    except Exception as e:
        await message.answer("Произошла ошибка при сохранении URL LLM API. Пожалуйста, попробуйте позже.")
        print(f"Ошибка при обработке команды /set_llm_base_url: {e}")
    finally:
        await conn.release()


@router.message(Command("set_llm_api_key"))
async def set_llm_api_key_handler(message: Message):
    """Обработчик команды /set_llm_api_key - установка API ключа LLM"""
    telegram_id = message.from_user.id
    command_args = message.text.split(maxsplit=1)

    if len(command_args) < 2:
        await message.answer("Пожалуйста, укажите API ключ LLM. Пример: /set_llm_api_key your_api_key_here")
        return

    api_key = command_args[1]

    # Подключение к базе данных
    conn = await db.get_connection()
    connection = await conn.acquire()

    try:
        # Получаем пользователя
        user = await User.get_by_telegram_id(connection, telegram_id)

        if user:
            # Обновляем настройки LLM
            user.llm_api_key = api_key
            await user.save(connection)
            await message.answer("API ключ LLM установлен.")
        else:
            await message.answer("Сначала зарегистрируйтесь, используя команду /start")
    except Exception as e:
        await message.answer("Произошла ошибка при сохранении API ключа LLM. Пожалуйста, попробуйте позже.")
        print(f"Ошибка при обработке команды /set_llm_api_key: {e}")
    finally:
        await conn.release()


@router.message(Command("set_llm_model"))
async def set_llm_model_handler(message: Message):
    """Обработчик команды /set_llm_model - установка модели LLM"""
    telegram_id = message.from_user.id
    command_args = message.text.split(maxsplit=1)

    if len(command_args) < 2:
        await message.answer("Пожалуйста, укажите название модели LLM. Пример: /set_llm_model gpt-3.5-turbo")
        return

    model = command_args[1]

    # Подключение к базе данных
    conn = await db.get_connection()
    connection = await conn.acquire()

    try:
        # Получаем пользователя
        user = await User.get_by_telegram_id(connection, telegram_id)

        if user:
            # Обновляем настройки LLM
            user.llm_model = model
            await user.save(connection)
            await message.answer(f"Модель LLM установлена как: {model}")
        else:
            await message.answer("Сначала зарегистрируйтесь, используя команду /start")
    except Exception as e:
        await message.answer("Произошла ошибка при сохранении модели LLM. Пожалуйста, попробуйте позже.")
        print(f"Ошибка при обработке команды /set_llm_model: {e}")
    finally:
        await conn.release()


@router.message(Command("vacancies"))
async def vacancies_handler(message: Message):
    """Обработчик команды /vacancies - показ вакансий"""
    telegram_id = message.from_user.id

    # Подключение к базе данных
    conn = await db.get_connection()
    connection = await conn.acquire()

    try:
        # Получаем фильтры пользователя
        user_filter = await VacancyFilter.get_by_telegram_id(connection, telegram_id)

        if not user_filter or not user_filter.city and not user_filter.desired_position:
            await message.answer(
                "Для поиска вакансий сначала установите параметры поиска.\n"
                "Используйте команду /search_settings для настройки фильтров."
            )
            return

        # Подключаемся к HH API и ищем вакансии
        async with HHApiService() as hh_service:
            results = await hh_service.search_vacancies(
                keyword=user_filter.desired_position,
                city=user_filter.city,
                min_salary=user_filter.min_salary,
                period=user_filter.freshness_days
            )

            if results["found"] == 0:
                await message.answer("К сожалению, не найдено вакансий по вашим критериям.")
                return

            # Обрабатываем и сохраняем найденные вакансии
            vacancies = results["items"][:5]  # Берем первые 5 вакансий

            for vacancy_data in vacancies:
                formatted_vacancy = format_hh_vacancy(vacancy_data)

                # Создаем и сохраняем вакансию в БД
                vacancy = Vacancy(
                    external_id=formatted_vacancy['external_id'],
                    title=formatted_vacancy['title'],
                    company=formatted_vacancy['company'],
                    city=formatted_vacancy['city'],
                    salary=formatted_vacancy['salary'],
                    url=formatted_vacancy['url'],
                    description=formatted_vacancy['description']
                )
                await vacancy.save(connection)

                # Отправляем вакансию пользователю
                vacancy_text = f"📍 {formatted_vacancy['city']}\n"
                vacancy_text += f"🏢 {formatted_vacancy['company']}\n"
                vacancy_text += f"💼 {formatted_vacancy['title']}\n"
                if formatted_vacancy['salary']:
                    vacancy_text += f"💰 {formatted_vacancy['salary']}\n"
                vacancy_text += f"📝 {formatted_vacancy['description'][:100]}...\n"
                vacancy_text += f"🔗 {formatted_vacancy['url']}"

                # Создаем inline-кнопки для взаимодействия
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(text="Сгенерировать резюме", callback_data=f"resume_{formatted_vacancy['external_id']}"),
                        InlineKeyboardButton(text="Сгенерировать cover letter", callback_data=f"cover_{formatted_vacancy['external_id']}")
                    ],
                    [
                        InlineKeyboardButton(text="Неинтересно", callback_data=f"not_interesting_{formatted_vacancy['external_id']}")
                    ]
                ])

                await message.answer(vacancy_text, reply_markup=keyboard)

    except Exception as e:
        await message.answer("Произошла ошибка при поиске вакансий. Пожалуйста, попробуйте позже.")
        print(f"Ошибка при обработке команды /vacancies: {e}")
    finally:
        await conn.release()


@router.callback_query(F.data.startswith('resume_'))
async def handle_generate_resume(callback_query: CallbackQuery):
    """Обработка запроса на генерацию резюме"""
    vacancy_id = callback_query.data.split('_')[1]
    telegram_id = callback_query.from_user.id

    # Подключение к базе данных
    conn = await db.get_connection()
    connection = await conn.acquire()

    try:
        # Получаем информацию о пользователе
        user = await User.get_by_telegram_id(connection, telegram_id)

        if not user:
            await callback_query.message.answer("Сначала зарегистрируйтесь, используя команду /start")
            return

        # Проверяем, есть ли у пользователя настроенные LLM параметры
        llm_settings = {
            'llm_base_url': user.llm_base_url,
            'llm_api_key': user.llm_api_key,
            'llm_model': user.llm_model
        }

        # Получаем вакансию
        vacancy = await Vacancy.get_by_external_id(connection, vacancy_id)

        if not vacancy:
            await callback_query.message.answer("Ошибка: вакансия не найдена.")
            return

        # Если у пользователя нет настроенных LLM параметров, просим их задать
        if not user.llm_api_key:
            await callback_query.message.answer(
                "Для генерации резюме необходимо настроить параметры LLM.\n"
                "Используйте команды:\n"
                "/set_llm_base_url [URL] - Установить URL LLM API\n"
                "/set_llm_api_key [ключ] - Установить API ключ\n"
                "/set_llm_model [название модели] - Установить модель"
            )
            return

        # Генерируем резюме
        llm_service = LLMService()
        user_info = {
            'fio': user.fio,
            'skills': user.skills,
            'base_resume': user.base_resume
        }
        vacancy_info = {
            'title': vacancy.title,
            'company': vacancy.company,
            'city': vacancy.city,
            'salary': vacancy.salary,
            'description': vacancy.description
        }

        resume = await llm_service.generate_resume(user_info, vacancy_info, llm_settings)

        # Сохраняем информацию о взаимодействии
        interaction = UserVacancyInteraction(
            telegram_id=telegram_id,
            vacancy_external_id=vacancy_id,
            resume_generated=True
        )
        await interaction.save(connection)

        # Отправляем сгенерированное резюме пользователю
        await callback_query.message.answer(f"Ваше персонализированное резюме:\n\n{resume}")

    except Exception as e:
        await callback_query.message.answer("Произошла ошибка при генерации резюме. Пожалуйста, попробуйте позже.")
        print(f"Ошибка при генерации резюме: {e}")
    finally:
        await conn.release()

    # Отвечаем на callback, чтобы убрать "часики" в интерфейсе
    await callback_query.answer()


@router.callback_query(F.data.startswith('cover_'))
async def handle_generate_cover_letter(callback_query: CallbackQuery):
    """Обработка запроса на генерацию сопроводительного письма"""
    vacancy_id = callback_query.data.split('_')[1]
    telegram_id = callback_query.from_user.id

    # Подключение к базе данных
    conn = await db.get_connection()
    connection = await conn.acquire()

    try:
        # Получаем информацию о пользователе
        user = await User.get_by_telegram_id(connection, telegram_id)

        if not user:
            await callback_query.message.answer("Сначала зарегистрируйтесь, используя команду /start")
            return

        # Проверяем, есть ли у пользователя настроенные LLM параметры
        llm_settings = {
            'llm_base_url': user.llm_base_url,
            'llm_api_key': user.llm_api_key,
            'llm_model': user.llm_model
        }

        # Получаем вакансию
        vacancy = await Vacancy.get_by_external_id(connection, vacancy_id)

        if not vacancy:
            await callback_query.message.answer("Ошибка: вакансия не найдена.")
            return

        # Если у пользователя нет настроенных LLM параметров, просим их задать
        if not user.llm_api_key:
            await callback_query.message.answer(
                "Для генерации сопроводительного письма необходимо настроить параметры LLM.\n"
                "Используйте команды:\n"
                "/set_llm_base_url [URL] - Установить URL LLM API\n"
                "/set_llm_api_key [ключ] - Установить API ключ\n"
                "/set_llm_model [название модели] - Установить модель"
            )
            return

        # Генерируем сопроводительное письмо
        llm_service = LLMService()
        user_info = {
            'fio': user.fio,
            'skills': user.skills,
            'base_resume': user.base_resume
        }
        vacancy_info = {
            'title': vacancy.title,
            'company': vacancy.company,
            'city': vacancy.city,
            'description': vacancy.description
        }

        cover_letter = await llm_service.generate_cover_letter(user_info, vacancy_info, llm_settings)

        # Сохраняем информацию о взаимодействии
        interaction = UserVacancyInteraction(
            telegram_id=telegram_id,
            vacancy_external_id=vacancy_id,
            cover_letter_generated=True
        )
        await interaction.save(connection)

        # Отправляем сгенерированное сопроводительное письмо пользователю
        await callback_query.message.answer(f"Ваше персонализированное сопроводительное письмо:\n\n{cover_letter}")

    except Exception as e:
        await callback_query.message.answer("Произошла ошибка при генерации сопроводительного письма. Пожалуйста, попробуйте позже.")
        print(f"Ошибка при генерации сопроводительного письма: {e}")
    finally:
        await conn.release()

    # Отвечаем на callback, чтобы убрать "часики" в интерфейсе
    await callback_query.answer()


@router.callback_query(F.data.startswith('not_interesting_'))
async def handle_not_interesting(callback_query: CallbackQuery):
    """Обработка отметки вакансии как неинтересной"""
    vacancy_id = callback_query.data.split('_')[2]
    telegram_id = callback_query.from_user.id

    # Подключение к базе данных
    conn = await db.get_connection()
    connection = await conn.acquire()

    try:
        # Сохраняем информацию о взаимодействии
        interaction = UserVacancyInteraction(
            telegram_id=telegram_id,
            vacancy_external_id=vacancy_id,
            is_interesting=False
        )
        await interaction.save(connection)

        await callback_query.message.answer("Вакансия отмечена как неинтересная. Спасибо за обратную связь!")

    except Exception as e:
        await callback_query.message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")
        print(f"Ошибка при обработке 'неинтересно': {e}")
    finally:
        await conn.release()

    # Отвечаем на callback, чтобы убрать "часики" в интерфейсе
    await callback_query.answer()