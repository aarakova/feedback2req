# feedback2req

И1/И2а: backend с PostgreSQL, локальными учётными записями, серверными сессиями,
проектами, управлением доступом и сохранением текстовых отзывов/документов.
Ф1а/Ф1б добавляют React frontend: регистрация, вход/выход, восстановление сессии,
проекты и полномочия, ввод/списки/просмотр текстовых отзывов и документов.
Основание: [DEC-007–DEC-011](docs/DECISIONS.md).
Nginx/frontend и Python/backend разделены. Сервис worker пока выполняет
конечную проверку инфраструктуры и завершается; очереди/обработки заданий нет.
Работающий worker требует отдельного утверждения [И2б](docs/I2B_SPEC.md).
AI-обработка отсутствует; HTML-прототип в `prototype/` остаётся
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
docker compose up -d --build
docker compose ps -a
```

Интерфейс: `http://localhost:8000/`, API: `http://localhost:8000/api/v1`.
Frontend отдельно собирается на Node 24 и раздаётся Nginx 1.28; backend —
Python/FastAPI/Uvicorn без Node/React. db — PostgreSQL 17; worker — общий
Python-образ с другой командой. На этапе 1 ожидаются три работающих сервиса
и worker `Exited (0)` с сообщением об ожидающем согласования И2б.
`up -d` не доказывает готовность: проверьте healthy в `ps -a`.

Backend автоматически применяет Alembic перед Uvicorn. Весь online Alembic
держит transaction advisory lock на том же соединении до commit DDL и версии.
Ошибка откатывает миграцию и запрещает старт backend. Worker не выполняет DDL.
Проверка версии: `docker compose run --rm --no-deps backend alembic current`
(ожидается `m02a`). Отдельная миграция:
`docker compose run --rm --no-deps backend python -m feedback2req.runtime migrate`.
Прямой `alembic upgrade head` защищён той же блокировкой; БД должна работать.
Это процедура текущего локального одиночного backend, не будущего сервера.
Несовместимые миграции нельзя запускать под старым worker/приложением.
Перезапуск с тем же volume: `docker compose restart db backend frontend`.
Остановка: `docker compose stop`. Постоянный `postgres_data` сохраняет БД.
Команд удаления volume для пользовательских данных инструкция не предусматривает.
Сохраняйте имя проекта `feedback2req`: другой `-p` выбирает другой volume.
Прежний остановленный api может остаться orphan; удалять его для перехода
не требуется. Не меняйте пароль существующей БД только в `.env`:
POSTGRES_PASSWORD инициализирует новую БД, но не меняет пароль существующей роли.

```powershell
docker compose up -d --no-deps --build frontend
docker compose up -d --no-deps --build backend
docker compose restart frontend
docker compose restart backend
docker compose logs --tail 100 frontend backend db worker
docker compose run --rm --no-deps worker
```

Последняя команда проверяет конфигурацию/БД/совместимость схемы и завершается;
это не проверка очереди. Диагностическая ошибка даёт ненулевой код без SQL/секрета.

Реальная работа в LAN требует TLS, `F2R_LOCAL_HTTP=false` и точный HTTPS
`F2R_ALLOWED_ORIGIN`; внешний TLS proxy/хостинг этим этапом не настраиваются.
Порты БД и backend наружу не публикуются; Nginx слушает loopback хоста.
Uvicorn доверяет только фиксированному IP Nginx; Nginx заменяет клиентские
forwarded-заголовки. Proxy-сеть: 172.28.243.0/28, Nginx .2, backend .3;
при конфликте меняйте согласованно F2R_PROXY_SUBNET/F2R_PROXY_IP/
F2R_BACKEND_PROXY_IP из `.env.example`. Docker DNS переопрашивается после
пересоздания backend. IP лимитера — адрес соединения, видимый Nginx;
Docker Desktop/NAT может свести несколько клиентов к одному адресу.

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

## Frontend Ф1а/Ф1б и участники

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
для Compose укажите их в `.env` и выполните `docker compose up -d backend`.
Vite обращается через localhost:8000 → Nginx → backend, без дополнительного
порта backend и без пересборки frontend-контейнера.
Не заменяйте localhost на 127.0.0.1 в адресе браузера: Origin должен совпадать
точно. При другом порте API задайте `F2R_API_PROXY_TARGET` перед Vite;
эта переменная нужна только серверу разработки, не попадает в клиентскую сборку.
Проверки Origin/CSRF и cookie backend сохраняются.

Для проверки независимой сборки выполните из `frontend`:

```powershell
npm.cmd run build
```

FastAPI больше не раздаёт сборку; F2R_FRONTEND_DIST удалён. Для готовой сборки
используйте frontend-контейнер. Для возврата из Vite в готовую сборку укажите
Origin http://localhost:8000 в `.env`, пересоздайте backend через
`docker compose up -d backend` и откройте этот адрес. Как и прежде, разрешён
один точный Origin.

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
Владелец проекта видит вкладку **Участники**. Список загружается страницами;
«Показать ещё» продолжает его, «Обновить участников» начинает заново.
Показываются UUID и реальные полномочия из API, без вымышленных имён и дат.
В блоке текущего пользователя раскройте **Мой ID** и нажмите **Копировать ID**:
успех отображается после записи в буфер. Если браузер запрещает копирование,
ID можно выделить вручную. Передайте свой ID владельцу нужного проекта.

