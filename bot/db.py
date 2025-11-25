import asyncio
import asyncpg
from typing import Optional, List
from datetime import datetime
from bot.config import settings


class Database:
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None

    async def create_pool(self):
        """Создание пула подключений к базе данных"""
        self.pool = await asyncpg.create_pool(
            dsn=settings.database_url,
            min_size=5,
            max_size=20,
            command_timeout=60
        )
        return self.pool

    async def close_pool(self):
        """Закрытие пула подключений"""
        if self.pool:
            await self.pool.close()

    async def get_connection(self):
        """Получение подключения из пула"""
        if not self.pool:
            await self.create_pool()
        return self.pool


# Глобальный экземпляр базы данных
db = Database()


class User:
    def __init__(self, telegram_id: int, fio: Optional[str] = None, city: Optional[str] = None,
                 desired_position: Optional[str] = None, skills: Optional[str] = None,
                 base_resume: Optional[str] = None, llm_base_url: Optional[str] = None,
                 llm_api_key: Optional[str] = None, llm_model: Optional[str] = None):
        self.telegram_id = telegram_id
        self.fio = fio
        self.city = city
        self.desired_position = desired_position
        self.skills = skills
        self.base_resume = base_resume
        self.llm_base_url = llm_base_url
        self.llm_api_key = llm_api_key
        self.llm_model = llm_model
        self.created_at = datetime.now()

    async def save(self, conn: asyncpg.Connection):
        """Сохранение пользователя в базу данных"""
        await conn.execute('''
            INSERT INTO users (telegram_id, fio, city, desired_position, skills, base_resume,
                              llm_base_url, llm_api_key, llm_model, created_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            ON CONFLICT (telegram_id) DO UPDATE SET
                fio = EXCLUDED.fio,
                city = EXCLUDED.city,
                desired_position = EXCLUDED.desired_position,
                skills = EXCLUDED.skills,
                base_resume = EXCLUDED.base_resume,
                llm_base_url = EXCLUDED.llm_base_url,
                llm_api_key = EXCLUDED.llm_api_key,
                llm_model = EXCLUDED.llm_model
        ''', self.telegram_id, self.fio, self.city, self.desired_position,
                  self.skills, self.base_resume, self.llm_base_url,
                  self.llm_api_key, self.llm_model, self.created_at)

    @staticmethod
    async def get_by_telegram_id(conn: asyncpg.Connection, telegram_id: int):
        """Получение пользователя по telegram_id"""
        row = await conn.fetchrow('''
            SELECT * FROM users WHERE telegram_id = $1
        ''', telegram_id)

        if row:
            return User(
                telegram_id=row['telegram_id'],
                fio=row['fio'],
                city=row['city'],
                desired_position=row['desired_position'],
                skills=row['skills'],
                base_resume=row['base_resume'],
                llm_base_url=row['llm_base_url'],
                llm_api_key=row['llm_api_key'],
                llm_model=row['llm_model']
            )
        return None

    @staticmethod
    async def get_all_with_filters(conn: asyncpg.Connection):
        """Получение всех пользователей, у которых есть фильтры поиска"""
        rows = await conn.fetch('''
            SELECT * FROM users
            WHERE city IS NOT NULL OR desired_position IS NOT NULL
        ''')

        users = []
        for row in rows:
            users.append(User(
                telegram_id=row['telegram_id'],
                fio=row['fio'],
                city=row['city'],
                desired_position=row['desired_position'],
                skills=row['skills'],
                base_resume=row['base_resume'],
                llm_base_url=row['llm_base_url'],
                llm_api_key=row['llm_api_key'],
                llm_model=row['llm_model']
            ))
        return users


class VacancyFilter:
    def __init__(self, telegram_id: int, desired_position: Optional[str] = None,
                 city: Optional[str] = None, min_salary: Optional[int] = None,
                 metro_stations: Optional[List[str]] = None, freshness_days: Optional[int] = 3,
                 employment_type: Optional[str] = None, experience: Optional[str] = None,
                 direct_employers_only: bool = False, company_size: Optional[str] = None,
                 top_companies_only: bool = False):
        self.telegram_id = telegram_id
        self.desired_position = desired_position
        self.city = city
        self.min_salary = min_salary
        self.metro_stations = metro_stations or []
        self.freshness_days = freshness_days
        self.employment_type = employment_type
        self.experience = experience
        self.direct_employers_only = direct_employers_only
        self.company_size = company_size
        self.top_companies_only = top_companies_only

    async def save(self, conn: asyncpg.Connection):
        """Сохранение фильтров поиска в базу данных"""
        await conn.execute('''
            INSERT INTO vacancy_filters (telegram_id, desired_position, city, min_salary,
                                        metro_stations, freshness_days, employment_type,
                                        experience, direct_employers_only, company_size,
                                        top_companies_only)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            ON CONFLICT (telegram_id) DO UPDATE SET
                desired_position = EXCLUDED.desired_position,
                city = EXCLUDED.city,
                min_salary = EXCLUDED.min_salary,
                metro_stations = EXCLUDED.metro_stations,
                freshness_days = EXCLUDED.freshness_days,
                employment_type = EXCLUDED.employment_type,
                experience = EXCLUDED.experience,
                direct_employers_only = EXCLUDED.direct_employers_only,
                company_size = EXCLUDED.company_size,
                top_companies_only = EXCLUDED.top_companies_only
        ''', self.telegram_id, self.desired_position, self.city, self.min_salary,
                  self.metro_stations, self.freshness_days, self.employment_type,
                  self.experience, self.direct_employers_only, self.company_size,
                  self.top_companies_only)

    @staticmethod
    async def get_by_telegram_id(conn: asyncpg.Connection, telegram_id: int):
        """Получение фильтров поиска по telegram_id"""
        row = await conn.fetchrow('''
            SELECT * FROM vacancy_filters WHERE telegram_id = $1
        ''', telegram_id)

        if row:
            return VacancyFilter(
                telegram_id=row['telegram_id'],
                desired_position=row['desired_position'],
                city=row['city'],
                min_salary=row['min_salary'],
                metro_stations=row['metro_stations'],
                freshness_days=row['freshness_days'],
                employment_type=row['employment_type'],
                experience=row['experience'],
                direct_employers_only=row['direct_employers_only'],
                company_size=row['company_size'],
                top_companies_only=row['top_companies_only']
            )
        return None


