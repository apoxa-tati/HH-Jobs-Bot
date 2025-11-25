import aiohttp
import asyncio
from typing import Optional, Dict, List
from datetime import datetime, timedelta
from bot.config import settings


class HHApiService:
    def __init__(self):
        self.base_url = "https://api.hh.ru"
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        """Асинхронный контекстный менеджер для создания сессии"""
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Асинхронный контекстный менеджер для закрытия сессии"""
        if self.session:
            await self.session.close()

    async def search_vacancies(self, keyword: Optional[str] = None, city: Optional[str] = None,
                              min_salary: Optional[int] = None, employment: Optional[str] = None,
                              experience: Optional[str] = None, period: int = 3,
                              direct_employers_only: bool = False, top_companies_only: bool = False,
                              page: int = 0, per_page: int = 100) -> Dict:
        """
        Поиск вакансий по заданным параметрам
        """
        # Определяем ID области для города
        area_id = None
        if city:
            area_id = await self._get_area_id(city)

        # Формируем параметры запроса
        params = {}
        if keyword:
            params['text'] = keyword
        if area_id:
            params['area'] = area_id
        if min_salary:
            params['salary'] = min_salary
            params['only_with_salary'] = True
        params['period'] = period  # Вакансии за последние N дней

        try:
            async with self.session.get(f"{self.base_url}/vacancies", params=params) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    print(f"Ошибка при поиске вакансий: {response.status}")
                    # Возвращаем пустой результат в случае ошибки
                    return {"items": [], "found": 0}
        except Exception as e:
            print(f"Ошибка при обращении к API HH.ru: {e}")
            return {"items": [], "found": 0}

    async def _get_area_id(self, city_name: str) -> Optional[str]:
        """
        Получение ID области по названию города
        """
        try:
            async with self.session.get(f"{self.base_url}/suggests/areas", params={"text": city_name}) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("items"):
                        # Возвращаем ID первого совпадения
                        return data["items"][0]["id"]
        except Exception as e:
            print(f"Ошибка при поиске ID области для города {city_name}: {e}")

        # Если не найдено, проверим основные города
        default_areas = {
            "москва": "1",
            "санкт-петербург": "2",
            "екатеринбург": "3",
            "новосибирск": "4",
            "казань": "7",
            "минск": "115"
        }

        return default_areas.get(city_name.lower())

    async def get_vacancy_by_id(self, vacancy_id: str) -> Optional[Dict]:
        """
        Получение информации о вакансии по ID
        """
        try:
            async with self.session.get(f"{self.base_url}/vacancies/{vacancy_id}") as response:
                if response.status == 200:
                    return await response.json()
                else:
                    print(f"Ошибка при получении вакансии: {response.status}")
                    return None
        except Exception as e:
            print(f"Ошибка при обращении к API HH.ru для получения вакансии {vacancy_id}: {e}")
            return None


# Функция для преобразования вакансий из формата HH в наш формат
def format_hh_vacancy(hh_vacancy: Dict) -> Dict:
    """
    Преобразовать вакансию из формата HH в наш внутренний формат
    """
    salary_info = hh_vacancy.get('salary')
    salary_text = None
    if salary_info:
        salary_from = salary_info.get('from')
        salary_to = salary_info.get('to')
        salary_currency = salary_info.get('currency', '')

        if salary_from and salary_to:
            salary_text = f"{salary_from}-{salary_to} {salary_currency}"
        elif salary_from:
            salary_text = f"от {salary_from} {salary_currency}"
        elif salary_to:
            salary_text = f"до {salary_to} {salary_currency}"

    # Получаем описание вакансии (иногда оно может быть в другом формате)
    description = hh_vacancy.get('snippet', {}).get('requirement', '')

    return {
        'external_id': hh_vacancy.get('id'),
        'title': hh_vacancy.get('name', ''),
        'company': hh_vacancy.get('employer', {}).get('name', ''),
        'city': hh_vacancy.get('area', {}).get('name', ''),
        'salary': salary_text,
        'url': hh_vacancy.get('alternate_url'),
        'description': description,
        'created_at': datetime.fromisoformat(hh_vacancy.get('created_at').replace('Z', '+00:00')) if hh_vacancy.get('created_at') else datetime.now()
    }


class LLMService:
    def __init__(self):
        pass

    async def generate_resume(self, user_info: Dict, vacancy_info: Dict, llm_settings: Dict) -> str:
        """
        Генерация персонализированного резюме для конкретной вакансии
        """
        # Подготовка промпта для генерации резюме
        prompt = f"""
