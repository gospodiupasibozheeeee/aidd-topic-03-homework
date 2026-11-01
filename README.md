# Investing Demo

Учебный сервис мониторинга акций: каталог, карточка с графиком за 180 дней,
управление каталогом, REST API, регистрация/вход, импорт справочника и фоновое
обновление цен из Tinkoff Invest API.

## Быстрый старт

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# отредактируйте .env: задайте DJANGO_SECRET_KEY и, при необходимости, TINKOFF_TOKEN

python manage.py migrate
python manage.py runserver
```

Откройте <http://127.0.0.1:8000/>.

По умолчанию используется SQLite — внешние сервисы для запуска не нужны. Для
PostgreSQL установите в `.env` `DJANGO_DB_ENGINE=postgresql` и запустите
инфраструктуру:

```bash
docker compose up -d
```

## Tinkoff Invest API

Укажите `TINKOFF_TOKEN` в `.env`. SDK `tinkoff-investments` импортируется лениво:
если пакет недоступен или токен не задан, каталог продолжает работать, а вместо
графика выводится сообщение о недоступности рыночных данных.

```bash
# Первоначальная загрузка справочника акций
python manage.py add_shares
```

## Фоновое обновление цен

```bash
# Без Redis для локальной проверки:
# CELERY_ALWAYS_EAGER=True в .env

celery -A config beat
celery -A config worker -l info
```

На Windows для worker может потребоваться eventlet:

```bash
pip install eventlet
celery -A config worker -l info -P eventlet
```

## REST API

- `GET /api/v1/` — корень API;
- `GET /api/v1/shares/` — список (пагинация, фильтры, поиск, сортировка);
- `POST /api/v1/shares/` — создание (требуется аутентификация);
- `GET|PUT|PATCH|DELETE /api/v1/shares/<id>/` — операции с записью.

Чтение публично; изменение и удаление требуют аутентификации
(`IsAuthenticatedOrReadOnly`).

Примеры:

```bash
curl 'http://127.0.0.1:8000/api/v1/shares/?limit=10&ordering=name&search=App'
```

## Тесты и проверки

```bash
python manage.py test
python manage.py check
```

## Структура

- `config/` — настройки, URLconf, Celery, WSGI/ASGI;
- `dashboard/` — модель `Share`, HTML-представления, REST API, сервисы Tinkoff,
  задача Celery, импорт и admin;
- `user/` — регистрация, вход и выход на стандартной `auth.User`.

Документы анализа и требований: [ANALYSIS.md](ANALYSIS.md),
[REQUIREMENTS.md](REQUIREMENTS.md), [MODERNIZATION.md](MODERNIZATION.md).
