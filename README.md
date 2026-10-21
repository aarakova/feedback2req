# feedback2req

И1/И2а: backend с PostgreSQL, локальными учётными записями, серверными сессиями,
проектами, управлением доступом и сохранением текстовых отзывов/документов.
Ф1а/Ф1б добавляют React frontend: регистрация, вход/выход, восстановление сессии,
проекты и полномочия, ввод/списки/просмотр текстовых отзывов и документов.
Основание: [DEC-007–DEC-010](docs/DECISIONS.md).
Worker и AI-обработка отсутствуют; HTML-прототип в `prototype/` остаётся
визуальным референсом. Остальной [проект среза](docs/FIRST_TEXT_SLICE.md)
не утверждён этими решениями.

## Локальный запуск Docker Compose

Нужны Docker Engine/Desktop с Linux containers и Docker Compose v2.
Из корня репозитория (PowerShell):

```powershell
Copy-Item .env.example .env
```

В `.env` задайте собственный `POSTGRES_PASSWORD`: случайную строку минимум
32 символа из букв/цифр (она включается в URL БД, поэтому для этого примера
не используйте специальные символы URL). Файл игнорируется Git.
Профиль `.env.example` разрешает HTTP только на loopback.

```powershell
docker compose up -d --wait db
docker compose build api
docker compose run --rm api alembic upgrade head
docker compose up -d api
```

Интерфейс: `http://localhost:8000/`, API: `http://localhost:8000/api/v1`.
Dockerfile собирает frontend на Node 24 и включает только сборку в образ API.
Автомиграции при импорте/старте нет;
при развёртывании миграция выполняется отдельной командой до запуска API.
Проверка версии: `docker compose run --rm api alembic current` (ожидается `m02a`).
Та же `alembic upgrade head` обновляет существующую m01 без сброса данных И1.
Перезапуск с тем же volume: `docker compose restart db api`.
Остановка: `docker compose stop`. Постоянный `postgres_data` сохраняет БД.
Команд удаления volume для пользовательских данных инструкция не предусматривает.

Реальная работа в LAN требует TLS, `F2R_LOCAL_HTTP=false` и точный HTTPS
`F2R_ALLOWED_ORIGIN`; внешний TLS proxy/хостинг этим этапом не настраиваются.
Порт БД наружу не публикуется, API слушает только loopback хоста.

## Запуск через Python

Нужны Python 3.12+ и отдельная PostgreSQL 17. Команды из корня:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements-test.lock
.\.venv\Scripts\python.exe -m pip install --no-deps -e backend
$env:F2R_DATABASE_URL = 'postgresql+psycopg://USER:PASSWORD@127.0.0.1:5432/feedback2req'
$env:F2R_ALLOWED_ORIGIN = 'http://localhost:8000'
$env:F2R_LOCAL_HTTP = 'true'
.\.venv\Scripts\python.exe -m alembic -c backend/alembic.ini upgrade head
.\.venv\Scripts\python.exe -m uvicorn feedback2req.main:create_app --factory --host 127.0.0.1 --port 8000 --no-access-log --no-proxy-headers
```

Подставляйте URL и секреты только локально; не сохраняйте их в отслеживаемые
файлы/историю общих команд. Конфигурация читается из окружения, `.env` читает
Compose. Для Python её нужно передать самостоятельно. Пароли, сырые токены,
тела запросов и SQL-параметры приложение не логирует. SQL echo выключен.

Конфигурация `F2R_*`: обязательный `DATABASE_URL`; `ALLOWED_ORIGIN`,
`LOCAL_HTTP`; `SESSION_SECONDS=86400`, `IDLE_SECONDS=1800`,
`ARGON_TIME_COST=3`, `ARGON_MEMORY_COST=65536` (KiB), `ARGON_PARALLELISM=4`,
`MAX_BODY_BYTES=16384`, `MAX_MATERIAL_TEXT_CHARS=8192`,
`LOGIN_LIMIT=10`, `LOGIN_WINDOW_SECONDS=60`,
`PAGE_SIZE=50`. Лимитер register/login общий по IP в одном процессе;
он сбрасывается при restart. И1 запускается с одним процессом API.

## Frontend Ф1а/Ф1б

Нужен Node.js 20.19+ либо 22.12+ (локально проверен Node 24).
Для разработки из каталога `frontend`:

```powershell
npm.cmd ci
npm.cmd run dev
```

Откройте **`http://localhost:5173`**. Vite использует фиксированный порт,
проксирует `/api` на `http://127.0.0.1:8000` и сохраняет Origin браузера.
Backend должен быть запущен с `F2R_ALLOWED_ORIGIN=http://localhost:5173`
и `F2R_LOCAL_HTTP=true`. Для Python передайте эти переменные перед Uvicorn;
для Compose укажите их в `.env` и выполните `docker compose up -d api`.
Не заменяйте localhost на 127.0.0.1 в адресе браузера: Origin должен совпадать
точно. При другом порте API задайте `F2R_API_PROXY_TARGET` перед Vite;
эта переменная нужна только серверу разработки, не попадает в клиентскую сборку.
Проверки Origin/CSRF и cookie backend сохраняются.

