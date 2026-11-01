# Модернизация, устранение дефектов и рефакторинг (Task 3)

**Проект:** Investing Demo  
**Ветка:** `deepseek`  
**Базовая версия:** `362510b`  
**Результат:** работоспособное приложение на Django 5.2, SQLite/PostgreSQL,
Celery 5.6, Plotly 6.9; тесты — 36, все проходят.

---

## 1. Аудит зависимостей

| Компонент | Было | Стало | Причина |
|---|---|---|---|
| Python | не зафиксирован; стек 2023 г. | 3.10+ (проверено на 3.14) | Django 5.2 требует современный Python |
| Django | 4.1.7 | 5.2.18 | ветка 4.1 не поддерживается; несовместима с Python 3.12+ |
| DRF | 3.14.0 | 3.18.3 | совместимость с Django 5.2 |
| django-filter | 22.1 | 26.2 | совместимость |
| django-crispy-forms | 2.0 | 2.7 | совместимость |
| crispy-bootstrap3 | 2022.1 | crispy-bootstrap5 2026.9 | Bootstrap 5 в шаблонах |
| Celery | 5.2.7 | 5.6.3 | поддержка Python 3.14 |
| redis | 4.5.1 | 6.4.0 | совместимость с Celery 5.6 |
| psycopg2-binary | 2.9.5 | psycopg[binary] 3.3.6 | современный драйвер PostgreSQL |
| Plotly | 5.13.1 | 6.9.0 | актуальная версия; Plotly.js 3.7.0 |
| python-dotenv | отсутствовал | 1.2.4 | загрузка `.env` |
| Tinkoff SDK | `tinkoff==0.1.1`, `tinkoff-investments==0.2.0b50` | только `tinkoff-investments` (маркер Python < 3.12) | убран конфликтующий пакет; SDK стал опциональным |
| Black/isort | в runtime | `requirements-dev.txt` | dev-инструменты не нужны в production |

Транзитивные зависимости (kombu, billiard, grpcio, protobuf, pydantic и др.) больше
не фиксируются вручную: они разрешаются через верхнеуровневые пакеты. Это уменьшило
`requirements.txt` с 40 строк до 11 прямых зависимостей и устранило конфликт
`tinkoff`/`tinkoff-investments`.

**Ограничение:** upstream-пакет `tinkoff-investments==0.2.0b50` не имеет wheel для
Python 3.12+; на Python 3.14 он не устанавливается. Приложение импортирует SDK лениво,
поэтому каталог и веб-интерфейс работают без него, а график показывает понятное
сообщение. Для реальных рыночных данных нужен Python 3.10/3.11 с установленным SDK и
`TINKOFF_TOKEN`.

---

## 2. Конфигурация и совместимость

- Настройки переведены на переменные окружения (`python-dotenv`), добавлен
  `.env.example`; секреты больше не хранятся в `settings.py`.
- `SECRET_KEY` обязателен при `DJANGO_DEBUG=False`; для локальной разработки
  предусмотрен явно небезопасный fallback.
- `ALLOWED_HOSTS`, `DEBUG`, `TIME_ZONE`, `CSRF_TRUSTED_ORIGINS`, secure-cookie
  флаги задаются через env.
- База данных выбирается через `DJANGO_DB_ENGINE`: SQLite по умолчанию (запуск без
  Docker), PostgreSQL — при `postgresql`.
- PostgreSQL-драйвер заменён на `psycopg` 3.x; настроен `CONN_MAX_AGE`.
- `STATIC_ROOT` добавлен; `collectstatic` проверен (158 файлов).
- Логирование: `RotatingFileHandler` в `BASE_DIR/app.logs`, отдельные логгеры
  `main`, `dashboard`, `django.request`.
- Устранён рассинхрон `TIME_ZONE=UTC` / `CELERY_TIMEZONE=Europe/Moscow`:
  используется единая таймзона из env (`Europe/Moscow` по умолчанию).
- `CELERY_BEAT_SCHEDULE` перенесён в настройки; интервал задаётся
  `MARKET_UPDATE_INTERVAL`; исправлено вводящее в заблуждение имя
  `add-every-5-min`.
- `docker-compose.yml`: версии образов (`postgres:16-alpine`, `redis:7-alpine`),
  named volumes, healthchecks, переменные окружения; убран ошибочный volume
  `./:/app` у PostgreSQL.
- `manage.py` больше не содержит название `DjangoOld`.

---

## 3. Исправленные дефекты