«Добавить участника» открывает форму UUID и необязательного Approver.
Перед отправкой проверяются все необходимые страницы. Для существующего
участника добавление не выполняется: используйте отдельные действия
«Назначить Approver» / «Отозвать Approver». Удаление требует подтверждения;
оно прекращает членство, но сохраняет учётную запись. Доступ владельца
неизменяем; Member и Approver не видят административную вкладку.

При потере ответа PUT/DELETE результат неизвестен. Новые изменения блокируются
до команды **Проверить текущее состояние**, которая читает страницы до нужного
ID или конца списка. Автоматического повтора записи нет. Проверка показывает
текущее состояние, а не доказывает результат прошлого запроса. Ошибка обновления
списка после подтверждённой записи показывается отдельно от успеха операции.
При Owner-only 403 список скрывается и перепроверяется проект; такая ошибка
сама по себе не означает потерю членства. Права перепроверяются при возвращении
во вкладку. Сервер остаётся источником авторизации.

В API нет версий записей/условного PUT: изменение между предварительным
чтением и записью может заменить права или восстановить удалённое членство.
Форма заранее поясняет это ограничение; поиск по логину и передача владения
не реализованы. ID, черновики и результаты копирования не сохраняются
в localStorage/sessionStorage или журналах приложения.

Браузерные тесты используют отдельную PostgreSQL и уникальную тестовую схему,
не меняют рабочую БД. После установки Python backend и тестовых зависимостей,
запуска `compose.test.yaml` и сборки frontend выполните из `frontend`:

```powershell
$env:F2R_TEST_DATABASE_URL = 'postgresql+psycopg://f2r_test@127.0.0.1:55433/feedback2req_i1_test'
$env:F2R_BROWSER_CHANNEL = 'msedge' # установленный Edge; либо установите Chromium: npx playwright install chromium
npm.cmd run test:e2e # браузер → Vite proxy → настоящий API
$env:F2R_E2E_MODE = 'compose'
$env:F2R_E2E_BASE_URL = 'http://localhost:18080'
npm.cmd run test:e2e # браузер → тестовый Nginx → backend → PostgreSQL
Remove-Item Env:F2R_E2E_MODE
```

Для compose-режима сначала поднимите отдельный тестовый стек из раздела ниже.
Playwright не запускает свой API/Vite в этом режиме; built — прежний alias
compose-режима, раздачи FastAPI больше нет. В dev-режиме тестовый API
автоматически запускается на 18000, Vite — на 5173; порты
должны быть свободны. Если используется Chromium, уберите F2R_BROWSER_CHANNEL.
Тесты не запускают Docker сами. При принудительном завершении процесса
тестовая схема может сохраниться в отдельной тестовой БД. Трассы с паролями
и заголовками cookie не записываются; скриншоты содержат только тестовые данные.

## Изолированная проверка инфраструктуры DEC-011

Overlay нельзя применять к рабочему проекту. Он задаёт собственные проект,
volume, БД feedback2req_infra_test, порт 18080 и подсеть 172.28.244.0/28.
Пароль в overlay — публичный пароль только тестовой БД. Создайте `.local`
при отсутствии: там сохраняются только фиктивные сессия/материалы для restart.

```powershell
docker compose build backend frontend worker
docker compose -f compose.yaml -f compose.infrastructure-test.yaml up -d --no-build
docker compose -f compose.yaml -f compose.infrastructure-test.yaml ps -a
docker build -f backend/Dockerfile.checks -t feedback2req-checks .
docker run --rm --network feedback2req-infra-test_proxy --mount "type=bind,source=$PWD,target=/workspace" --mount "type=bind,source=$PWD/.local,target=/state" feedback2req-checks python scripts/check_infrastructure.py smoke
```

После restart тестовых db/backend дождитесь healthy и запустите `verify`
вместо `smoke`: проверяются прежняя сессия и точные text/id/state_id.
Для проверки DNS задайте F2R_TEST_BACKEND_PROXY_IP=172.28.244.5 и пересоздайте
только backend; после TTL `verify` должен пройти без restart frontend.
Для `rate` пересоздайте тестовый backend с F2R_TEST_LOGIN_LIMIT=2; проверяется
прямой недоверенный peer и подделка forwarded-заголовков через Nginx.
Перед браузерными тестами верните лимит 1000. Остановка тестового стека —
та же Compose-команда с `stop`; volume сохраняется.

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
DEC-011 добавляет job deployment: независимые образы, изолированный Nginx,
restart/смену IP/spoofing и браузерные сценарии через Nginx и Vite.
Изменение workflow само по себе не означает успешного GitHub-прогона.
Для restart используется отдельный Compose-проект
`feedback2req-ci-<run_id>-<run_attempt>`, БД на 55433 и свой volume; pytest-БД
сервиса GitHub на 5432 не останавливается. `F2R_TEST_COMPOSE_PROJECT` позволяет
скрипту выбрать только это безопасное имя или feedback2req-i1-test.
TestClient использует совместимый httpx2 вместо deprecated-интеграции с httpx;
версии включены в requirements-test.lock, предупреждения не подавляются.
Границы покрытия и фактические результаты: [TESTING.md](docs/TESTING.md).