Для раздачи сборки приложением выполните из `frontend`:

```powershell
npm.cmd run build
```

Перезапустите Python API с `F2R_ALLOWED_ORIGIN=http://localhost:8000`,
откройте `http://localhost:8000/`. По умолчанию API ищет `frontend/dist`;
другой локальный путь задаётся `F2R_FRONTEND_DIST`. Без сборки работает API.
При Compose сборка включается командой `docker compose build api` выше,
а Origin также должен соответствовать адресу браузера.

Проверка вручную: зарегистрируйтесь (регистрация не выполняет автоматический
вход), войдите, создайте и откройте проект, перезагрузите страницу. Должны
сохраниться сессия и проект; полномочия берутся из API. После выхода открытие
адреса проекта снова показывает форму входа. Пароль/CSRF/session token не
сохраняются в localStorage/sessionStorage; cookie сессии остаётся HttpOnly.
Внутри проекта откройте раздел **Материалы**. «Добавить обратную связь»
сохраняет текст отзыва, «Добавить документацию» — название и текст контекста
продукта. После подтверждения API материал открывается по ID; каждый список
имеет собственную кнопку «Показать ещё». Перезагрузите страницу: выбранный
раздел/материал должен восстановиться. Вернуться к обзору можно через вкладку
проекта, к списку проектов — через «Все проекты».

Ошибки сохраняют введённое в открытой форме. При потере ответа результат
сохранения неизвестен: обновите список перед повтором, чтобы проверить,
не появился ли уже материал. Тексты не обрезаются и не нормализуются клиентом;
ограничения окончательно проверяет сервер. Браузерный textarea может заменить
CRLF на LF до отправки — сервер сохраняет фактически отправленный JSON.
Тексты/черновики не записываются в localStorage/sessionStorage или логи.
При завершении сессии/потере доступа проектный интерфейс очищается.
Управление участниками остаётся доступным только через API.

Браузерные тесты используют отдельную PostgreSQL и уникальную тестовую схему,
не меняют рабочую БД. После установки Python backend и тестовых зависимостей,
запуска `compose.test.yaml` и сборки frontend выполните из `frontend`:

```powershell
$env:F2R_TEST_DATABASE_URL = 'postgresql+psycopg://f2r_test@127.0.0.1:55433/feedback2req_i1_test'
$env:F2R_BROWSER_CHANNEL = 'msedge' # установленный Edge; либо установите Chromium: npx playwright install chromium
npm.cmd run test:e2e # браузер → Vite proxy → настоящий API
$env:F2R_E2E_MODE = 'built'
npm.cmd run test:e2e # браузер → сборка, раздаваемая API
Remove-Item Env:F2R_E2E_MODE
```

Тестовый API автоматически запускается на 18000, Vite — на 5173; порты
должны быть свободны. Если используется Chromium, уберите F2R_BROWSER_CHANNEL.
Тесты не запускают Docker сами. При принудительном завершении процесса
тестовая схема может сохраниться в отдельной тестовой БД. Трассы с паролями
и заголовками cookie не записываются; скриншоты содержат только тестовые данные.

## Проверка HTTP

Пример для PowerShell 7; пароль выберите локально, не используйте реальные
персональные данные в инженерной проверке:

```powershell
$base = 'http://localhost:8000/api/v1'
$headers = @{Origin='http://localhost:8000'}
$credentials = @{login='local-owner'; password=(Read-Host 'Тестовый пароль (12+ символов)')} | ConvertTo-Json
$user = Invoke-RestMethod "$base/auth/register" -Method Post -Headers $headers -ContentType application/json -Body $credentials
$login = Invoke-RestMethod "$base/auth/session" -Method Post -Headers $headers -ContentType application/json -Body $credentials -SessionVariable web
$headers['X-CSRF-Token'] = $login.csrf_token
$project = Invoke-RestMethod "$base/projects" -Method Post -Headers $headers -WebSession $web -ContentType application/json -Body '{"name":"Проект И1"}'
Invoke-RestMethod "$base/projects" -Headers $headers -WebSession $web
Invoke-RestMethod "$base/projects/$($project.id)" -Method Patch -Headers $headers -WebSession $web -ContentType application/json -Body '{"name":"Новое название"}'
```

Другой пользователь регистрируется/входит с отдельной web-сессией и сообщает
свой `id` из регистрации или GET `/auth/session`. Owner вызывает
PUT `/projects/{project_id}/access/{user_id}` с `{"can_approve":false}`;
тот же PUT с true назначает Approver, с false отзывает только Approver.
DELETE того же URL удаляет членство. Owner не может изменить свои права
этими командами. Logout: DELETE `/auth/session` с текущими Origin/CSRF/cookie.
Полный [контракт И1/И2а и ошибки](docs/API.md).

