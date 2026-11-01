# Investing Demo

Учебный каталог акций на Django 5.2 LTS: HTML-интерфейс, REST API, регистрация,
администрирование, импорт инструментов, обновление цен через Celery и графики Plotly.
Python 3.12–3.14; проверка выполнена на Python 3.14.6.

## Быстрый локальный запуск

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Откройте <http://127.0.0.1:8000/>. По умолчанию используется SQLite, поэтому для
каталога, регистрации и CRUD не нужны Docker, PostgreSQL или Redis. Первоначально
каталог пуст. Пользователь регистрируется через `/user/registration/`.
Для Django Admin создайте администратора: `python manage.py createsuperuser`.

В Windows активируйте окружение командой `.venv\Scripts\activate`.

## Конфигурация

Скопируйте `.env.example` в `.env` и задайте необходимые значения. Переменные
окружения имеют приоритет над `.env`; настоящий токен и ключи не коммитятся.
После изменения `.env` перезапустите веб-сервер, Worker и Beat.

- `DJANGO_DEBUG`: по умолчанию `true` для локальной разработки.
- `DJANGO_SECRET_KEY`: постоянный случайный ключ. Без него в DEBUG создаётся
  временный ключ процесса; сессии не сохраняются после перезапуска. При
  `DJANGO_DEBUG=false` ключ обязателен. Генерация:
  `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`.
- `DJANGO_ALLOWED_HOSTS`: разрешённые хосты через запятую.
- `DJANGO_DB_ENGINE`: `sqlite` или `postgresql`; `SQLITE_PATH` меняет путь SQLite.
- `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`,
  `POSTGRES_PORT`: подключение PostgreSQL.
- `TINKOFF_TOKEN`: токен Т‑Инвестиций; достаточно доступа только для чтения.
- `TINKOFF_API_URL`: официальный REST gateway, по умолчанию
  `https://invest-public-api.tbank.ru/rest`.