| ID | Дефект | Что сделано | Проверка |
|---|---|---|---|
| Д-01 | API открыт анонимно | `IsAuthenticatedOrReadOnly`: чтение публично, запись — после входа | `ShareAPITests` (403/201) |
| Д-02 | `uid` вне сериализатора, второй POST → 500 | `uid` генерируется моделью, поле `read_only` в API | тест второго POST |
| Д-03 | 500 на отсутствующей карточке | `ShareDetailView` переведён на `DetailView` (404) | `test_missing_detail_returns_404` |
| Д-04 | `KeyError` в регистрации | `cleaned_data.get`, `add_error`; шаблон выводит ошибки формы | тесты mismatched/duplicate/weak |
| Д-05 | `AuthView` без `is_valid` | форма валидируется, `AuthForm.clean` аутентифицирует | тесты входа |
| Д-06 | Парольные валидаторы не применялись | `validate_password` в `clean_password1` | `test_registration_rejects_weak_password` |
| Д-07 | `updated_at` не обновлялся задачей | `update(..., updated_at=...)` | `UpdateLastPriceTaskTests` |
| Д-08 | `FloatField` и потеря `nano` | `DecimalField(20,9)`, `quotation_to_decimal` | `test_quotation_conversion_uses_nano` |
| Д-09 | N+1 gRPC-запросов | один `get_last_prices(figi=[...])` на все акции | `test_updates_price...` с mock |
| Д-10 | `get_or_create` по всем полям | `update_or_create(figi=..., defaults=...)` | `AddSharesCommandTests` |
| Д-11 | Выход через GET | logout только POST, ссылка заменена формой с CSRF | `test_logout_requires_post` |
| Д-12 | `/userlogin/`, `/create/` | канонические `/user/login/`; редиректы со старых URL | `test_legacy_auth_url_redirects` |
| Д-13 | Нет транзакций/гонки | `update_or_create`, обработка `IntegrityError` при регистрации | тесты регистрации |
| Д-14 | Нестабильная пагинация API | `ordering = ("name",)` | тест ordering |
| Д-15 | `$name` — regex, а не обычный поиск | заменено на `search_fields = ("name",)` — `icontains` | тест `search=app` |
| Д-16 | Неоднозначный тренд | `is_trend_high` non-null, default `False`; логика сохранена | тесты task |
| Д-17 | Синхронный Tinkoff без обработки ошибок | `MarketDataError`, `try/except` в карточке, пустой график | `test_chart_error_is_graceful` |
| Д-18 | Пустые секреты/DEBUG | env-конфигурация, обязательный `SECRET_KEY` в production | `check`, `.env.example` |
| Д-19 | Compose без версий/персистентности | версии, volumes, healthchecks | статическая проверка |
| Д-20 | Мало тестов | 36 тестов: модель, формы, HTML, auth, API, task, command, graph | `manage.py test` |
| Д-21 | Bootstrap 3 + Bootstrap 5 | crispy-bootstrap5, исправлены `col3`, удалены мёртвые CDN | визуальная проверка |
| Д-22 | `AuthForm` класс вместо экземпляра | передаётся экземпляр формы | тесты auth |
| Д-23 | E-mail > 150 символов | `max_length=150` в формах | форма |
| Д-24 | Имя Beat-задачи | `update-last-price`, интервал из настроек | `celery.py` |
| Д-25 | Нет портфелей/истории | не входит в Task 3; задел для Task 4 | — |

---

## 4. Рефакторинг

- Выделен `dashboard/services/tinkoff.py`:
  - ленивый импорт SDK;
  - единая точка `MarketDataError`;
  - преобразование `Quotation`/`MoneyValue` (`units` + `nano`) в `Decimal`;
  - пакетный `get_last_prices`;
  - `get_candles`.
- `market_data.py` оставлен совместимым фасадом (`get_last_data`, re-export).
- `graph.py` использует `go.Figure`, `include_plotlyjs=False` (Plotly.js подключается
  один раз в шаблоне), подписывает график тикером.
- `ShareDetailView` переведён с `View` на `DetailView`; ошибки Tinkoff не роняют
  страницу.
- `ShareCreateView`/`UpdateView`/`DeleteView` используют `LoginRequiredMixin`
  и `messages`.
- `ShareModelForm` получил явный список полей, виджеты, нормализацию тикера и
  проверку неотрицательной цены.
- `add_shares` обновляет существующие записи по `figi`, а не создаёт дубликаты;
  сообщает статистику.
- Celery-задача переведена на пакетный запрос и `update()` с явным `updated_at`.
- API: `IsAuthenticatedOrReadOnly`, явный `ordering`, `uid` read-only, `last_price`
  как Decimal, поиск через `icontains`.
- URL: канонические `/user/...`; редиректы со старых адресов; trailing-slash
  редиректы для create/update/delete.
