"""
Файл с тестовыми данными для бота, чтобы он работал без HH API
"""

TEST_VACANCIES = [
    {
        "id": "1",
        "name": "Python разработчик",
        "employer": {"name": "IT Company"},
        "area": {"name": "Москва"},
        "salary": {"from": 150000, "to": 250000, "currency": "RUR"},
        "alternate_url": "https://example.com/vacancy/1",
        "snippet": {"requirement": "Опыт работы с Python от 2 лет, знание Django, Flask"},
        "created_at": "2025-11-20T10:00:00+03:00"
    },
    {
        "id": "2",
        "name": "Frontend разработчик",
        "employer": {"name": "Web Solutions"},
        "area": {"name": "Санкт-Петербург"},
        "salary": {"from": 120000, "to": 200000, "currency": "RUR"},
        "alternate_url": "https://example.com/vacancy/2",
        "snippet": {"requirement": "Знание JavaScript, React, HTML, CSS"},
        "created_at": "2025-11-21T09:30:00+03:00"
    },
    {
        "id": "3",
        "name": "Data Scientist",
        "employer": {"name": "Analytics Pro"},
        "area": {"name": "Новосибирск"},
        "salary": {"from": 180000, "to": 300000, "currency": "RUR"},
        "alternate_url": "https://example.com/vacancy/3",
        "snippet": {"requirement": "Опыт работы с Python, Pandas, Scikit-learn, знание статистики"},
        "created_at": "2025-11-22T14:15:00+03:00"
    },
    {
        "id": "4",
        "name": "QA инженер",
        "employer": {"name": "Test Masters"},
        "area": {"name": "Екатеринбург"},
        "salary": {"from": 80000, "to": 120000, "currency": "RUR"},
        "alternate_url": "https://example.com/vacancy/4",
        "snippet": {"requirement": "Опыт тестирования, знание тестовой документации, автоматизация"},
        "created_at": "2025-11-23T11:45:00+03:00"
    },
    {
        "id": "5",
        "name": "DevOps инженер",
        "employer": {"name": "Cloud Systems"},
        "area": {"name": "Казань"},
        "salary": {"from": 160000, "to": 220000, "currency": "RUR"},
        "alternate_url": "https://example.com/vacancy/5",
        "snippet": {"requirement": "Знание Docker, Kubernetes, CI/CD, Linux"},
        "created_at": "2025-11-23T16:20:00+03:00"
    },
    {
        "id": "6",
        "name": "Fullstack разработчик",
        "employer": {"name": "Digital Agency"},
        "area": {"name": "Москва"},
        "salary": {"from": 200000, "to": 300000, "currency": "RUR"},
        "alternate_url": "https://example.com/vacancy/6",
        "snippet": {"requirement": "Опыт работы с React и Node.js, понимание архитектуры приложений"},
        "created_at": "2025-11-24T08:10:00+03:00"
    },
    {
        "id": "7",
        "name": "iOS разработчик",
        "employer": {"name": "Mobile Experts"},
        "area": {"name": "Санкт-Петербург"},
        "salary": {"from": 170000, "to": 250000, "currency": "RUR"},
        "alternate_url": "https://example.com/vacancy/7",
        "snippet": {"requirement": "Знание Swift, опыт работы с iOS SDK"},
        "created_at": "2025-11-24T09:00:00+03:00"
    },
    {
        "id": "8",
        "name": "Android разработчик",
        "employer": {"name": "Mobile Experts"},
        "area": {"name": "Москва"},
        "salary": {"from": 170000, "to": 250000, "currency": "RUR"},
        "alternate_url": "https://example.com/vacancy/8",
        "snippet": {"requirement": "Знание Kotlin или Java, опыт работы с Android SDK"},
        "created_at": "2025-11-24T09:15:00+03:00"
    }
]

def filter_vacancies(keyword=None, city=None, min_salary=None, period=3):
    """
    Фильтрует тестовые вакансии по заданным параметрам
    """
    from datetime import datetime, timedelta
    import pytz

    # Преобразуем строку даты в объект datetime
    filtered_vacancies = []
    
    for vacancy in TEST_VACANCIES:
        # Фильтр по ключевому слову
        if keyword and keyword.lower() not in vacancy['name'].lower():
            continue
            
        # Фильтр по городу
        if city and city.lower() not in vacancy['area']['name'].lower():
            continue
            
        # Фильтр по минимальной зарплате
        if min_salary:
            salary_from = vacancy.get('salary', {}).get('from')
            if salary_from is not None and salary_from < min_salary:
                continue
                
        # Фильтр по дате (вакансии за последние period дней)
        created_at_str = vacancy.get('created_at')
        if created_at_str:
            # Убираем таймзону из строки, если есть
            if '+' in created_at_str:
                date_str = created_at_str.split('+')[0]
            elif 'Z' in created_at_str:
                date_str = created_at_str.replace('Z', '')
            else:
                date_str = created_at_str
                
            try:
                created_at = datetime.fromisoformat(date_str)
                # Используем московскую таймзону
                tz = pytz.timezone('Europe/Moscow')
                if created_at.tzinfo is None:
                    created_at = tz.localize(created_at)
                else:
                    created_at = created_at.astimezone(tz)
                    
                if created_at < datetime.now(tz) - timedelta(days=period):
                    continue
            except ValueError:
                # Если формат даты некорректен, пропускаем вакансию
                continue
        
        filtered_vacancies.append(vacancy)
        
    return {
        "items": filtered_vacancies,
        "found": len(filtered_vacancies)
    }