- `TINKOFF_TIMEOUT`: сетевой тайм-аут в секундах, по умолчанию 10.
- `TINKOFF_CA_BUNDLE`: необязательный путь к доверенному CA bundle, если сертификат
  API требует отдельной настройки. Проверка TLS не отключается. См.
  [сетевые настройки Т‑Инвестиций](https://developer.tbank.ru/invest/intro/developer/network).
- `CELERY_BROKER_URL`: Redis, по умолчанию `redis://127.0.0.1:6379/0`.
- `MARKET_UPDATE_INTERVAL`: интервал постановки задачи обновления цен в секундах,
  по умолчанию 10. Не является гарантией времени завершения всего обновления.

Без токена веб-приложение запускается: карточка показывает сохранённые данные и
сообщение о недоступности графика; фоновое обновление пропускается. Для получения
реальных котировок и загрузки каталога необходим действующий токен.

## PostgreSQL, Redis и рыночные данные

```sh
docker compose up -d --wait
```

Установите `DJANGO_DB_ENGINE=postgresql` в `.env`, проверьте параметры PostgreSQL,
затем выполните в активированном окружении:

```sh
python manage.py migrate
python manage.py add_shares
```

Импорт повторяемый: инструмент ищется по FIGI, его реквизиты обновляются, цена
сохраняется. В разных терминалах с тем же `.env` запустите:

```sh
celery -A config worker -l info --pool=solo
celery -A config beat -l info
```

`--pool=solo` подходит и для локального запуска в Windows. Обновление получает
котировки пакетами по 100 инструментов; дробная часть сохраняется с точностью до
9 знаков. PostgreSQL использует именованный том; `docker compose down` сохраняет
данные. Образы ограничены версиями PostgreSQL 17.11 и Redis 7.4.12.

## Интерфейс и API

- `/` — публичный каталог, сортировка по названию, по 100 акций на странице.
- `/<id>` — карточка и дневной график за 180 дней.
- `/create`, `/update/<id>`, `/delete/<id>` — управление общим каталогом после входа.
- `/user/login/`, `/user/registration/`, `/user/logout/` — учётная запись;
  прежние `/userlogin/`, `/userregistration/`, `/userlogout/` сохранены как алиасы.
- Выход выполняется POST с CSRF-токеном; GET показывает подтверждение.
- `/api/v1/shares/` и `/api/v1/shares/<id>/` — GET, POST, PUT, PATCH, DELETE.
  Чтение публичное, запись требует аутентификации. Сессионные запросы изменения
  требуют CSRF; также доступна стандартная Basic Authentication DRF.
- Создание через API требует `uid`; при обновлении его можно опустить.
  `id` и `updated_at` доступны только для чтения. Цена в JSON остаётся числом;
  в БД используется DecimalField.
- Пример фильтра: `/api/v1/shares/?ticker=SBER&ordering=name&limit=20&offset=0`.
  Параметр `search` сохраняет исходный поиск регулярным выражением по названию;
  некорректное выражение возвращает 400.

## Личный кабинет и новые функции

После входа откройте `/workspace/`:

- создайте списки наблюдения и уровни «не ниже»/«не выше»; уведомления появятся
  внутри приложения, по одному на настроенное условие;
- создайте виртуальный портфель, покупайте и продавайте акции, просматривайте
  среднюю цену, стоимость, прибыль/убытки и журнал;
- настройте стратегию с нижним уровнем покупки и верхним продажи; Worker
  выполнит виртуальный цикл и сохранит успешные операции и отказы;
- откройте «Накопленную историю цен» из карточки акции, выберите даты и изучите
  сохранённые наблюдения, изменение цены и график без обращения к внешнему API.

Персональные данные видит только владелец. Валюта портфеля фиксируется при создании;
конвертация, кредит и реальные биржевые поручения не моделируются. Начальный
баланс и журнал сделок защищены от произвольного изменения.

После обновления кода примените `python manage.py migrate` и перезапустите
веб-сервер, Worker и Beat. История начнёт накапливаться с новых котировок;
без токена доступны личный кабинет и ручные сделки по заданной цене.
Требования, архитектура, расчёты и новые API описаны в [FEATURES.md](FEATURES.md).

## Проверка и разработка

```sh
python -m pip install -r requirements-dev.txt
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
black --check config dashboard investing user scripts manage.py
isort --check-only config dashboard investing user scripts manage.py
pip-audit --no-deps --disable-pip -r requirements.txt
python scripts/verify_runtime.py --features
```

`verify_runtime.py` поднимает настоящий HTTP-сервер и изолированную временную SQLite
БД, проверяет регистрацию, сессии, CSRF, CRUD, импорт, обновление цены и график.
С флагом `--features` дополнительно проверяются уведомления, конкурентный повтор
сделки, портфель, полный цикл стратегии, история и изоляция двух пользователей.
Рыночный сервис в этой проверке **синтетический**, настоящий токен не используется.
Временные процессы и БД удаляются по завершении.

Для проверки также реальных Worker, Beat и Redis:

```sh
python scripts/verify_runtime.py --features --broker redis://127.0.0.1:6379/0
```

Ключ `--postgres` использует `POSTGRES_*` из окружения и создаёт/удаляет отдельную
временную БД; пользователь PostgreSQL должен иметь право `CREATEDB`.

Прямые зависимости перечислены в `requirements.in`, dev-инструменты — в
`requirements-dev.in`; `.txt` фиксируют и транзитивные версии. Обновление lock-файлов:

```sh
uv pip compile --upgrade --universal --python-version 3.12 requirements.in -o requirements.txt
uv pip compile --upgrade --universal --python-version 3.12 requirements-dev.in -o requirements-dev.txt
```

Итоги модернизации и проверок: [AUDIT.md](AUDIT.md). Описание исходной версии:
[ANALYSIS.md](ANALYSIS.md), [REQUIREMENTS.md](REQUIREMENTS.md).

Задание №5: [сравнение трёх реализаций](COMPARISON.md),
[отчёт о работе с агентами](REPORT.md), [первичные результаты](audit/comparison.json).
Повторить проверку изолированных Git-снимков можно командой
`python scripts/compare_branches.py`; нужен доступ к PyPI и коммиты сравниваемых веток.