Создай профессиональное резюме для кандидата, подходящего под следующую вакансию:

ВАКАНСИЯ:
- Название: {vacancy_info.get('title', 'Не указано')}
- Компания: {vacancy_info.get('company', 'Не указано')}
- Город: {vacancy_info.get('city', 'Не указано')}
- Зарплата: {vacancy_info.get('salary', 'Не указано')}
- Описание: {vacancy_info.get('description', 'Не указано')[:200]}

ИНФОРМАЦИЯ О КАНДИДАТЕ:
- Имя: {user_info.get('fio', 'Не указано')}
- Навыки: {user_info.get('skills', 'Не указаны')}
- Базовое резюме: {user_info.get('base_resume', 'Отсутствует')}

Требования:
1. Резюме должно быть адаптировано под конкретную вакансию
2. Учитывать ключевые навыки и требования из описания вакансии
3. Выделить соответствующие навыки и опыт кандидата
4. Использовать профессиональный стиль
5. Длина резюме - не более 500 слов

Резюме:
"""

        # Отправляем запрос к LLM
        response = await self._send_to_llm(prompt, llm_settings)
        return response

    async def generate_cover_letter(self, user_info: Dict, vacancy_info: Dict, llm_settings: Dict) -> str:
        """
        Генерация персонализированного сопроводительного письма для конкретной вакансии
        """
        # Подготовка промпта для генерации сопроводительного письма
        prompt = f"""
Создай профессиональное сопроводительное письмо для кандидата, который хочет подать заявку на следующую вакансию:

ВАКАНСИЯ:
- Название: {vacancy_info.get('title', 'Не указано')}
- Компания: {vacancy_info.get('company', 'Не указано')}
- Город: {vacancy_info.get('city', 'Не указано')}
- Описание: {vacancy_info.get('description', 'Не указано')[:300]}

ИНФОРМАЦИЯ О КАНДИДАТЕ:
- Имя: {user_info.get('fio', 'Не указано')}
- Навыки: {user_info.get('skills', 'Не указаны')}
- Базовое резюме: {user_info.get('base_resume', 'Отсутствует')}

Требования к сопроводительному письму:
1. Письмо должно быть персонализировано и обращено к конкретной компании и вакансии
2. Упомянуть, почему кандидат интересуется этой позицией
3. Кратко описать соответствующий опыт и навыки кандидата
4. Объяснить, чем кандидат может быть полезен компании
5. Использовать профессиональный и вежливый тон
6. Длина письма - 150-250 слов

Сопроводительное письмо:
"""

        # Отправляем запрос к LLM
        response = await self._send_to_llm(prompt, llm_settings)
        return response

    async def _send_to_llm(self, prompt: str, llm_settings: Dict) -> str:
        """
        Отправка запроса к LLM API
        """
        # Получаем настройки LLM из переданных параметров или из конфига
        base_url = llm_settings.get('llm_base_url') or settings.llm_base_url
        api_key = llm_settings.get('llm_api_key') or settings.llm_api_key
        model = llm_settings.get('llm_model') or settings.llm_model

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }

        data = {
            "model": model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 1000
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{base_url}/chat/completions",
                                      json=data, headers=headers) as response:
                    if response.status == 200:
                        result = await response.json()
                        return result['choices'][0]['message']['content'].strip()
                    else:
                        print(f"Ошибка при обращении к LLM API: {response.status}")
                        return "Не удалось сгенерировать текст. Пожалуйста, попробуйте позже."
        except Exception as e:
            print(f"Ошибка при обращении к LLM API: {e}")
            return "Не удалось сгенерировать текст. Пожалуйста, попробуйте позже."