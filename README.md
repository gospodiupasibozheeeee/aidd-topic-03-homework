# Investing Demo (Модернизированная версия — Агент Antigravity)

Веб-приложение для мониторинга котировок акций, аналитики, управления инвестиционным портфелем и фонового сбора рыночных данных.

---

## 1. Быстрый старт (Локальная разработка)

### 1.1. Настройка окружения
1. Создайте файл `.env` на основе примера:
   ```bash
   cp .env.example .env
   ```
2. По умолчанию настроена база данных **SQLite** (`DJANGO_DB_ENGINE=sqlite`), что позволяет запускать приложение локально без Docker.
3. При необходимости укажите `TINKOFF_TOKEN` для загрузки котировок из Т-Банк Инвестиций.

### 1.2. Установка зависимостей и миграции
```bash
pip install -r requirements.txt
python manage.py migrate
```

### 1.3. Запуск тестов
```bash
python manage.py test
```

### 1.4. Запуск сервера разработки
```bash
python manage.py runserver
```
Приложение доступно по адресу: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)

---

## 2. Запуск с PostgreSQL и Redis (Docker)

Если установлен Docker, сервисы СУБД и брокера сообщений запускаются командой:
```bash
docker-compose up -d
```
В файле `.env` установите:
```ini
DJANGO_DB_ENGINE=postgresql
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
CELERY_BROKER_URL=redis://127.0.0.1:6379/0
```

---

## 3. Фоновые процессы (Celery)

### Celery Beat (планировщик)
```bash
celery -A config beat -l info
```

### Celery Worker (обработчик задач)
```bash
celery -A config worker -l info
```

Для Windows:
```bash
celery -A config worker -l info -P eventlet
```

---

## 4. Загрузка справочника акций
```bash
python manage.py add_shares
```

---

## 5. Основные эндпоинты

- `/` — Главная страница (каталог акций с пагинацией)
- `/<pk>` — Карточка акции с историческим графиком за 180 дней
- `/create` — Форма добавления акции (требуется вход)
- `/user/login/` (а также `/userlogin/`) — Авторизация
- `/user/registration/` (а также `/userregistration/`) — Регистрация
- `/api/v1/shares/` — REST API для работы с акциями
- `/admin/` — Панель администрирования Django
