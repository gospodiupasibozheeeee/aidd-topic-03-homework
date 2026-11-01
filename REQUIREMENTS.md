# Восстановленные функциональные требования к приложению Investing Demo (Агент Antigravity)

## 1. Введение и область применения

Настоящий документ содержит спецификацию функциональных требований, восстановленных на основе анализа исходного кода приложения **Investing Demo** (базовый коммит `362510b`).

Требования описывают **фактически реализованное поведение системы**, зафиксированное в кодовой базе (модели, формы, представления, сериализаторы, шаблоны, задачи Celery и тесты). Дефекты, архитектурные несоответствия и ошибки реализации отделены от требований и вынесены в раздел [6. Выявленные неоднозначности, противоречия и дефекты реализации](#6-выявленные-неоднозначности-противоречия-и-дефекты-реализации).

---

## 2. Основные функциональные возможности

Приложение предоставляет следующие ключевые функциональные возможности:
1. **Просмотр публичного каталога акций**: табличное представление ценных бумаг с пагинацией и цветовой подсветкой динамики цен.
2. **Просмотр детальной карточки акции**: отображение реквизитов инструмента, последней зафиксированной цены, времени обновления и интерактивного графика котировок за последние 180 дней.
3. **Управление каталогом через веб-интерфейс**: создание, редактирование и удаление акций авторизованными пользователями через HTML-формы.
4. **Управление каталогом через REST API**: программный доступ к операциям CRUD, фильтрации по тикеру/названию, сортировке, пагинации и регулярному поиску.
5. **Управление учетной записью и сессиями**: регистрация пользователей по email и паролю, аутентификация (вход в систему) и завершение сеанса (выход).
6. **Пакетная консольная загрузка каталога**: команда CLI Django для синхронизации справочника доступных акций из Tinkoff Invest API.
7. **Фоновое периодическое обновление котировок**: автоматический опрос рыночных цен через Celery и фиксация изменений тренда в БД.
8. **Панель администрирования**: управление каталогом акций через встроенную админку Django (`/admin/`).

---

## 3. Основные сценарии взаимодействия (Use Cases)

| Сценарий | Участник | Последовательность действий | Ожидаемый результат | Связанные ФТ |
|---|---|---|---|---|
| **UC-1. Просмотр каталога акций** | Любой посетитель (анонимный / авторизованный) | Переходит по адресу `/` (главная страница), просматривает таблицу, при необходимости переключает страницы пагинации. | Отображается таблица акций с полями: тикер, наименование, ISIN, цена, валюта и подсветка тренда. | ФТ-01, ФТ-02, ФТ-03, ФТ-06 |
| **UC-2. Просмотр карточки акции и графика** | Любой посетитель | Кликает по тикеру акции в таблице или переходит по URL `/<pk>`. | Открывается страница с реквизитами акции, текущей ценой, датой обновления и графиком Plotly за 180 дней. | ФТ-04, ФТ-05 |
| **UC-3. Регистрация нового пользователя** | Анонимный посетитель | Переходит на `/userregistration/`, вводит email, пароль и подтверждение пароля, нажимает «Зарегистрироваться». | Создается аккаунт в Django Auth, пользователь автоматически авторизуется и перенаправляется на главную страницу. | ФТ-08, ФТ-09, ФТ-10, ФТ-11 |
| **UC-4. Аутентификация (вход)** | Анонимный посетитель | Переходит на `/userlogin/`, вводит зарегистрированный email и пароль, нажимает «Войти». | Создается сессия Django, открывается главная страница; в шапке отображается «Привет, {email}» и кнопка «Выход». | ФТ-07, ФТ-12, ФТ-13 |
| **UC-5. Завершение сеанса (выход)** | Авторизованный пользователь | Нажимает кнопку «Выход» в шапке (GET-запрос на `/userlogout/`). | Сессия завершается, пользователь перенаправляется на главную страницу как гость. | ФТ-14 |
| **UC-6. Добавление акции через веб-форму** | Авторизованный пользователь | Нажимает кнопку «Добавить» на главной, переходит на `/create`, заполняет поля формы и нажимает «Сохранить». | В БД создается новая запись акции, пользователь перенаправляется на главную страницу с обновленным списком. | ФТ-15, ФТ-16, ФТ-19, ФТ-20 |
| **UC-7. Редактирование акции через веб-форму** | Авторизованный пользователь | Нажимает «Редактировать» в строке акции на главной (`/update/<pk>`), вносит изменения и нажимает «Сохранить». | Изменения сохраняются в БД, пользователь перенаправляется на главную страницу. | ФТ-15, ФТ-17, ФТ-19, ФТ-20 |
| **UC-8. Удаление акции через веб-форму** | Авторизованный пользователь | Нажимает «Удалить» в строке акции (`/delete/<pk>`), видит запрос подтверждения и нажимает кнопку «Удалить». | Запись акции удаляется из БД, пользователь перенаправляется на главную страницу. | ФТ-15, ФТ-18 |
| **UC-9. Программная работа с REST API** | Клиент REST API | Отправляет HTTP-запросы к `/api/v1/shares/` (GET, POST, PUT, PATCH, DELETE). | Получает ответы в формате JSON со статусами 200, 201, 204, 400, 404. | ФТ-21, ФТ-22, ФТ-27, ФТ-28, ФТ-29, ФТ-30 |
| **UC-10. Поиск, фильтрация и пагинация API** | Клиент REST API | Передает query-параметры `limit`, `offset`, `ticker`, `name`, `ordering`, `search`. | Получает отфильтрованный, упорядоченный список акций с пагинационными ссылками (`count`, `next`, `previous`, `results`). | ФТ-23, ФТ-24, ФТ-25, ФТ-26 |
| **UC-11. Первоначальный импорт акций** | Администратор / Оператор | Выполняет команду `python manage.py add_shares` в терминале. | Запрашиваются все акции из Tinkoff API, новые записи сохраняются в БД. | ФТ-31 |
| **UC-12. Автоматическое фоновое обновление котировок** | Фоновый процесс Celery | Celery Beat каждые 10 секунд инициирует задачу `update_last_price`. | Worker получает свежие цены из Tinkoff API и обновляет `last_price` и `is_trend_high` в БД. | ФТ-32 |

---

## 4. Бизнес-правила, проверки и ограничения

- **БП-01 (Идентификация и уникальность инструментов)**: Каждая акция в системе должна обладать уникальными значениями полей `figi`, `ticker` и `uid`. Повторное добавление инструмента с существующим `figi`, `ticker` или `uid` запрещено на уровне схемы БД (`unique=True`).
- **БП-02 (Обязательность реквизитов акции)**: При создании акции обязательны для заполнения: международный идентификатор `figi`, код `isin`, наименование компании `name`, биржевой тикер `ticker`, валюта `currency` и внешний идентификатор `uid`.
- **БП-03 (Публичность каталога)**: Просмотр каталога акций и детальной информации доступен любым пользователям без обязательной аутентификации.
- **БП-04 (Разграничение прав в веб-интерфейсе)**: Действия по созданию (`/create`), редактированию (`/update/<pk>`) и удалению (`/delete/<pk>`) акций в веб-интерфейсе разрешены только аутентифицированным пользователям. При попытке доступа анонимного пользователя происходит автоматическое перенаправление на главную страницу (`dashboard:index`).
- **БП-05 (Общий каталог)**: Каталог акций является глобальным и общесистемным. Акции не привязаны к конкретным пользователям или владельцам; любой аутентифицированный пользователь может редактировать или удалять любые акции.
- **БП-06 (Идентификация пользователя по email)**: Логином пользователя в системе является адрес его электронной почты. При регистрации email одновременно сохраняется в поля `username` и `email` стандартной модели Django User.
- **БП-07 (Правила валидации регистрации)**:
  - Адрес email должен соответствовать формату электронной почты.
  - Введенные пароли `password1` и `password2` должны совпадать.
  - Email должен быть уникальным среди существующих пользователей системы.
- **БП-08 (Индикация ценового тренда)**: Если сохраненное значение `is_trend_high == True`, фон ячейки с ценой в каталоге подсвечивается зеленым цветом (`mediumseagreen`). В противном случае (`False` или `None`) фон подсвечивается розово-красным цветом (`palevioletred`).
- **БП-09 (Логика фиксации ценового тренда)**: При получении новой котировки из внешнего API:
  - Если предыдущая цена strictly больше новой (`share.last_price > last_price`), признак `is_trend_high` принимает значение `False` (падение цены).
  - В остальных случаях (цена выросла, не изменилась или предыдущая цена отсутствовала) `is_trend_high` принимает значение `True`.
- **БП-10 (Параметры исторического графика)**: Исторический график строится по дневным свечам за последние 180 дней от текущего момента времени с интервалом `CandleInterval.CANDLE_INTERVAL_DAY`.
- **БП-11 (Лимиты пагинации)**:
  - Веб-каталог отображает максимум 100 записей на страницу.
  - REST API по умолчанию возвращает порцию из 100 записей (настройка `LimitOffsetPagination` со значением `PAGE_SIZE = 100`).

---

## 5. Нумерованный список функциональных требований

### 5.1. Веб-интерфейс каталога и карточки акции

#### ФТ-01. Публичный просмотр каталога акций
- **Описание**: При отправке HTTP-запроса `GET /` система отображает таблицу акций, отсортированную по наименованию компании в алфавитном порядке (`ordering = ["name"]`). В таблице выводятся колонки: «Тикер», «Название», «ISIN», «Текущая цена». Тикер отображается в виде гиперссылки на детальную карточку.
- **Подтверждение в коде**:
  - `dashboard/views.py`: класс [`ShareListView`](file:///Users/lendwye/documents/antigravity/aidd-topic-03-homework/dashboard/views.py#L20-L27) (`model = Share`, `ordering = ["name"]`, `paginate_by = 100`).
  - `dashboard/templates/dashboard/list.html`: строки 16–58 (табличная разметка `<table>`).
  - `dashboard/urls.py`: строка 14 (`path("", ShareListView.as_view(), name="index")`).

#### ФТ-02. Постраничная навигация (пагинация) в веб-каталоге
- **Описание**: Если общее число акций превышает 100, система разбивает список на страницы по 100 элементов и отображает блок пагинации с номерами страниц и ссылками перехода «вперед/назад» через query-параметр `?page=N`.
- **Подтверждение в коде**:
  - `dashboard/views.py`: [`ShareListView.paginate_by = 100`](file:///Users/lendwye/documents/antigravity/aidd-topic-03-homework/dashboard/views.py#L25).
  - `dashboard/templates/dashboard/list.html`: строки 60–80 (пагинатор `page_obj`).

#### ФТ-03. Отображение пустого состояния каталога
- **Описание**: При отсутствии записей в таблице акций вместо таблицы отображается информационное сообщение «Акций еще нет».
- **Подтверждение в коде**:
  - `dashboard/templates/dashboard/list.html`: строки 15, 83–85 (`{% if share_list %} ... {% else %} <p>Акций еще нет</p> {% endif %}`).

#### ФТ-04. Просмотр детальной карточки акции
- **Описание**: При запросе `GET /<pk>` система находит акцию по первичному ключу и отображает наименование компании, последнюю зафиксированную цену, валюту, дату/время последнего обновления (`updated_at`) и график котировок.
- **Подтверждение в коде**:
  - `dashboard/views.py`: класс [`ShareDetailView`](file:///Users/lendwye/documents/antigravity/aidd-topic-03-homework/dashboard/views.py#L29-L38).
  - `dashboard/templates/dashboard/detail.html`: строки 8–16.
  - `dashboard/urls.py`: строка 15 (`path("<int:pk>", ShareDetailView.as_view(), name="detail")`).

#### ФТ-05. Формирование интерактивного графика котировок
- **Описание**: При формировании карточки акции система запрашивает в Tinkoff API исторические дневные свечи за последние 180 дней по FIGI акции и генерирует линейный график с помощью библиотеки Plotly, встраивая его в HTML-шаблон.
- **Подтверждение в коде**:
  - `dashboard/services/graph.py`: функция [`get_graph`](file:///Users/lendwye/documents/antigravity/aidd-topic-03-homework/dashboard/services/graph.py#L11-L36) (`Client.get_all_candles`, `CandleInterval.CANDLE_INTERVAL_DAY`, `timedelta(days=180)`).
  - `dashboard/templates/dashboard/detail.html`: строки 22–26 (`{% autoescape off %} {{ plot_div }} {% endautoescape %}`).

#### ФТ-06. Цветовая индикация тренда котировки
- **Описание**: В таблице каталога ячейка с текущей ценой окрашивается в зеленый цвет (`style="background-color: mediumseagreen"`), если `is_trend_high` равен `True`, либо в розовый цвет (`style="background-color: palevioletred"`), если `False` или `None`.
- **Подтверждение в коде**:
  - `dashboard/templates/dashboard/list.html`: строки 35–39 (`{% if share.is_trend_high %} ... {% else %} ... {% endif %}`).

---

### 5.2. Управление учетными записями и сессиями

#### ФТ-07. Отображение статуса аутентификации в навигации
- **Описание**: В шапке сайта для неавторизованного пользователя отображается кнопка «Войти». Для авторизованного пользователя выводится приветствие «Привет, {email}» и кнопка «Выход».
- **Подтверждение в коде**:
  - `dashboard/templates/dashboard/base.html`: строки 36–45 (`{% if user.is_authenticated %} ... {% endif %}`).

#### ФТ-08. Отображение формы регистрации
- **Описание**: При запросе `GET /userregistration/` система отображает форму с обязательными полями ввода адреса электронной почты (`email`), пароля (`password1`) и подтверждения пароля (`password2`).
- **Подтверждение в коде**:
  - `user/forms.py`: класс [`RegistrationForm`](file:///Users/lendwye/documents/antigravity/aidd-topic-03-homework/user/forms.py#L8-L28).
  - `user/views.py`: [`RegistrationView.get`](file:///Users/lendwye/documents/antigravity/aidd-topic-03-homework/user/views.py#L40-L42).
  - `user/templates/user/registration.html`: строки 4–24.

#### ФТ-09. Валидация совпадения паролей при регистрации
- **Описание**: Если введенные значения `password1` и `password2` не совпадают, регистрация отклоняется с ошибкой «Введенные пароли не совпадают».
- **Подтверждение в коде**:
  - `user/forms.py`: метод [`RegistrationForm.clean`](file:///Users/lendwye/documents/antigravity/aidd-topic-03-homework/user/forms.py#L30-L37).

#### ФТ-10. Проверка уникальности email при регистрации
- **Описание**: Если пользователь с указанным адресом email уже существует в БД, форма возвращает ошибку «Данный e-mail уже зарегистрирован! Введите другой e-mail или воспользуйтесь формой авторизации.».
- **Подтверждение в коде**:
  - `user/forms.py`: метод [`RegistrationForm.clean`](file:///Users/lendwye/documents/antigravity/aidd-topic-03-homework/user/forms.py#L39-L46).

#### ФТ-11. Успешная регистрация и автоматический вход
- **Описание**: При успешной валидации данных формы регистрации создается пользователь через `User.objects.create_user(email, email, password)`, производится аутентификация, открывается сессия через `login(request, user)` и выполняется перенаправление на главную страницу (`dashboard:index`).
- **Подтверждение в коде**:
  - `user/forms.py`: метод [`RegistrationForm.save`](file:///Users/lendwye/documents/antigravity/aidd-topic-03-homework/user/forms.py#L48-L53).
  - `user/views.py`: метод [`RegistrationView.post`](file:///Users/lendwye/documents/antigravity/aidd-topic-03-homework/user/views.py#L44-L49).

#### ФТ-12. Аутентификация пользователя (вход)
- **Описание**: При отправке `POST /userlogin/` система производит проверку учетных данных вызовом `authenticate(request, username=email.lower(), password=password)`. При успехе открывается пользовательская сессия (`login`) и выполняется редирект на главную страницу.
- **Подтверждение в коде**:
  - `user/views.py`: метод [`AuthView.post`](file:///Users/lendwye/documents/antigravity/aidd-topic-03-homework/user/views.py#L16-L24).
  - `user/templates/user/auth.html`: строки 3–20.

#### ФТ-13. Отказ в аутентификации
- **Описание**: Если учетные данные неверны (`authenticate` вернул `None`), система повторно отображает форму входа с текстом ошибки: «Неверный логин или пароль! Повторите попытку.».
- **Подтверждение в коде**:
  - `user/views.py`: строки 25–33 (`AuthView.post`).
  - `user/templates/user/auth.html`: строки 13–15 (`{{ error }}`).

#### ФТ-14. Завершение сеанса (выход)
- **Описание**: При обращении `GET /userlogout/` система вызывает функцию `logout(request)`, завершает пользовательскую сессию и перенаправляет браузер на главную страницу (`dashboard:index`).
- **Подтверждение в коде**:
  - `user/views.py`: класс [`LogoutView`](file:///Users/lendwye/documents/antigravity/aidd-topic-03-homework/user/views.py#L58-L64).

---

### 5.3. Управление каталогом через веб-интерфейс

#### ФТ-15. Ограничение доступа к модификации каталога через веб-интерфейс
- **Описание**: Доступ к страницам добавления (`/create`), редактирования (`/update/<pk>`) и удаления (`/delete/<pk>`) акций разрешен только авторизованным пользователям через миксин `IsUserAuthenticatedMixin`. При обращении неавторизованного пользователя происходит редирект на главную страницу. Кнопки «Добавить», «Редактировать», «Удалить» в шаблоне отображаются только при `user.is_authenticated`.
- **Подтверждение в коде**:
  - `dashboard/views.py`: класс [`IsUserAuthenticatedMixin`](file:///Users/lendwye/documents/antigravity/aidd-topic-03-homework/dashboard/views.py#L11-L17) (`test_func`, `handle_no_permission`).
  - `dashboard/templates/dashboard/list.html`: строки 9–13, 23–25, 41–50.

#### ФТ-16. Создание акции через веб-форму
- **Описание**: При отправке валидных данных через `POST /create` авторизованным пользователем создается новый объект акции в БД, и пользователь перенаправляется на главную страницу. Форма включает поля модели `Share`.
- **Подтверждение в коде**:
  - `dashboard/views.py`: класс [`ShareCreateView`](file:///Users/lendwye/documents/antigravity/aidd-topic-03-homework/dashboard/views.py#L41-L47).
  - `dashboard/forms.py`: класс [`ShareModelForm`](file:///Users/lendwye/documents/antigravity/aidd-topic-03-homework/dashboard/forms.py#L6-L11).
  - `dashboard/templates/dashboard/create.html`: строки 8–20.

#### ФТ-17. Редактирование акции через веб-форму
- **Описание**: При отправке `POST /update/<pk>` авторизованным пользователем обновляются поля существующей акции, после чего происходит редирект на главную страницу.
- **Подтверждение в коде**:
  - `dashboard/views.py`: класс [`ShareUpdateView`](file:///Users/lendwye/documents/antigravity/aidd-topic-03-homework/dashboard/views.py#L49-L56).

#### ФТ-18. Удаление акции через веб-интерфейс
- **Описание**: При запросе `GET /delete/<pk>` авторизованному пользователю отображается диалог подтверждения удаления с именем акции. При отправке `POST /delete/<pk>` акция удаляется из БД, и происходит редирект на главную страницу.
- **Подтверждение в коде**:
  - `dashboard/views.py`: класс [`ShareDeleteView`](file:///Users/lendwye/documents/antigravity/aidd-topic-03-homework/dashboard/views.py#L58-L63).
  - `dashboard/templates/dashboard/delete.html`: строки 9–13.

---

### 5.4. Программный интерфейс REST API (`/api/v1/shares/`)

#### ФТ-19. Получение списка акций через API
- **Описание**: Запрос `GET /api/v1/shares/` возвращает список акций в формате JSON. Каждый объект содержит поля: `id`, `figi`, `isin`, `name`, `ticker`, `currency`, `last_price`, `is_trend_high`, `updated_at`.
- **Подтверждение в коде**:
  - `dashboard/api/v1/views.py`: класс [`ShareViewSet`](file:///Users/lendwye/documents/antigravity/aidd-topic-03-homework/dashboard/api/v1/views.py#L16-L22).
  - `dashboard/api/v1/serializer.py`: класс [`ShareSerializer`](file:///Users/lendwye/documents/antigravity/aidd-topic-03-homework/dashboard/api/v1/serializer.py#L6-L19).
  - `dashboard/tests.py`: метод [`test_share_list`](file:///Users/lendwye/documents/antigravity/aidd-topic-03-homework/dashboard/tests.py#L36-L47).

#### ФТ-20. Получение детальной информации об акции через API
- **Описание**: Запрос `GET /api/v1/shares/<id>/` возвращает сериализованные данные конкретной акции с HTTP-статусом 200. Если акция с указанным ID не найдена, API возвращает статус 404 Not Found.
- **Подтверждение в коде**:
  - `dashboard/tests.py`: методы [`test_share_detail`](file:///Users/lendwye/documents/antigravity/aidd-topic-03-homework/dashboard/tests.py#L48-L53) и [`test_share_detail_invalid`](file:///Users/lendwye/documents/antigravity/aidd-topic-03-homework/dashboard/tests.py#L54-L57).

#### ФТ-21. Пагинация списка акций в REST API
- **Описание**: Список акций в API поддерживает параметры пагинации `limit` и `offset`. Ответ содержит поля `count` (общее число записей), `next` (ссылка на следующую страницу), `previous` (ссылка на предыдущую) и `results` (массив акций). По умолчанию размер страницы составляет 100 элементов.
- **Подтверждение в коде**:
  - `config/settings.py`: параметры [`REST_FRAMEWORK`](file:///Users/lendwye/documents/antigravity/aidd-topic-03-homework/config/settings.py#L31-L35) (`LimitOffsetPagination`, `PAGE_SIZE = 100`).

#### ФТ-22. Точная фильтрация акций в API
- **Описание**: Запрос `GET /api/v1/shares/` поддерживает фильтрацию по полному совпадению наименования компании (`?name=...`) и биржевого тикера (`?ticker=...`).
- **Подтверждение в коде**:
  - `dashboard/api/v1/views.py`: класс [`ShareFilter`](file:///Users/lendwye/documents/antigravity/aidd-topic-03-homework/dashboard/api/v1/views.py#L10-L14) (`fields = ("name", "ticker")`).

#### ФТ-23. Сортировка акций в API
- **Описание**: Запрос `GET /api/v1/shares/` поддерживает упорядочивание результатов через параметр `?ordering=...` по полям `name` и `ticker` (включая нисходящий порядок с префиксом `-`, например `?ordering=-ticker`).
- **Подтверждение в коде**:
  - `dashboard/api/v1/views.py`: [`ShareViewSet.ordering_fields = ["name", "ticker"]`](file:///Users/lendwye/documents/antigravity/aidd-topic-03-homework/dashboard/api/v1/views.py#L21).

#### ФТ-24. Поиск по регулярному выражению в API
- **Описание**: Запрос `GET /api/v1/shares/` поддерживает параметр поиска `?search=...`, который производит фильтрацию по полю `name` с использованием синтаксиса регулярных выражений DRF (`search_fields = ["$name"]`).
- **Подтверждение в коде**:
  - `dashboard/api/v1/views.py`: [`ShareViewSet.search_fields = ["$name"]`](file:///Users/lendwye/documents/antigravity/aidd-topic-03-homework/dashboard/api/v1/views.py#L22).

#### ФТ-25. Полное обновление акции через API (PUT)
- **Описание**: Запрос `PUT /api/v1/shares/<id>/` с полным набором обязательных полей сериализатора производит обновление записи в БД и возвращает обновленный JSON-объект со статусом 200 OK. Если обязательные поля отсутствуют, возвращается статус 400 Bad Request.
- **Подтверждение в коде**:
  - `dashboard/tests.py`: методы [`test_share_update`](file:///Users/lendwye/documents/antigravity/aidd-topic-03-homework/dashboard/tests.py#L58-L77) и [`test_share_update_invalid`](file:///Users/lendwye/documents/antigravity/aidd-topic-03-homework/dashboard/tests.py#L78-L90).

#### ФТ-26. Частичное обновление акции через API (PATCH)
- **Описание**: Запрос `PATCH /api/v1/shares/<id>/` производит частичное обновление указанных полей существующей акции (предоставляется стандартным `ModelViewSet`).
- **Подтверждение в коде**:
  - `dashboard/api/v1/views.py`: наследование [`ShareViewSet` от `viewsets.ModelViewSet`](file:///Users/lendwye/documents/antigravity/aidd-topic-03-homework/dashboard/api/v1/views.py#L16).

#### ФТ-27. Удаление акции через API (DELETE)
- **Описание**: Запрос `DELETE /api/v1/shares/<id>/` удаляет существующую акцию из БД и возвращает статус 204 No Content. При попытке удаления несуществующей записи возвращается статус 404 Not Found.
- **Подтверждение в коде**:
  - `dashboard/tests.py`: методы [`test_share_delete`](file:///Users/lendwye/documents/antigravity/aidd-topic-03-homework/dashboard/tests.py#L111-L119) и [`test_share_delete_invalid`](file:///Users/lendwye/documents/antigravity/aidd-topic-03-homework/dashboard/tests.py#L120-L122).

#### ФТ-28. Создание акции через API (POST) — с дефектом реализации
- **Описание**: Запрос `POST /api/v1/shares/` валидирует тело запроса через `ShareSerializer`. При успешной валидации создается запись в таблице `Share` и возвращается статус 201 Created. При невалидных полях возвращается статус 400 Bad Request. *(Примечание: создание повторных записей блокируется дефектом Д-02)*.
- **Подтверждение в коде**:
  - `dashboard/tests.py`: методы [`test_share_create`](file:///Users/lendwye/documents/antigravity/aidd-topic-03-homework/dashboard/tests.py#L91-L104) и [`test_share_create_invalid`](file:///Users/lendwye/documents/antigravity/aidd-topic-03-homework/dashboard/tests.py#L105-L110).

---

### 5.5. Фоновые процессы, интеграции и служебные команды

#### ФТ-29. Первоначальный консольный импорт акций из Tinkoff API
- **Описание**: При выполнении команды `python manage.py add_shares` система инициирует gRPC-клиент к Tinkoff Invest API с токеном `TINKOFF_TOKEN`, запрашивает перечень доступных акций (`client.instruments.shares()`) и для каждого инструмента выполняет `Share.objects.get_or_create(...)` с параметрами `figi`, `name`, `isin`, `ticker`, `currency`, `uid`.
- **Подтверждение в коде**:
  - `dashboard/management/commands/add_shares.py`: класс [`Command`](file:///Users/lendwye/documents/antigravity/aidd-topic-03-homework/dashboard/management/commands/add_shares.py#L8-L23).

#### ФТ-30. Периодический запуск обновления рыночных цен (Celery Beat)
- **Описание**: Планировщик Celery Beat периодически публикует в брокер Redis задачу `dashboard.tasks.update_last_price` с интервалом запуска 10 секунд.
- **Подтверждение в коде**:
  - `config/celery.py`: словарь расписания [`app.conf.beat_schedule`](file:///Users/lendwye/documents/antigravity/aidd-topic-03-homework/config/celery.py#L13-L18).

#### ФТ-31. Фоновое обновление котировок и тренда (Celery Worker)
- **Описание**: Задача `update_last_price` извлекает все акции из БД, запрашивает для каждой актуальную цену через `get_last_data`, определяет направление изменения цены (`is_trend_high`) путем сравнения с предыдущим значением `share.last_price` и обновляет поля `last_price` и `is_trend_high` в БД.
- **Подтверждение в коде**:
  - `dashboard/tasks.py`: функция [`update_last_price`](file:///Users/lendwye/documents/antigravity/aidd-topic-03-homework/dashboard/tasks.py#L7-L28).
  - `dashboard/services/market_data.py`: функция [`get_last_data`](file:///Users/lendwye/documents/antigravity/aidd-topic-03-homework/dashboard/services/market_data.py#L6-L11).

#### ФТ-32. Администрирование через панель Django Admin
- **Описание**: По адресу `/admin/` доступен административный интерфейс модели `Share`. В списке отображаются `figi`, `isin`, `name`, `ticker`, `currency`, доступен поиск по этим же полям.
- **Подтверждение в коде**:
  - `dashboard/admin.py`: класс [`ShareAdmin`](file:///Users/lendwye/documents/antigravity/aidd-topic-03-homework/dashboard/admin.py#L7-L19).

---

## 6. Выявленные неоднозначности, противоречия и дефекты реализации

| Идентификатор | Компонент / Файл | Описание проблемы | Фактическое проявление и последствия |
|---|---|---|---|
| **Д-01** | `dashboard/api/v1/views.py` | В `ShareViewSet` отсутствуют `permission_classes`. | В веб-интерфейсе операции создания/удаления защищены аутентификацией, а через REST API любой анонимный пользователь может беспрепятственно модифицировать или удалять каталог акций. |
| **Д-02** | `dashboard/api/v1/serializer.py` | Поле `uid` не включено в `fields` сериализатора `ShareSerializer`. | Поле `uid` в модели `Share` обязательно и уникально. Поскольку сериализатор не принимает `uid`, при создании через API в БД передается пустое значение. Попытка создать вторую акцию через API завершается падением с ошибкой нарушения `unique constraint` на `uid`. |
| **Д-03** | `dashboard/services/market_data.py`, `dashboard/services/graph.py` | Использование только поля `price.units` (без `nano`). | Игнорируется дробная часть котировки. Акция стоимостью 150.75 руб. сохраняется и отображается как 150.00 руб. |
| **Д-04** | `dashboard/models.py` | Использование `FloatField` для цены `last_price`. | Денежные значения во float подвержены погрешностям двоичного округления. Требуется использование `DecimalField`. |
| **Д-05** | `dashboard/tasks.py` | Обновление через `Share.objects.filter(...).update(...)`. | Метод `QuerySet.update()` выполняет прямой SQL UPDATE и не триггерит поле `auto_now=True` у атрибута `updated_at`. Дата обновления в БД остается старой. |
| **Д-06** | `config/urls.py` | Маршрут объявлен как `path("user", include("user.urls"))` без слэша. | Все дочерние пути склеиваются в некорректные URL: `/userlogin/`, `/userregistration/`, `/userlogout/` вместо канонических `/user/login/` и т.д. |
| **Д-07** | `user/forms.py` | Прямое обращение `self.cleaned_data["email"]` в `RegistrationForm.clean()`. | Если email не прошел валидацию поля (например, пустой или некорректного формата), в словаре `cleaned_data` ключ `"email"` отсутствует, и метод падает с необработанным `KeyError`. |
| **Д-08** | `user/views.py` | В `RegistrationView.post()` в блоке ошибок вызывается `form.errors["__all__"].data[0].message`. | Если ошибка валидации возникла в конкретном поле (например, пароль короче минимальной длины или некорректный email), ключа `"__all__"` в словаре ошибок нет. Сервер падает с `KeyError: '__all__'`. |
| **Д-09** | `user/views.py` | В `AuthView.post()` не вызывается `form.is_valid()`. | Чтение полей происходит напрямую из `request.POST` (`form.data`). При отсутствии полей в теле запроса возникает `KeyError`. |
| **Д-10** | `user/views.py` | `LogoutView` производит выход по методу GET. | Завершение сеанса по GET-запросу нарушает правила RFC и стандарты безопасности (уязвимость к предзагрузке ссылок браузером и CSRF). |
| **Д-11** | `dashboard/views.py` | В `ShareDetailView` используется `Share.objects.get(id=pk)`. | При переходе по ID несуществующей акции поднимается необработанное исключение `Share.DoesNotExist`, приводящее к ответу HTTP 500 вместо 404 (не используется `get_object_or_404`). |
| **Д-12** | `dashboard/views.py`, `dashboard/services/graph.py` | Синхронный сетевой вызов `get_graph` при открытии детальной карточки. | Если Tinkoff API недоступен, токен не задан или исчерпаны лимиты, страница карточки падает с 500 ошибкой. Отсутствует обработка сбоев и кэширование. |
| **Д-13** | `dashboard/tasks.py` | Создание нового экземпляра `Client(TINKOFF_TOKEN)` на каждую акцию в цикле. | При N акциях в каталоге создается N раздельных gRPC-соединений (проблема сетевого N+1) вместо одного пакетного вызова `get_last_prices(figi=[...])`. |
| **Д-14** | `config/celery.py` | Несоответствие расписания: ключ назван `"add-every-5-min"`, но интервал равен `10.0` сек. | Рассинхронизация конфигурации и названия задачи. |
| **Д-15** | `config/settings.py` | Пустые значения `SECRET_KEY = ""` и `TINKOFF_TOKEN = ""`, включенный `DEBUG = True`, отсутствие поддержки `.env`. | Критический дефект безопасности и конфигурирования для рабочего окружения. |

---

## 7. Функциональные требования к новой функциональности (Задание №4)

В рамках Задания №4 реализованы 4 взаимосвязанных функциональных модуля, расширяющих возможности платформы.

### 7.1. Персональный мониторинг акций и уведомления

#### ФТ-33. Персональный список наблюдения за акциями
- **Описание**: Авторизованный пользователь имеет возможность формировать персональный список наблюдения за акциями (`WatchlistItem`), добавляя любые бумаги из доступного каталога.
- **Подтверждение в коде**:
  - `dashboard/models.py`: модель [`WatchlistItem`](file:///Users/lendwye/documents/antigravity/aidd-topic-03-homework/dashboard/models.py#L83-L129).
  - `dashboard/views.py`: представление [`WatchlistListView`](file:///Users/lendwye/documents/antigravity/aidd-topic-03-homework/dashboard/views.py#L148-L190).
  - `dashboard/templates/dashboard/watchlist_list.html`.

#### ФТ-34. Установка целевых ценовых порогов и условий
- **Описание**: Для каждого элемента списка наблюдения пользователь устанавливает целевую цену (`target_price`) и направление условия срабатывания (`condition`: `ABOVE` — текущая цена &ge; порога, `BELOW` — текущая цена &le; порога).
- **Подтверждение в коде**:
  - `dashboard/forms.py`: форма [`WatchlistForm`](file:///Users/lendwye/documents/antigravity/aidd-topic-03-homework/dashboard/forms.py#L42-L62).
  - `dashboard/api/v1/serializer.py`: [`WatchlistItemSerializer`](file:///Users/lendwye/documents/antigravity/aidd-topic-03-homework/dashboard/api/v1/serializer.py#L45-L65).

#### ФТ-35. Автоматическая проверка условий и генерация уведомлений
- **Описание**: При каждом фоновом или ручном обновлении котировок система проверяет выполнение заданных пользователем условий. При достижении пороговой цены создается запись `PriceNotification` с точным описанием события, фактической и целевой ценой.
- **Подтверждение в коде**:
  - `dashboard/services/monitoring_service.py`: функция [`check_watchlist_alerts`](file:///Users/lendwye/documents/antigravity/aidd-topic-03-homework/dashboard/services/monitoring_service.py#L10-L60).
  - `dashboard/models.py`: модель [`PriceNotification`](file:///Users/lendwye/documents/antigravity/aidd-topic-03-homework/dashboard/models.py#L131-L165).

#### ФТ-36. Защита от дублирования уведомлений
- **Описание**: При срабатывании уведомления выставляется флаг `is_triggered=True`. Повторные уведомления на том же уровне не генерируются до тех пор, пока цена инструмента не вернется обратно за пределы целевого порога (что сбрасывает флаг `is_triggered` в `False`).
- **Подтверждение в коде**:
  - `dashboard/services/monitoring_service.py`: строки 35–58.
  - `dashboard/test_task4.py`: тест `test_alert_triggered_above_condition`.

#### ФТ-37. Журнал уведомлений и управление статусом прочтения
- **Описание**: Пользователь имеет доступ к журналу полученных оповещений с индикатором количества непрочитанных событий в шапке сайта, возможностью постраничного просмотра и отметки отдельных либо всех уведомлений как прочитанных.
- **Подтверждение в коде**:
  - `dashboard/context_processors.py`: процессор [`notifications_processor`](file:///Users/lendwye/documents/antigravity/aidd-topic-03-homework/dashboard/context_processors.py#L4-L14).
  - `dashboard/views.py`: представления [`NotificationListView`](file:///Users/lendwye/documents/antigravity/aidd-topic-03-homework/dashboard/views.py#L203-L213), [`NotificationMarkReadView`](file:///Users/lendwye/documents/antigravity/aidd-topic-03-homework/dashboard/views.py#L215-L228).
  - `dashboard/api/v1/views.py`: [`PriceNotificationViewSet.mark_all_read`](file:///Users/lendwye/documents/antigravity/aidd-topic-03-homework/dashboard/api/v1/views.py#L76-L89).

---

### 7.2. Виртуальный инвестиционный портфель

#### ФТ-38. Автоматическая инициализация виртуального инвестиционного портфеля
- **Описание**: Для каждого зарегистрированного пользователя создается персональный инвестиционный портфель с настраиваемым стартовым балансом виртуальных средств (по умолчанию 100 000.00 USD).
- **Подтверждение в коде**:
  - `dashboard/models.py`: модель [`Portfolio`](file:///Users/lendwye/documents/antigravity/aidd-topic-03-homework/dashboard/models.py#L171-L232).
  - `dashboard/services/portfolio_service.py`: функция [`get_or_create_portfolio`](file:///Users/lendwye/documents/antigravity/aidd-topic-03-homework/dashboard/services/portfolio_service.py#L15-L26).

#### ФТ-39. Моделирование виртуальных сделок покупки акций
- **Описание**: Пользователь может моделировать покупку ценных бумаг по текущей рыночной цене. Система проверяет достаточность свободных средств на балансе портфеля, списывает сумму сделки, увеличивает количество акций в позиции и пересчитывает средневзвешенную цену приобретения. Все изменения выполняются атомарно с пессимистической блокировкой записи портфеля (`select_for_update`).
- **Подтверждение в коде**:
  - `dashboard/services/portfolio_service.py`: функция [`buy_share`](file:///Users/lendwye/documents/antigravity/aidd-topic-03-homework/dashboard/services/portfolio_service.py#L29-L91).
  - `dashboard/models.py`: модель [`PortfolioPosition`](file:///Users/lendwye/documents/antigravity/aidd-topic-03-homework/dashboard/models.py#L234-L289).

#### ФТ-40. Моделирование виртуальных сделок продажи и фиксация прибыли/убытка
- **Описание**: Пользователь может продавать имеющиеся акции полностью или частично. Система контролирует достаточность объема в позиции, рассчитывает реализованную прибыль или убыток (`realized_pnl = (execution_price - avg_price) * quantity`), зачисляет выручку на свободный баланс и уменьшает позицию (вплоть до удаления при нулевом остатке).
- **Подтверждение в коде**:
  - `dashboard/services/portfolio_service.py`: функция [`sell_share`](file:///Users/lendwye/documents/antigravity/aidd-topic-03-homework/dashboard/services/portfolio_service.py#L94-L159).

#### ФТ-41. Расчет агрегированной стоимости портфеля и доходности
- **Описание**: В режиме реального времени рассчитывается общая рыночная стоимость открытых позиций (`invested_value`), суммарная капитализация портфеля (`total_value = balance + invested_value`), а также абсолютный (`total_pnl`) и процентный (`total_pnl_percent`) финансовый результат относительно первоначального депозита.
- **Подтверждение в коде**:
  - `dashboard/models.py`: вычисляемые свойства [`Portfolio.invested_value`, `total_value`, `total_pnl`, `total_pnl_percent`](file:///Users/lendwye/documents/antigravity/aidd-topic-03-homework/dashboard/models.py#L208-L232).
  - `dashboard/templates/dashboard/portfolio.html`.

#### ФТ-42. Ведение журнала операций (история сделок)
- **Описание**: Каждая совершенная операция покупки или продажи сохраняется в неизменяемом журнале `PortfolioTransaction` с фиксацией времени, инструмента, объема, цены исполнения, итоговой суммы и реализованного PnL.
- **Подтверждение в коде**:
  - `dashboard/models.py`: модель [`PortfolioTransaction`](file:///Users/lendwye/documents/antigravity/aidd-topic-03-homework/dashboard/models.py#L290-L345).
  - `dashboard/views.py`: [`PortfolioDashboardView`](file:///Users/lendwye/documents/antigravity/aidd-topic-03-homework/dashboard/views.py#L236-L263).

---

### 7.3. История изменения рыночных цен и динамика

#### ФТ-43. Автоматическое сохранение рыночных котировок в базу данных
- **Описание**: При каждом периодическом обновлении котировок фоновой задачей Celery `update_last_price` текущая цена акции автоматически архивируется в таблицу `PriceHistory`. Предусмотрена дедупликация идентичных значений в пределах короткого интервала времени (1 минута).
- **Подтверждение в коде**:
  - `dashboard/models.py`: модель [`PriceHistory`](file:///Users/lendwye/documents/antigravity/aidd-topic-03-homework/dashboard/models.py#L51-L77).
  - `dashboard/services/history_service.py`: функция [`record_price`](file:///Users/lendwye/documents/antigravity/aidd-topic-03-homework/dashboard/services/history_service.py#L16-L42).
  - `dashboard/tasks.py`: вызов `record_price` в [`update_last_price`](file:///Users/lendwye/documents/antigravity/aidd-topic-03-homework/dashboard/tasks.py#L58-L60).

#### ФТ-44. Выбор временных интервалов выборки цен
- **Описание**: Пользователь и API-клиенты могут запрашивать выборку исторических котировок по стандартным периодам: 1 день (`1D`), 1 неделя (`1W`), 1 месяц (`1M`), 1 год (`1Y`) или за всё время (`ALL`).
- **Подтверждение в коде**:
  - `dashboard/services/history_service.py`: функции [`_get_period_cutoff`, `get_price_history`](file:///Users/lendwye/documents/antigravity/aidd-topic-03-homework/dashboard/services/history_service.py#L44-L65).

#### ФТ-45. Расчет аналитических показателей динамики котировок
- **Описание**: На основе накопленной истории автоматически рассчитываются: стартовая и финишная цена за интервал, минимальный и максимальный экстремумы, абсолютное изменение стоимости и процентный прирост/просадка.
- **Подтверждение в коде**:
  - `dashboard/services/history_service.py`: функция [`calculate_price_dynamics`](file:///Users/lendwye/documents/antigravity/aidd-topic-03-homework/dashboard/services/history_service.py#L67-L113).
  - `dashboard/api/v1/views.py`: действие [`ShareViewSet.dynamics`](file:///Users/lendwye/documents/antigravity/aidd-topic-03-homework/dashboard/api/v1/views.py#L50-L56).

#### ФТ-46. Построение интерактивных графиков на основе накопленной истории
- **Описание**: Приложение динамически генерирует интерактивные линейные графики изменения цен (Plotly) с цветовой индикацией тренда за выбранный период и подсказками в точках фиксации данных.
- **Подтверждение в коде**:
  - `dashboard/services/history_service.py`: функция [`generate_history_chart`](file:///Users/lendwye/documents/antigravity/aidd-topic-03-homework/dashboard/services/history_service.py#L115-L156).
  - `dashboard/views.py`: представления [`ShareDetailView`](file:///Users/lendwye/documents/antigravity/aidd-topic-03-homework/dashboard/views.py#L64-L115), [`SharePriceHistoryView`](file:///Users/lendwye/documents/antigravity/aidd-topic-03-homework/dashboard/views.py#L309-L332).

---

### 7.4. Симулятор инвестиционных стратегий

#### ФТ-47. Создание и настройка торговых стратегий
- **Описание**: Пользователь может конструировать персональные инвестиционные стратегии двух типов:
  1. `THRESHOLD_BUY_SELL` — пороговая стратегия (покупка при цене &le; $P_1$, продажа при цене &ge; $P_2$).
  2. `DIP_BUY_PROFIT_SELL` — процентная стратегия (усреднение при падении на $X$\%, фиксация прибыли при росте на $Y$\%).
  Форма и сериализатор валидируют логическую корректность порогов ($P_{buy} < P_{sell}$).
- **Подтверждение в коде**:
  - `dashboard/models.py`: модель [`TradingStrategy`](file:///Users/lendwye/documents/antigravity/aidd-topic-03-homework/dashboard/models.py#L351-L414).
  - `dashboard/forms.py`: форма [`TradingStrategyForm`](file:///Users/lendwye/documents/antigravity/aidd-topic-03-homework/dashboard/forms.py#L65-L125).

#### ФТ-48. Автоматическое исполнение симуляции, протоколирование и оценка эффективности
- **Описание**: Система автоматически оценивает рыночные условия для активных стратегий как при поступлении новых котировок, так и по ручному запросу пользователя («Запустить шаг симуляции»). При совпадении условий автоматически инициируется виртуальная сделка покупки/продажи в портфеле пользователя, факт сделки или пропуска логируется в `StrategyExecutionLog`, а на странице стратегии отображаются ключевые метрики эффективности: суммарный реализованный PnL, количество сделок и текущая позиция.
- **Подтверждение в коде**:
  - `dashboard/services/strategy_service.py`: функции [`execute_strategy`, `simulate_active_strategies`, `get_strategy_performance`](file:///Users/lendwye/documents/antigravity/aidd-topic-03-homework/dashboard/services/strategy_service.py#L17-L245).
  - `dashboard/models.py`: модель [`StrategyExecutionLog`](file:///Users/lendwye/documents/antigravity/aidd-topic-03-homework/dashboard/models.py#L416-L449).
  - `dashboard/views.py`: представления [`StrategyListView`, `StrategyDetailView`, `StrategyRunView`, `StrategyToggleActiveView`](file:///Users/lendwye/documents/antigravity/aidd-topic-03-homework/dashboard/views.py#L340-L442).

