import asyncio
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from aiogram import Bot
from bot.config import settings
from bot.db import db, User, VacancyFilter, Vacancy
from bot.services import HHApiService, format_hh_vacancy


class DailyMailer:
    def __init__(self, bot: Bot):
        self.bot = bot
        self.scheduler = AsyncIOScheduler()

    async def start_scheduler(self):
        """Запуск планировщика для ежедневной рассылки"""
        # Рассылаем вакансии каждый день в 9:00 утра
        self.scheduler.add_job(
            self.send_daily_vacancies,
            CronTrigger(hour=9, minute=0),
            id='daily_vacancies',
            name='Ежедневная рассылка вакансий'
        )
        self.scheduler.start()

    async def stop_scheduler(self):
        """Остановка планировщика"""
        self.scheduler.shutdown()

    async def send_daily_vacancies(self):
        """Отправка ежедневных вакансий всем пользователям с настроенными фильтрами"""
        conn = await db.get_connection()
        connection = await conn.acquire()

        try:
            # Получаем всех пользователей с настроенными фильтрами
            users = await User.get_all_with_filters(connection)

            for user in users:
                # Получаем фильтры для данного пользователя
                user_filter = await VacancyFilter.get_by_telegram_id(connection, user.telegram_id)

                if user_filter:
                    # Подключаемся к HH API и ищем вакансии
                    async with HHApiService() as hh_service:
                        results = await hh_service.search_vacancies(
                            keyword=user_filter.desired_position,
                            city=user_filter.city,
                            min_salary=user_filter.min_salary,
                            period=user_filter.freshness_days
                        )

                        if results["found"] > 0:
                            # Обрабатываем и сохраняем найденные вакансии
                            vacancies = results["items"][:5]  # Берем первые 5 вакансий

                            if vacancies:
                                message_text = f"Ежедневная подборка вакансий для вас:\n\n"

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

                                    # Добавляем вакансию в сообщение
                                    message_text += f"📍 {formatted_vacancy['city']}\n"
                                    message_text += f"🏢 {formatted_vacancy['company']}\n"
                                    message_text += f"💼 {formatted_vacancy['title']}\n"
                                    if formatted_vacancy['salary']:
                                        message_text += f"💰 {formatted_vacancy['salary']}\n"
                                    message_text += f"📝 {formatted_vacancy['description'][:100]}...\n"
                                    message_text += f"🔗 {formatted_vacancy['url']}\n\n"

                                # Отправляем сообщение пользователю
                                try:
                                    await self.bot.send_message(user.telegram_id, message_text)
                                except Exception as e:
                                    print(f"Ошибка при отправке сообщения пользователю {user.telegram_id}: {e}")
                        else:
                            # Если не найдено вакансий, отправляем сообщение об этом
                            try:
                                await self.bot.send_message(
                                    user.telegram_id,
                                    "Сегодня не найдено новых вакансий по вашим критериям. "
                                    "Рекомендуем проверить настройки поиска с помощью команды /search_settings"
                                )
                            except Exception as e:
                                print(f"Ошибка при отправке сообщения пользователю {user.telegram_id}: {e}")
        except Exception as e:
            print(f"Ошибка при отправке ежедневных вакансий: {e}")
        finally:
            await conn.release()