- Шаблоны переведены на Bootstrap 5, убраны неиспользуемые jQuery/Popper/Moment/
  Tempus Dominus/Font Awesome; сообщения и ошибки форм отображаются.
- `admin` получил `last_price`, `is_trend_high`, `updated_at`, фильтры и
  `readonly_fields`.
- Добавлены `requirements-dev.txt`, `.env.example`, обновлены README и `.gitignore`.

---

## 5. Модель данных и миграция

- `last_price`: `FloatField` → `DecimalField(max_digits=20, decimal_places=9)`.
- `uid`: `blank=True`, `default=generate_uid`; ручное создание и API больше не
  требуют UID.
- `is_trend_high`: `null=False`, `default=False`.
- `name`: индекс для сортировки/поиска.
- `Meta.ordering = ["name"]`, `__str__`.
- Миграция `0008_alter_share_options_alter_share_figi_and_more`:
  - data-migration заполняет пустые `uid` и `NULL`-тренды;
  - затем AlterField для Decimal, default UID, Boolean, индекса и options.
- Проверено: `makemigrations --check` — «No changes detected»; `migrate` — OK.

---

## 6. Изменения поведения

| Область | Было | Стало |
|---|---|---|
| API-запись | анонимно | только аутентифицированные |
| API `uid` | отсутствовал | read-only в ответе, генерируется |
| API поиск | regex `$name` | `icontains` по `name` |
| API сортировка | без default | `name` по умолчанию |
| Выход | GET | POST + CSRF; GET — безопасный редирект |
| Пользовательские URL | `/userlogin/` и т.п. | `/user/login/`, `/user/registration/`, `/user/logout/` + редиректы |
| Форма акции | все поля, включая `uid` | `uid` генерируется; поля явные |
| Last price | float | Decimal |
| Ошибка Tinkoff | 500 | сообщение в карточке, каталог работает |
| Celery | N запросов/10 с | один пакетный запрос, интервал из env |

---

## 7. Проверка работоспособности

Выполнено в локальном окружении (Python 3.14, SQLite, `.env` с `CELERY_ALWAYS_EAGER=True`):

```text
python manage.py check
System check identified no issues (0 silenced).

python manage.py makemigrations --check --dry-run
No changes detected

python manage.py migrate
Applying dashboard.0008... OK

python manage.py test
Ran 36 tests ... OK

python manage.py collectstatic --noinput
158 static files copied

pip install --dry-run -r requirements.txt
(разрешение зависимостей успешно; Tinkoff SDK пропущен по маркеру Python < 3.12)
```

Smoke-тест `runserver`:

| URL | Код | Примечание |
|---|---|---|
| `/` | 200 | каталог, тестовая акция отображается |
| `/1` | 200 | карточка; вместо графика — сообщение об отсутствии Tinkoff SDK |
| `/create` | 302 | анонимный пользователь → каталог |
| `/create/` | 302 | редирект на `/create` |
| `/user/login/` | 200 | форма входа |
| `/user/registration/` | 200 | форма регистрации |
| `/api/v1/shares/` | 200 | JSON, `uid`, Decimal-цена |
| `/admin/` | 302 | редирект на admin login |

`manage.py check --deploy` в локальном режиме выдаёт ожидаемые предупреждения
(`DEBUG=True`, dev-secret, secure cookies/SSL). Для production задайте
`DJANGO_DEBUG=False`, длинный `DJANGO_SECRET_KEY`, `DJANGO_SECURE_COOKIES=True` и
настройте HTTPS/HSTS на reverse proxy.

---

## 8. Ограничения проверки

- **Tinkoff SDK** не установлен на Python 3.14 (нет wheel); реальные запросы к
  Tinkoff API не выполнялись. Сервисный слой, преобразование цен, обработка ошибок и
  задача проверены с mock-объектами.
- **PostgreSQL** не запускался: Docker в окружении отсутствует; конфигурация
  PostgreSQL проверена статически, миграции — на SQLite.
- **Redis/Celery worker** не запускались: локально `CELERY_ALWAYS_EAGER=True`;
  задача вызвана напрямую в тестах.
- **Браузерная визуальная проверка** ограничена HTML-ответами и шаблонными тестами;
  Plotly-график без CDN/токена не отрисовывается, но страница не падает.

---

## 9. Что дальше (Task 4)

Добавление портфелей, watchlist, истории цен и стратегий потребует:

- новых моделей и внешних ключей на `auth_user`/`Share`;
- `DecimalField` для всех денежных значений;
- фонового накопления `PriceHistory` и исключения дублей уведомлений;
- API-прав на владельца объектов;
- тестов на новые сценарии и миграции данных.
