# Восстановленные функциональные требования Investing Demo

## Основание и границы документа

Требования восстановлены по исходному коду приложения до модернизации, описанному в [ANALYSIS.md](ANALYSIS.md). Исследованная исходная версия — коммит `362510b`; ссылки на код зафиксированы на этой версии. Последующая модернизация описана в [AUDIT.md](AUDIT.md). Приложение и тесты при подготовке документа не запускались.

Формулировки ниже описывают наблюдаемую в коде реализацию. Ссылки ведут к файлам и строкам, а упомянутые тесты служат дополнительным свидетельством предусмотренного поведения, без утверждения об их успешном выполнении. Поведение generic views, ModelForm и ModelViewSet восстановлено по подключённым механизмам Django и DRF. Дефекты и спорные решения выделены отдельно и не задают требований к их сохранению. ФТ-27 имеет явно указанное ограничение реализации.

Приложение ведёт **общий каталог акций**: в `Share` нет владельца и связей с пользователями ([модель](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/models.py#L4), [пользовательская модель](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/user/models.py#L1)). Роли: посетитель, вошедший пользователь, администратор Django, клиент REST API и оператор служебных команд. Права HTML-интерфейса и API нельзя считать одинаковыми — см. Д-01.

## Основные сценарии

| Участник и сценарий | Последовательность и результат | Требования |
| --- | --- | --- |
| Посетитель просматривает акции | Открывает главную, переходит между страницами, выбирает тикер; получает карточку и график при доступности рыночного API | ФТ-01–06 |
| Новый пользователь регистрируется | Открывает регистрацию из формы входа, вводит email и два пароля; после успешной проверки создаётся учётная запись и открывается сессия | ФТ-08–11 |
| Пользователь входит и выходит | Отправляет email и пароль; при успехе попадает на главную, затем может завершить сессию | ФТ-07, 12–14 |
| Вошедший пользователь управляет каталогом | Открывает форму добавления или изменения либо страницу подтверждения удаления; после успешной операции возвращается к списку | ФТ-15–20 |
| Клиент API работает с акциями | Получает список или запись, задаёт фильтры, поиск и сортировку, изменяет или удаляет запись; создание имеет ограничение Д-02 | ФТ-21–30 |
| Оператор загружает справочник | Запускает `python manage.py add_shares` с настроенным доступом к Tinkoff API; инструменты записываются в БД | ФТ-31–32 |
| Фоновый процесс обновляет цены | При работающих Beat, Redis и Worker запрашивает цены акций и сохраняет текущие значения и направление изменения | ФТ-33–35 |
| Администратор управляет справочником | Входит в Django Admin с соответствующими правами, просматривает и ищет акции, редактирует записи | ФТ-36–37 |

## Нумерованный список функциональных требований

### Просмотр каталога и карточки

1. **ФТ-01. Публичный список акций.** При `GET /` система показывает посетителю каталог без обязательного входа, упорядоченный по `name`. В строке отображаются тикер, название, ISIN, сохранённая цена и валюта. Тикер является ссылкой на карточку.

   **Подтверждение:** [ShareListView](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/views.py#L20), [шаблон списка](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/templates/dashboard/list.html#L15), [маршруты](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/urls.py#L14), [тест HTML-списка](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/tests.py#L32).

2. **ФТ-02. Постраничный просмотр.** HTML-список содержит не более 100 акций на странице. Пользователь переключает страницы через параметр `page`, номера страниц и ссылки назад/вперёд.

   **Подтверждение:** [paginate_by](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/views.py#L25), [элементы пагинации](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/templates/dashboard/list.html#L60).

3. **ФТ-03. Пустой каталог.** Если список акций пуст, вместо таблицы выводится сообщение «Акций еще нет».

   **Подтверждение:** [условие share_list](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/templates/dashboard/list.html#L15), [пустое состояние](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/templates/dashboard/list.html#L83).

4. **ФТ-04. Карточка акции.** При открытии существующей акции по `GET /<pk>` система получает запись по её внутреннему идентификатору и выводит название, сохранённую цену, валюту и значение `updated_at`. Это отображение поля БД, а не гарантия актуальности времени котировки — см. Д-04.

   **Подтверждение:** [ShareDetailView.get](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/views.py#L29), [шаблон карточки](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/templates/dashboard/detail.html#L8), [маршрут](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/urls.py#L15).

5. **ФТ-05. График исторических котировок.** При открытии карточки система запрашивает у Tinkoff дневные свечи начиная с даты за 180 дней до текущего момента и строит линейный график по датам и ценам закрытия. Период задаётся кодом; выбора периода в интерфейсе нет. Сценарий требует доступного API и токена; ограничения точности описаны в Д-03.

   **Подтверждение:** [get_graph](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/services/graph.py#L11), [вызов из карточки](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/views.py#L38), [вставка графика](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/templates/dashboard/detail.html#L23).

6. **ФТ-06. Обозначение направления цены.** В HTML-списке сохранённое значение `is_trend_high=True` обозначается зелёным фоном цены, `False` — красным. Обработка неизвестного значения и смысл равенства цен рассматриваются отдельно в Н-02.

   **Подтверждение:** [условие оформления цены](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/templates/dashboard/list.html#L35).

### Учётная запись и сессия

7. **ФТ-07. Навигация по состоянию входа.** Посетителю показывается ссылка «Войти»; вошедшему пользователю — его email и ссылка «Выход». Из формы входа доступен переход к регистрации, из регистрации — ко входу.

   **Подтверждение:** [шапка сайта](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/templates/dashboard/base.html#L36), [форма входа](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/user/templates/user/auth.html#L19), [форма регистрации](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/user/templates/user/registration.html#L23).

8. **ФТ-08. Данные регистрации.** Форма регистрации запрашивает email, пароль и повтор пароля. Все три поля объявлены обязательными, email — полем `EmailField`; создание учётной записи выполняется только после успешного `form.is_valid()`. Обработка некорректных полей имеет дефект Д-05, поэтому корректный ответ для любого ошибочного ввода здесь не гарантируется.

   **Подтверждение:** [RegistrationForm](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/user/forms.py#L8), [RegistrationView.post](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/user/views.py#L44), [шаблон](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/user/templates/user/registration.html#L3).

9. **ФТ-09. Совпадение паролей.** Если оба пароля прошли проверку полей, но различаются, регистрация отклоняется с сообщением «Введенные пароли не совпадают» и повторным показом формы.

   **Подтверждение:** [RegistrationForm.clean](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/user/forms.py#L30), [вывод ошибки регистрации](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/user/views.py#L52).

10. **ФТ-10. Проверка повторного email.** При корректно заполненных полях регистрация проверяет наличие пользователя через `User.objects.filter(email=email)`. При совпадении отклоняет регистрацию и предлагает другой email либо вход. Это проверка формы; регистронезависимая уникальность email документом не утверждается — см. Д-06.

    **Подтверждение:** [проверка существующего email](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/user/forms.py#L39).

11. **ФТ-11. Завершение регистрации.** После успешной проверки система создаёт стандартного пользователя Django, передавая email в поля `username` и `email`, а пароль — в `create_user()`. Затем аутентифицирует созданного пользователя, открывает сессию и перенаправляет на главную. Пароль обрабатывается механизмом хеширования Django.

    **Подтверждение:** [RegistrationForm.save](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/user/forms.py#L48), [создание сессии и перенаправление](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/user/views.py#L46), [используемая модель](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/user/models.py#L1).

12. **ФТ-12. Успешный вход.** При отправке заполненной формы входа система вызывает `authenticate()` с email в нижнем регистре как `username` и переданным паролем. Если пользователь аутентифицирован, система открывает сессию и перенаправляет его на главную.

    **Подтверждение:** [AuthView.post](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/user/views.py#L16).

13. **ФТ-13. Отказ во входе.** Если `authenticate()` возвращает `None` для переданных реквизитов, система повторно показывает форму с сообщением «Неверный логин или пароль! Повторите попытку.». Обработка отсутствующих полей рассматривается в Д-07.

    **Подтверждение:** [ветвление AuthView.post](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/user/views.py#L23), [вывод сообщения](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/user/templates/user/auth.html#L14).

14. **ФТ-14. Завершение сессии.** При переходе по ссылке выхода система вызывает `logout()` и возвращает пользователя на главную страницу. Метод запроса отмечен отдельно как спорное решение Н-04.

    **Подтверждение:** [LogoutView](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/user/views.py#L58), [ссылка выхода](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/templates/dashboard/base.html#L39).

### Изменение каталога через HTML и правила данных

15. **ФТ-15. Доступ к HTML-изменениям.** Добавление, изменение и удаление акций через HTML-представления доступны после входа. При прямом обращении анонимного посетителя к этим представлениям система перенаправляет его на главную. Кнопки управления в списке показываются вошедшему пользователю.

    **Подтверждение:** [IsUserAuthenticatedMixin](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/views.py#L11), [подключение mixin к CRUD](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/views.py#L41), [кнопки управления](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/templates/dashboard/list.html#L8).

16. **ФТ-16. Добавление акции.** Вошедший пользователь открывает `/create`, заполняет форму и отправляет её. При успешной валидации создаётся запись общего каталога и выполняется перенаправление на главную.

    **Подтверждение:** [ShareCreateView](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/views.py#L41), [ShareModelForm](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/forms.py#L6), [POST-форма](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/templates/dashboard/create.html#L13), [маршрут](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/urls.py#L16).

17. **ФТ-17. Редактирование акции.** Вошедший пользователь открывает `/update/<pk>`, изменяет данные существующей акции и сохраняет форму. Используется та же форма, что при добавлении; после успешной записи система возвращает пользователя на главную.

    **Подтверждение:** [ShareUpdateView](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/views.py#L49), [ShareModelForm](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/forms.py#L6), [маршрут](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/urls.py#L17).

18. **ФТ-18. Подтверждение удаления.** При открытии `/delete/<pk>` система показывает название выбранной акции и запрос подтверждения. Отправка POST-формы удаляет запись и перенаправляет на главную; показ страницы подтверждения сам по себе запись не удаляет.

    **Подтверждение:** [ShareDeleteView](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/views.py#L58), [шаблон подтверждения](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/templates/dashboard/delete.html#L9), [маршрут](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/urls.py#L18).

19. **ФТ-19. Обязательные атрибуты и уникальность.** HTML-форма требует `figi`, `isin`, `name`, `ticker`, `currency`, `uid`. FIGI и UID ограничены 255 символами, название и ISIN — 255, тикер — 10, валюта — 20. Значения FIGI, тикера и UID должны быть уникальны в общем каталоге; ограничения проверяются модельной формой и схемой БД. UID хранится строкой, отдельная проверка формата UUID не задана.

    **Подтверждение:** [Share](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/models.py#L4), [ModelForm](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/forms.py#L6), [миграция уникальности](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/migrations/0002_update_share.py#L11), [миграция UID](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/migrations/0003_add_uuid.py#L11).

20. **ФТ-20. Необязательные рыночные поля.** При добавлении и редактировании HTML-форма позволяет задать цену и признак направления либо оставить их неопределёнными. Автоматические `id` и `updated_at` не являются редактируемыми полями формы. Проверки положительности цены, справочник валют и связь акции с владельцем не реализованы.

    **Подтверждение:** [last_price, is_trend_high, updated_at](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/models.py#L13), [fields = "__all__"](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/forms.py#L11).

### REST API

21. **ФТ-21. Получение списка через API.** `GET /api/v1/shares/` предоставляет записи общего каталога. Представление акции содержит `id`, `figi`, `isin`, `name`, `ticker`, `currency`, `last_price`, `is_trend_high`, `updated_at`; `uid` в представление не включён.

    **Подтверждение:** [ShareViewSet](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/api/v1/views.py#L16), [ShareSerializer](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/api/v1/serializer.py#L6), [регистрация маршрута](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/api/v1/router.py#L6), [тест списка](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/tests.py#L36).

22. **ФТ-22. Получение акции через API.** `GET /api/v1/shares/<pk>/` возвращает представление существующей акции; обращение к отсутствующей записи обрабатывается DRF с ответом 404. Это правило относится к API, а не к HTML-карточке — см. Д-08.

    **Подтверждение:** [ModelViewSet и queryset](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/api/v1/views.py#L16), [тест существующей записи](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/tests.py#L48), [тест отсутствующей записи](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/tests.py#L54).

23. **ФТ-23. Фильтрация списка API.** Клиент может ограничивать список точным совпадением `name` и/или `ticker`, например `?ticker=AAPL`. Фильтры применяются к queryset общего каталога.

    **Подтверждение:** [ShareFilter](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/api/v1/views.py#L10), [DjangoFilterBackend](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/api/v1/views.py#L19).

24. **ФТ-24. Сортировка списка API.** Параметр `ordering` позволяет сортировать по `name` и `ticker`, в том числе в обратном порядке через префикс `-`, например `?ordering=-ticker`. Порядок API без этого параметра отдельно не задан.

    **Подтверждение:** [OrderingFilter и ordering_fields](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/api/v1/views.py#L19).

25. **ФТ-25. Поиск по названию через API.** Параметр `search` применяется к названию акции с настройкой `search_fields = ["$name"]`, то есть как регистронезависимое регулярное выражение DRF. Например, `?search=^Apple` ограничивает результат названиями, начинающимися с Apple. Интерфейс обычного поиска подстроки этим кодом не задан; спорность выбора отмечена в Н-03.

    **Подтверждение:** [SearchFilter и search_fields](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/api/v1/views.py#L19).

26. **ФТ-26. Пагинация API.** Список API использует `limit` и `offset`, по умолчанию возвращая до 100 записей. Ответ содержит `count`, `next`, `previous` и `results`. В проекте собственный максимальный `limit` не установлен.

    **Подтверждение:** [LimitOffsetPagination и PAGE_SIZE](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/config/settings.py#L31), [использование results в тесте](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/tests.py#L39).

27. **ФТ-27. Подключённая операция создания API — с ограничением.** Маршрут `POST /api/v1/shares/` направляет данные в стандартную операцию создания `ModelViewSet` через `ShareSerializer`; не прошедшие валидацию входные данные отклоняются с 400. Полноценное создание произвольного числа акций через API не подтверждается контрактом UID — см. Д-02. Успех для любого корректного инструмента не является восстановленным требованием.

    **Подтверждение:** [ModelViewSet](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/api/v1/views.py#L16), [роутер](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/api/v1/router.py#L6), [набор полей](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/api/v1/serializer.py#L9), [тесты создания и валидации](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/tests.py#L91).

28. **ФТ-28. Изменение акции через API.** `PUT /api/v1/shares/<pk>/` выполняет полное обновление доступных полей сериализатора, `PATCH` — частичное. Автоматические `id` и `updated_at` доступны только для чтения; изменение UID через этот сериализатор не предоставлено. После успешного изменения возвращается представление акции.

    **Подтверждение:** [ModelViewSet](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/api/v1/views.py#L16), [ShareSerializer](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/api/v1/serializer.py#L6), [автоматическое поле updated_at](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/models.py#L17), [тест PUT](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/tests.py#L58). Отдельного теста PATCH нет.

29. **ФТ-29. Проверка входных данных API.** При создании и полном обновлении сериализатор проверяет обязательность доступных строковых полей, ограничения длины и уникальность FIGI и тикера по модели. Неполное полное обновление, например только с `figi` и `name`, отклоняется с 400. Необязательные цена и направление определяются параметрами полей модели; дополнительного бизнес-валидатора сериализатора нет.

    **Подтверждение:** [ModelSerializer](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/api/v1/serializer.py#L6), [Share](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/models.py#L7), [тест неполного PUT](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/tests.py#L78), [тест неполного POST](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/tests.py#L105).

30. **ФТ-30. Удаление через API.** `DELETE /api/v1/shares/<pk>/` удаляет существующую акцию с ответом 204; отсутствующая запись даёт 404. Удалённая запись больше не входит в список.

    **Подтверждение:** [ModelViewSet](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/api/v1/views.py#L16), [тест удаления](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/tests.py#L111), [тест отсутствующей записи](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/tests.py#L120).

### Импорт и фоновая обработка

31. **ФТ-31. Импорт справочника акций.** Оператор запускает `python manage.py add_shares`. При доступном Tinkoff API система получает список акций и сохраняет FIGI, название, ISIN, тикер, валюту и UID. Команда не задаёт начальную рыночную цену и направление.

    **Подтверждение:** [Command.handle](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/management/commands/add_shares.py#L11), [настройка токена](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/config/settings.py#L134), [необязательные поля цены](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/models.py#L13).

32. **ФТ-32. Пропуск полностью совпадающего инструмента при импорте.** Если в БД уже существует запись с совпадением всех шести переданных атрибутов, импорт использует её без создания второй записи. Это не требование синхронизации изменившихся реквизитов; случай изменения атрибута описан в Д-09.

    **Подтверждение:** [get_or_create с полным набором атрибутов](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/management/commands/add_shares.py#L15).

33. **ФТ-33. Автоматическое получение последних цен.** При работающей инфраструктуре Celery периодическая задача выбирает все акции, запрашивает последнюю цену по FIGI каждой и сохраняет её в `last_price`. Запрос выполняется последовательно для каждой записи. Реальное расписание и точность значения отдельно отмечены в Н-01 и Д-03; гарантии завершения обновления всего каталога за заданный срок нет.

    **Подтверждение:** [beat_schedule](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/config/celery.py#L13), [update_last_price](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/tasks.py#L8), [get_last_data](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/services/market_data.py#L6), [брокер](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/config/settings.py#L141).

34. **ФТ-34. Сравнение последовательных цен.** Для сравнимых цен, если новая ниже предыдущей, задача сохраняет `is_trend_high=False`; если выше — `True`. Случаи равенства и отсутствующей предыдущей цены не формулируются как бизнес-требования и описаны в Н-02.

    **Подтверждение:** [сравнение и запись направления](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/tasks.py#L15).

35. **ФТ-35. Продолжение обхода при ошибке отдельной акции.** Если при обработке одной акции возникает перехваченное исключение, задача записывает ошибку в лог и продолжает обход следующих записей. Сообщения логгера `main` направляются в консоль и `app.logs`; автоматическое повторение неуспешного запроса отдельно не задано.

    **Подтверждение:** [обработка исключений в цикле](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/tasks.py#L11), [LOGGING](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/config/settings.py#L37).

### Административный интерфейс

36. **ФТ-36. Администрирование каталога.** По `/admin/` подключён стандартный Django Admin; модель `Share` зарегистрирована для просмотра и управления пользователями с соответствующими правами администратора. В списке отображаются FIGI, ISIN, название, тикер и валюта.

    **Подтверждение:** [маршрут admin](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/config/urls.py#L5), [ShareAdmin и list_display](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/admin.py#L6), [установленные admin/auth](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/config/settings.py#L13).

37. **ФТ-37. Поиск и редактируемые данные администратора.** Административный поиск ведётся по FIGI, ISIN, названию и тикеру. Форма управления акцией включает эти поля, валюту, UID, последнюю цену и признак направления; `updated_at` в список редактируемых полей не включён.

    **Подтверждение:** [search_fields и fields](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/admin.py#L9).

### Проверки HTML-запросов

38. **ФТ-38. CSRF-проверка отправки HTML-форм.** Формы регистрации, входа, добавления, изменения и удаления акции передают CSRF-токен. Их POST-запросы проходят стандартную проверку `CsrfViewMiddleware`: запрос без действительного токена отклоняется. Это правило HTML-форм; оно не подменяет отсутствующие ограничения доступа API.

    **Подтверждение:** [middleware](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/config/settings.py#L65), [регистрация](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/user/templates/user/registration.html#L5), [вход](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/user/templates/user/auth.html#L4), [добавление и изменение](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/templates/dashboard/create.html#L14), [удаление](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/templates/dashboard/delete.html#L10).

## Неоднозначности и противоречия

Эти наблюдения требуют уточнения при последующей модернизации и **не являются требованиями к сохранению спорного поведения**.

| Код | Наблюдаемая реализация и неопределённость | Подтверждение |
| --- | --- | --- |
| Н-01 | Ключ расписания называется `add-every-5-min`, но `schedule=10.0` ставит задачу в очередь каждые 10 секунд. Требуемый бизнес-интервал из кода однозначно не восстанавливается; частота постановки также не гарантирует частоту успешной записи | [config/celery.py](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/config/celery.py#L13) |
| Н-02 | Равная цена даёт `True`; ошибка сравнения, в том числе с `None`, также даёт `True`. В шаблоне неизвестное направление окрашивается как отрицательное. Представление неизменной цены и отсутствия данных не определено отдельными состояниями | [задача](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/tasks.py#L15), [список](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/templates/dashboard/list.html#L35) |
| Н-03 | `$name` задаёт поиск регулярным выражением. В интерфейсе нет объяснения, а тестов поиска нет; нельзя подменять это требованием обычного текстового поиска | [search_fields](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/api/v1/views.py#L22) |
| Н-04 | Выход выполняется GET-запросом. Это факт маршрута и view, но обоснования выбора метода нет | [LogoutView.get](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/user/views.py#L61), [ссылка](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/templates/dashboard/base.html#L39) |
| Н-05 | Пользовательские URL фактически имеют вид `/userlogin/`, `/userregistration/`, `/userlogout/`: префикс `user` соединяется с дочерними путями без разделителя. Такие адреса не трактуются как обязательное бизнес-правило | [корневой префикс](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/config/urls.py#L7), [дочерние пути](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/user/urls.py#L7) |

## Возможные дефекты реализации

Ни один пункт этой таблицы не является функциональным требованием. Последствия выведены из кода без воспроизведения в работающем приложении.

| Код | Дефект или риск и его следствие | Подтверждение |
| --- | --- | --- |
| Д-01 | HTML-изменения требуют входа, а ViewSet и глобальные настройки DRF не задают ограничений доступа. При стандартных настройках DRF анонимному клиенту доступны и операции изменения. Обход HTML-ограничения не оформляется как требование открытой записи | [HTML-mixin](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/views.py#L11), [ViewSet](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/api/v1/views.py#L16), [REST_FRAMEWORK](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/config/settings.py#L31), [тест изменения без входа](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/tests.py#L58) |
| Д-02 | Уникальный обязательный `uid` отсутствует в сериализаторе. UID из тестового JSON не сохраняется через объявленные поля; повторные создания могут нарушить уникальность неявной пустой строки. Наличие теста с ожидаемым 201 не доказывает полноценную реализацию создания | [модель](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/models.py#L12), [сериализатор](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/api/v1/serializer.py#L9), [тестовые данные](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/tests.py#L21), [тест POST](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/tests.py#L91) |
| Д-03 | Последняя цена и цена закрытия свечи берутся только из `.units`; дробная составляющая не учитывается. Обрезание котировки не является бизнес-правилом округления | [последняя цена](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/services/market_data.py#L11), [свечи](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/services/graph.py#L20) |
| Д-04 | Задача обновляет цену через `QuerySet.update()` без `updated_at`; `auto_now` при этом не срабатывает. Полученное время котировки также не сохраняется, поэтому подпись времени в карточке может вводить в заблуждение | [поле даты](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/models.py#L17), [задача](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/tasks.py#L13), [карточка](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/templates/dashboard/detail.html#L13) |
| Д-05 | `RegistrationForm.clean()` обращается напрямую к ключам `cleaned_data`, которые могут отсутствовать при ошибке поля. View предполагает наличие `form.errors["__all__"]`. Ошибочный email или пропущенный пароль могут привести к `KeyError` вместо сообщения формы | [clean](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/user/forms.py#L30), [обработка ошибок](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/user/views.py#L52) |
| Д-06 | Регистрация не приводит email к нижнему регистру так же, как вход; проверка email не обеспечивает уникальность без учёта регистра. Возможна несогласованность зарегистрированного username и последующего входа | [save](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/user/forms.py#L48), [вход с lower](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/user/views.py#L19) |
| Д-07 | Вход читает `form.data` без `is_valid()`: типовая проверка `EmailField` обходится, а отсутствующие ключи могут вызвать исключение. Настроенные валидаторы сложности пароля явно не вызываются пользовательской формой регистрации; нельзя утверждать наличие проверки сложности | [AuthView.post](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/user/views.py#L16), [создание пользователя](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/user/forms.py#L48), [настроенные валидаторы](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/config/settings.py#L106) |
| Д-08 | HTML-карточка использует `Share.objects.get()` без преобразования `DoesNotExist` в 404 и вызывает внешний API без обработки сбоя. Отсутствующая акция или ошибка интеграции могут привести к серверной ошибке | [ShareDetailView.get](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/views.py#L31), [get_graph](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/services/graph.py#L11) |
| Д-09 | Импорт ищет запись по всем реквизитам. Если у существующего FIGI изменился другой атрибут, попытка создать новую запись может нарушить уникальность вместо обновления реквизитов | [get_or_create](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/management/commands/add_shares.py#L15), [уникальные поля](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/models.py#L7) |
| Д-10 | В исходных настройках пустые `SECRET_KEY` и токен Tinkoff. Успешность сценариев с сессией и рыночным API требует конфигурации окружения; текущие значения не подтверждают готовность приложения к запуску | [SECRET_KEY](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/config/settings.py#L6), [TINKOFF_TOKEN](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/config/settings.py#L134) |

## Функциональность за пределами исходной версии

Персональные списки наблюдения, целевые цены и уведомления, виртуальные портфели и сделки, локальная история котировок и симуляция стратегий не входят в восстановленные требования. Они перечислены в [HOMEWORK.md](HOMEWORK.md) как новое развитие. В текущем коде доменная модель ограничивается `Share`, пользовательские представления — регистрацией и сессией, а рыночные сервисы получают внешние данные без накопления истории ([модель](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/models.py), [маршруты](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/urls.py), [пользовательские views](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/user/views.py), [сервисы](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/services/graph.py), [задача](https://github.com/gospodiupasibozheeeee/aidd-topic-03-homework/blob/362510b/dashboard/tasks.py)).