И2а: с теми же `$headers` и `$web` создайте фиктивные материалы:

```powershell
$text = "  Фиктивный отзыв ё Е$([char]0x0308) 🙂`tстрока`r`nCRLF`nLF  "
$sourceBody = [Text.Encoding]::UTF8.GetBytes((@{kind='text'; text=$text} | ConvertTo-Json -Compress))
$source = Invoke-RestMethod "$base/projects/$($project.id)/sources" -Method Post -Headers $headers -WebSession $web -ContentType 'application/json; charset=utf-8' -Body $sourceBody
$documentBody = [Text.Encoding]::UTF8.GetBytes((@{title='Фиктивный контекст'; text=$text} | ConvertTo-Json -Compress))
$document = Invoke-RestMethod "$base/projects/$($project.id)/documents" -Method Post -Headers $headers -WebSession $web -ContentType 'application/json; charset=utf-8' -Body $documentBody
Invoke-RestMethod "$base/projects/$($project.id)/sources/$($source.id)" -WebSession $web
Invoke-RestMethod "$base/projects/$($project.id)/documents/$($document.id)" -WebSession $web
Invoke-RestMethod "$base/projects/$($project.id)/sources" -WebSession $web
Invoke-RestMethod "$base/projects/$($project.id)/documents" -WebSession $web
```

Member также может выполнять эти операции. Списки имеют `{items,next_cursor}`,
продолжение — `?cursor=<next_cursor>`. Создание возвращает устойчивые id/state_id
и точный text; обработка не запускается. Слишком большой текст/body → 413,
пустой/пробельный/неподдержанный PostgreSQL ввод → 422; текст не обрезается
и не нормализуется. Сохранение файла, редактирование и удаление не реализованы.

## Тесты с изолированной PostgreSQL

Не используйте пользовательскую БД. Compose для тестов — отдельный проект,
порт 55433, собственный постоянный volume. Trust-auth допустима только для
этой локальной тестовой БД на loopback, не для приложения.

```powershell
docker compose -f compose.test.yaml up -d --wait db
$env:F2R_TEST_DATABASE_URL = 'postgresql+psycopg://f2r_test@127.0.0.1:55433/feedback2req_i1_test'
.\.venv\Scripts\python.exe -m pytest backend/tests -q -W error
.\.venv\Scripts\python.exe scripts/check_i1_restart.py
.\.venv\Scripts\python.exe -m ruff check backend scripts/check_i1_restart.py
.\.venv\Scripts\python.exe scripts/validate_ai_contracts.py
docker compose -f compose.test.yaml stop db
```

pytest требует явную F2R_TEST_DATABASE_URL с `test` в имени БД, создаёт
уникальную схему на каждый тест, применяет Alembic к пустой схеме, удаляет
только собственную схему. Отдельный тест также создаёт новую пустую БД с
уникальным префиксом f2r_test_, применяет m01 → m02a и удаляет только эту БД;
тестовой роли нужны CREATE SCHEMA и CREATEDB (Compose/CI это предоставляют).
SQLite не используется. Скрипт restart разрешает
только loopback-БД `feedback2req_i1_test` и перезапускает только тестовый db
из compose.test.yaml; API запускает отдельным временным процессом.
Два stop/start цикла проверяют сохранение сессий/прав И1 и обоих материалов
И2а с тем же текстом, id/state_id, включая Unicode/LF/CRLF.
Не запускайте restart параллельно другим тестам.

Для установленной PostgreSQL вместо Docker: initdb в `.local/i1-postgres`,
сервер только `127.0.0.1` на отдельном свободном порту, новая БД
`feedback2req_i1_test`, URL этой БД в F2R_TEST_DATABASE_URL. Запустите pytest,
затем `python scripts/check_i1_restart.py --pg-ctl 'ПУТЬ/К/pg_ctl.exe'`.
Native-режим управляет только `.local/i1-postgres`, не системной службой.
Каталог и конфигурация тестового кластера игнорируются Git.

GitHub Actions: [.github/workflows/i1.yml](.github/workflows/i1.yml) запускает
pytest на PostgreSQL 17, Ruff, исходный валидатор AI-контрактов и полный restart.
Для restart используется отдельный Compose-проект
`feedback2req-ci-<run_id>-<run_attempt>`, БД на 55433 и свой volume; pytest-БД
сервиса GitHub на 5432 не останавливается. `F2R_TEST_COMPOSE_PROJECT` позволяет
скрипту выбрать только это безопасное имя или feedback2req-i1-test.
TestClient использует совместимый httpx2 вместо deprecated-интеграции с httpx;
версии включены в requirements-test.lock, предупреждения не подавляются.
Границы покрытия и фактические результаты: [TESTING.md](docs/TESTING.md).
