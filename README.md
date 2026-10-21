# feedback2req

И1: backend с PostgreSQL, локальными учётными записями, серверными сессиями,
проектами и управлением доступом. Основание: [DEC-007](docs/DECISIONS.md).
Frontend, worker, материалы и AI-обработка ещё отсутствуют; HTML-прототип
в `prototype/` остаётся референсом. Остальной [проект среза](docs/FIRST_TEXT_SLICE.md)
не утверждён этим решением.

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

API: `http://localhost:8000/api/v1`. Автомиграции при импорте/старте нет;
при развёртывании миграция выполняется отдельной командой до запуска API.
Проверка версии: `docker compose run --rm api alembic current` (ожидается `m01`).
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
`MAX_BODY_BYTES=16384`, `LOGIN_LIMIT=10`, `LOGIN_WINDOW_SECONDS=60`,
`PAGE_SIZE=50`. Лимитер register/login общий по IP в одном процессе;
он сбрасывается при restart. И1 запускается с одним процессом API.

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
Полный [контракт И1 и ошибки](docs/API.md).

## Тесты с изолированной PostgreSQL

Не используйте пользовательскую БД. Compose для тестов — отдельный проект,
порт 55433, собственный постоянный volume. Trust-auth допустима только для
этой локальной тестовой БД на loopback, не для приложения.

```powershell
docker compose -f compose.test.yaml up -d --wait db
$env:F2R_TEST_DATABASE_URL = 'postgresql+psycopg://f2r_test@127.0.0.1:55433/feedback2req_i1_test'
.\.venv\Scripts\python.exe -m pytest backend/tests -q
.\.venv\Scripts\python.exe scripts/check_i1_restart.py
.\.venv\Scripts\python.exe -m ruff check backend scripts/check_i1_restart.py
.\.venv\Scripts\python.exe scripts/validate_ai_contracts.py
docker compose -f compose.test.yaml stop db
```

pytest требует явную F2R_TEST_DATABASE_URL с `test` в имени БД, создаёт
уникальную схему на каждый тест, применяет Alembic к пустой схеме, удаляет
только собственную схему. Отдельный тест также создаёт новую пустую БД с
уникальным префиксом f2r_test_, применяет M01 и удаляет только эту БД;
тестовой роли нужны CREATE SCHEMA и CREATEDB (Compose/CI это предоставляют).
SQLite не используется. Скрипт restart разрешает
только loopback-БД `feedback2req_i1_test` и перезапускает только тестовый db
из compose.test.yaml; API запускает отдельным временным процессом.
Не запускайте restart параллельно другим тестам.

Для установленной PostgreSQL вместо Docker: initdb в `.local/i1-postgres`,
сервер только `127.0.0.1` на отдельном свободном порту, новая БД
`feedback2req_i1_test`, URL этой БД в F2R_TEST_DATABASE_URL. Запустите pytest,
затем `python scripts/check_i1_restart.py --pg-ctl 'ПУТЬ/К/pg_ctl.exe'`.
Native-режим управляет только `.local/i1-postgres`, не системной службой.
Каталог и конфигурация тестового кластера игнорируются Git.

GitHub Actions: [.github/workflows/i1.yml](.github/workflows/i1.yml) запускает
pytest на PostgreSQL 17, Ruff и исходный валидатор AI-контрактов. Настоящий
restart тестового контейнера воспроизводится отдельной локальной командой
выше. Границы покрытия и фактические результаты: [TESTING.md](docs/TESTING.md).