class Vacancy:
    def __init__(self, external_id: str, title: str, company: str, city: Optional[str] = None,
                 salary: Optional[str] = None, url: Optional[str] = None, description: Optional[str] = None,
                 created_at: Optional[datetime] = None):
        self.external_id = external_id
        self.title = title
        self.company = company
        self.city = city
        self.salary = salary
        self.url = url
        self.description = description
        self.created_at = created_at or datetime.now()

    async def save(self, conn: asyncpg.Connection):
        """Сохранение вакансии в базу данных"""
        await conn.execute('''
            INSERT INTO vacancies (external_id, title, company, city, salary, url, description, created_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            ON CONFLICT (external_id) DO NOTHING
        ''', self.external_id, self.title, self.company, self.city,
                  self.salary, self.url, self.description, self.created_at)

    @staticmethod
    async def get_by_external_id(conn: asyncpg.Connection, external_id: str):
        """Получение вакансии по external_id"""
        row = await conn.fetchrow('''
            SELECT * FROM vacancies WHERE external_id = $1
        ''', external_id)

        if row:
            return Vacancy(
                external_id=row['external_id'],
                title=row['title'],
                company=row['company'],
                city=row['city'],
                salary=row['salary'],
                url=row['url'],
                description=row['description'],
                created_at=row['created_at']
            )
        return None

    @staticmethod
    async def get_new_vacancies_for_user(conn: asyncpg.Connection, telegram_id: int,
                                        filter_params: VacancyFilter, limit: int = 10):
        """Получение новых вакансий для пользователя по его фильтрам"""
        # Базовый SQL-запрос
        query = '''
            SELECT * FROM vacancies
            WHERE created_at > $1
        '''

        # Параметры для фильтрации
        params = [datetime.now().replace(day=datetime.now().day - filter_params.freshness_days)]

        # Добавляем фильтры по мере необходимости
        if filter_params.city:
            query += " AND city = ${}".format(len(params) + 1)
            params.append(filter_params.city)

        if filter_params.min_salary:
            # Предполагаем, что в базе данных зарплата хранится в определенном формате
            # Нужно будет адаптировать в зависимости от формата хранения
            pass  # Пока пропускаем, нужно уточнить формат хранения зарплаты

        query += " LIMIT ${}".format(len(params) + 1)
        params.append(limit)

        rows = await conn.fetch(query, *params)

        vacancies = []
        for row in rows:
            vacancies.append(Vacancy(
                external_id=row['external_id'],
                title=row['title'],
                company=row['company'],
                city=row['city'],
                salary=row['salary'],
                url=row['url'],
                description=row['description'],
                created_at=row['created_at']
            ))
        return vacancies


class UserVacancyInteraction:
    def __init__(self, telegram_id: int, vacancy_external_id: str,
                 is_interesting: Optional[bool] = None, resume_generated: bool = False,
                 cover_letter_generated: bool = False):
        self.telegram_id = telegram_id
        self.vacancy_external_id = vacancy_external_id
        self.is_interesting = is_interesting
        self.resume_generated = resume_generated
        self.cover_letter_generated = cover_letter_generated
        self.interacted_at = datetime.now()

    async def save(self, conn: asyncpg.Connection):
        """Сохранение взаимодействия пользователя с вакансией"""
        await conn.execute('''
            INSERT INTO user_vacancy_interactions (telegram_id, vacancy_external_id, is_interesting,
                                                  resume_generated, cover_letter_generated, interacted_at)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (telegram_id, vacancy_external_id) DO UPDATE SET
                is_interesting = EXCLUDED.is_interesting,
                resume_generated = EXCLUDED.resume_generated,
                cover_letter_generated = EXCLUDED.cover_letter_generated,
                interacted_at = EXCLUDED.interacted_at
        ''', self.telegram_id, self.vacancy_external_id, self.is_interesting,
                  self.resume_generated, self.cover_letter_generated, self.interacted_at)