# Testing

Статус: проверки И1/И2а/Ф1а/Ф1б разрешены DEC-007–DEC-010 от 2026-10-21; автономная валидация
AI-контрактов — DEC-005. Остальная стратегия приложения остаётся незавершённой.
DEC-011 от 2026-10-23 разрешает проверки инфраструктуры этапа 1; И2б и его
исполняемые проверки не реализуются до согласования спецификации.
Исходные критерии среза: [FIRST_TEXT_SLICE.md](FIRST_TEXT_SLICE.md), ревизия 1.

## Testing strategy

Cover approved functionality and applicable acceptance criteria with meaningful
checks. Choose the order of test writing, implementation, and debugging within
the authorized scope; tests need not invariably precede implementation.
Separate defects from design-change proposals; follow
[AGENTS.md](../AGENTS.md) when an approved artifact is insufficient.
И1/И2а используют pytest, FastAPI TestClient с httpx2, отдельные процессы Python/Uvicorn,
настоящую PostgreSQL 17 и Alembic. Версии зафиксированы в
backend/requirements-test.lock. Никаких SQLite или подмены проектных прав.
Переход TestClient на httpx2 соответствует
[документации Starlette](https://www.starlette.io/testclient/); предупреждение
устраняется установкой совместимого инструмента, без фильтра warnings.

## Test levels

API-тесты проходят через HTTP-обработчики, прикладные сервисы и реальную БД.
На каждый тест создаётся уникальная пустая PostgreSQL-схема в явно заданной
тестовой БД, к ней применяются m01 → m02a. Отдельно создаётся новая пустая БД и
проверяется upgrade head в public, а также обновление populated m01 с точным
сохранением пользователей/сессий/проектов/access. Проверяются UNIQUE/FK/CHECK и повторный
upgrade head без потери записей. Проверка нового Python-процесса отдельно
от проверки полного stop/start БД. Настоящий restart выполняет
scripts/check_i1_restart.py на отдельной БД, никогда на пользовательской.

## Mapping tests to requirements

До реализации зафиксировано [FR → AC → сценарий → тест](plans/i1-backend.md).
И1 покрывает FR-001/FR-003/FR-032 и часть AC-01 регистрации/проектов/прав.
И2а добавляет FR-002/FR-003/FR-032 → часть AC-01 материалов и сохранение текста
для FR-004; соответствие до реализации — [план И2а](plans/i2a-materials.md).
Обработка, межпроектный контекст AI, решения Approver, остальной AC-01 и
AC-02 целиком не реализованы. Для AI остаётся [AI_VALIDATION.md](AI_VALIDATION.md).

## Execution commands once known

Точные команды, конфигурация и изоляция: [README](../README.md#тесты-с-изолированной-postgresql).
Из корня, после установки backend и requirements-test.lock:

```text
python -m pytest backend/tests -q -W error
python scripts/check_i1_restart.py
python -m ruff check backend scripts/check_i1_restart.py
python scripts/validate_ai_contracts.py
```

Первые две команды требуют F2R_TEST_DATABASE_URL; restart — запущенную БД из
compose.test.yaml либо --pg-ctl для выделенного .local/i1-postgres.
При отсутствии URL pytest завершается ошибкой, не сообщает фиктивный PASS.
CI: [.github/workflows/i1.yml](../.github/workflows/i1.yml), PostgreSQL 17,
миграции/API/ограничения, Ruff, исходный валидатор AI. Новый шаг полного stop/start
использует отдельный проект feedback2req-ci-<run_id>-<run_attempt> и volume
compose.test.yaml на порту 55433, независимо от pytest-сервиса БД на 5432.
API — отдельный процесс Uvicorn. Проверяются И1, текст/id/state_id И2а и отзыв
доступа после restart. Проект/host/порт/роль/имя БД ограничены restart-скриптом;
test_restart_safety.py проверяет отказ до обращения к БД/процессам.
Тестовой роли нужны
CREATE SCHEMA и CREATEDB; права пользовательской БД для этого не используются.

## Test-change policy

Never weaken or remove a valid failing test without an approved requirement/design
change. Never change production behavior merely to make a test pass. Report
suspected incorrect tests with evidence rather than silently rewriting expectations.
Obtain approval before changing controlled requirements or design. Within an
approved change, keep documentation, tests, and implementation consistent without
a mandatory docs → tests → implementation sequence. Report failures and checks not run.

## Definition of done

Applicable approvals are recorded; documentation, tests, and code agree; relevant
checks are run and results reported. Use independent review for substantial changes
when available and disclose review limitations. Failures,
unresolved errors, uncertainty, and unavailable checks/review must be disclosed,
not represented as passing or complete validation.
Для И1: рабочие регистрация/сессия/проекты/access, защиты и M01, успешные
проверки PostgreSQL и перезапуска с тем же хранилищем. Ограничения проверки
развёртывания и независимого ревью указываются отдельно.

## Результаты И1 от 2026-10-21

21 pytest-тест прошёл на настоящей PostgreSQL 17.0 (Python 3.12/Windows).
Ruff check/format, pip check, git diff --check и исходный AI-валидатор прошли.
Фактически выполнены два stop/start Uvicorn и native PostgreSQL с прежним
каталогом; отдельно собран Docker-образ, применена M01 и проверен HTTP-сценарий
с restart контейнеров API/PostgreSQL и сохранением постоянного volume.
Проверены сохранение сессии/проекта/Approver, отзыв доступа и logout.

На этапе И1 было одно предупреждение Starlette/httpx; И2а заменяет его
совместимой интеграцией TestClient/httpx2 без подавления. Полный pytest И1
выполнялся локально на native PostgreSQL, Docker — отдельный HTTP smoke.
Независимого ревью нет. Позднее подтверждён успешный GitHub Actions
[run 39574175588](https://github.com/aarakova/feedback2req/actions/runs/39574175588),
коммит c20f6e51c687f0dac792148320873bac3f6fc14d, event push, job i1 success
(pytest/Ruff/AI-валидатор). В этом запуске полного restart ещё не было.
Детали, исходные сбои окружения и границы
готовности — в [плане И1](plans/i1-backend.md#фактическая-валидация).

## Валидация И2а

Проверяются сохранение/чтение обоих материалов Owner/Member, изоляция и отзыв
членства, в том числе реальная гонка под Project FOR UPDATE, Origin/CSRF,
Unicode/emoji/комбинируемые символы/пробелы/табуляции/LF/CRLF, пагинация,
неподдержанный kind/неизвестные поля, ограничения FK/NOT NULL/UNIQUE/CHECK,
отложенная ссылка current_state именно на свой материал/проект, ошибка вставки
state после header с откатом обеих записей. Файловых копий/обработки нет.

CI И2а подтверждён чтением GitHub API 2026-10-21:
[run 39587510535](https://github.com/aarakova/feedback2req/actions/runs/39587510535),
SHA `746c0f4c229fb2f22951d8898defb9deabc41ce3`, event push, job `i1` success.
Успешны pytest, Ruff, AI-валидатор и полный stop/start API/PostgreSQL
с сохранением материалов. Это отдельный запуск обновлённого workflow;
исторический run И1 выше его не заменяет. Локальные результаты
И2а записаны в [плане И2а](plans/i2a-materials.md).

Локальный результат И2а от 2026-10-21: **51 passed с -W error, без предупреждений**,
PostgreSQL 17.11 в тестовом Compose, Python 3.12/Windows. Реально выполнены
два stop/start цикла Uvicorn и тестовой PostgreSQL (Compose-ветка скрипта) с
сохранением точного текста/id/state_id обоих материалов и проверкой отзыва прав.
Обновлён контейнерный API отдельного проверочного проекта m01 → m02a;
create/list/read обоих видов материалов через контейнерный HTTP — PASS.
Ruff check/format, pip check, AI-валидатор и git diff --check прошли.
Независимого ревью нет; успешный GitHub Actions И2а подтверждён выше.

## Валидация Ф1а

Браузерные сценарии: `frontend/tests/workspace.spec.ts`, Playwright и
настоящий API с отдельной PostgreSQL; тестовый сервер запускается скриптом
`scripts/serve_frontend_test.py` в уникальной схеме, page_size=2. Настройка и
команды — в [README](../README.md). Прогон API-only тестов
по-прежнему требует отдельной тестовой PostgreSQL. Тест раздачи статики
дополнительно проверяет no-store, сохранение защиты API и недоступность путей
вне публичной сборки.

Фактически выполнено 2026-10-21, Windows/Python 3.12/Node 24, PostgreSQL 17
в тестовом Compose:

- `pytest backend/tests -q -W error`: **52 passed**, без предупреждений.
- TypeScript/Vite build: PASS; Ruff check/format, pip check, git diff --check: PASS.
- Playwright в установленном Edge: **7 passed** через Vite proxy,
  **7 passed** на сборке, раздаваемой FastAPI. Регистрация без автоматического
  входа, вход, создание/список/открытие проекта, reload, cookie/Origin/CSRF,
  пагинация, Owner/Member/Approver из API, отзыв доступа, 401, ошибки входа,
  повтор после сбоя сети, неуспешный logout и запоздалый ответ после выхода.
- Скриншоты проекта 1280×720 и 390×844 просмотрены; на узком экране
  горизонтальное переполнение отсутствует. Это не полный аудит доступности.
- Собран Docker-образ `feedback2req-f1a-test`; временный контейнер:
  index/JS asset 200, no-store, анонимная сессия 401 — PASS; контейнер остановлен.

Первые проверки выявили перекрытие тестовых маршрутов корневым static mount;
реализация исправлена на отдельные `/` и `/assets`, исходные тесты сохранены.
Проверка Origin в Playwright исправлена на `allHeaders()`. Первый sandbox-прогон
завис при завершении дочерних процессов Windows; остановлены только его
подтверждённые процессы. В следующем прогоне перестал отвечать Vite (две ошибки
ECONNRESET/connection refused); причина одиночной остановки не установлена.
Повторный полный dev-прогон и отдельный built-прогон прошли без ошибок.
Playwright выдаёт предупреждение о NO_COLOR/FORCE_COLOR окружения; оно не
подавлялось и не относится к backend pytest.

Независимого ревью не было. Firefox/Safari и полный контейнерный браузерный
сценарий не проверялись; в контейнере выполнена только HTTP-проверка статики и
анонимного API. При принудительной остановке Windows тестовые схемы могут
сохраняться в выделенной тестовой БД. CI Ф1а не запускался: commit/push
не разрешены; подтверждённый CI И2а выше не выдаётся за CI frontend.
Детали — в [плане Ф1а](plans/f1a-frontend.md).

## Валидация Ф1б

`frontend/tests/materials.spec.ts` проверяет реальные API И2а и отдельную
тестовую PostgreSQL вместе с регрессиями `workspace.spec.ts`. Общие помощники
регистрации/настройки вынесены в `tests/helpers.ts`; ожидаемое поведение Ф1а
сохранено. Page size тестового сервера равен 2, что позволяет проверить
независимую пагинацию списков и чтение материала вне первой страницы.

Проверяются оба вида материалов Owner/Member/Approver, запрет постороннему,
отзыв доступа, 401 и очистка данных, reload выбранного раздела/материала,
безопасный текстовый вывод, независимые ошибки списков, ошибки 413/422 и
сохранность черновика, отправка без повторного нажатия, поздние ответы при
выходе/смене проекта. Отдельная проверка повторного входа и смены пользователя
после переоценки сессии не позволяет вернуть прежний проектный интерфейс.
При подтверждённой действующей сессии/доступе черновик после ошибки остаётся;
до проверки доступа проект скрыт.

Кириллица/emoji/комбинируемые символы/пробелы/табуляция/переводы строк сравниваются
с фактическим JSON POST и GET. Тест textarea явно проверяет преобразование CRLF
в LF браузером до отправки; отдельный материал с CRLF создан прямым API-вводом.
Не заявляется сохранение исходного CRLF ручного ввода. Перехват сети используется
только для задержек/обрывов/500; положительные сценарии работают с настоящими
API/БД. Тест потерянного POST сначала действительно сохраняет материал на сервере,
затем обрывает ответ и проверяет отсутствие фиктивного успеха/автоповтора.

Текущий GitHub backend workflow проверен чтением API и steps:
[run 39591705278](https://github.com/aarakova/feedback2req/actions/runs/39591705278),
SHA `a4cd0e4b9da43c7a4289bf1d0eadd1658e4176c1`, job i1 success.
В нём нет Node/frontend build/Playwright: он не подтверждает frontend Ф1а/Ф1б.
Отправка изменений и новые запуски GitHub в Ф1б не выполняются.

Итог от 2026-10-21: TypeScript/Vite build — PASS; Playwright/Edge —
**18 passed через Vite proxy, 18 passed на сборке FastAPI** (11 Ф1б + 7 Ф1а),
настоящая PostgreSQL 17. Применимые backend-регрессии материалов/раздачи
frontend: **19 passed с -W error, без предупреждений**. Полный backend suite
в Ф1б повторно не запускался. Desktop/mobile скриншоты форм, списков и длинного
текста просмотрены; на 390 px переполнения нет. Git diff --check — PASS.

Начальные ошибки label textarea/неоднозначного status/ожидания пагинации
исправлены. Повторные обрывы dev-сервера расследованы: в Vite есть завершение
при закрытии stdin, для тестового webServer задан CI=true. После настройки
полные dev-прогоны проходят; событие stdin конкретного обрыва не трассировалось.
Один ранний worker Windows аварийно завершился, причина не установлена;
итоговые прогоны проходят без аварии. Предупреждение NO_COLOR/FORCE_COLOR
Playwright остаётся. Независимого ревью, Firefox/Safari и контейнерного
браузерного прогона не было. Подробности и ограничения —
в [плане этапа](plans/f1b-materials-ui.md).

## Инфраструктура DEC-011 — результаты 2026-10-23

Существующий тест раздачи обновлён по утверждённому изменению: FastAPI не
публикует локальную сборку, API/Origin/private-path проверки сохраняются.
Добавлены test_runtime.py и scripts/check_infrastructure.py; тестовый overlay
compose.infrastructure-test.yaml использует отдельные проект/БД/volume/сеть.
Рабочая БД для регистрации тестовых пользователей не используется.

Фактически выполнено в Docker Desktop/Linux containers на Windows:

- Независимые Python backend/worker и React/TypeScript/Vite/Nginx образы:
  сборка PASS. Node/React исключены из backend Dockerfile; frontend runtime
  содержит только публичную сборку и Nginx, секреты в сборку не передаются.
- Полный backend: **60 passed с -W error**, Python 3.12, настоящая PostgreSQL 17.
  Включены empty/populated m01→m02a, сохранение сессии/проекта/текста,
  два одновременно ожидающих мигратора, проверка блокировки во время DDL,
  освобождение после commit/rollback, откат DDL/версии при ошибке, запрет
  старта Uvicorn после ошибки, отказ worker-check на старой схеме без DDL,
  безопасный вывод ошибочной конфигурации. Прежний полный набор сохранён.
- Реальный Nginx HTTP: регистрация/вход/cookie/CSRF/Origin, проекты, оба материала,
  чужой проект, Unicode/LF/CRLF, JSON 413 и API 404 — PASS. Некорректный traversal
  над корнем Nginx отклоняет 400; первоначальное ожидание 404 в новом тестовом
  скрипте исправлено как неверное. Приватные существующие пути не публикуются.
- Реальный restart тестовых PostgreSQL/backend и сохранение прежней cookie,
  text/id/state_id — PASS. Смена IP backend с .3 на .5 без restart Nginx и
  повторное чтение сохранённых данных через Docker DNS — PASS.
- Подделка X-Forwarded-For/Proto, Forwarded и X-Real-IP: прямой недоверенный peer
  и тот же клиент через Nginx используют один IP bucket; третий запрос при
  limit=2 даёт 429 — PASS. Отдельные ASGI-тесты проверяют, что только точный
  доверенный адрес может задавать разные IP; wildcard-доверия нет.
- Chromium/Playwright 1.64.1: **18 passed через Nginx**, **18 passed через Vite**,
  включая все Ф1а/Ф1б. Контейнерному браузеру test-only TCP relay предоставляет
  localhost:18080 с неизменными байтами HTTP к настоящему Nginx; ответы API не
  имитируются. Vite проверен с отдельным настоящим API/тестовой схемой.
  Дополнительно **1 passed**: регистрация/сессия/проект/reload/logout по пути
  Vite → Nginx → backend после изменения только разрешённого Origin, без сборки.
- Ruff для backend и изменённых Python-скриптов — PASS; автономный AI-валидатор
  — PASS (9 схем, 38 positive/34 negative примера, 399 mutations, 20 fixture pairs).
  Ошибки первого lint-вызова включали неверный cwd и лишнюю область legacy-скриптов;
  проверка повторена в корректном backend-каталоге, без изменения старых ожиданий.
- Рабочий стек запущен `docker compose up -d --build`; frontend на localhost:8000,
  backend/db healthy. Worker-check завершается 0 — это подготовка, не очередь.
  До/после переключения сохранены m02a, по одной записи users/sessions/projects/
  feedback_sources/product_documents и время создания прежнего volume
  feedback2req_postgres_data. Рабочие материалы не изменялись тестовыми POST.

Первый запуск тестовой proxy-сети обнаружил занятие адреса Nginx динамическим
backend; адрес backend закреплён отдельно и повторный запуск прошёл.
Healthcheck проверяет HTTP+БД+head, но не является гарантией доступности после
будущего сбоя. Полный `up -d` не равнозначен успешному healthcheck.

Прежнее native Python-окружение ссылается на отсутствующую установку, Node нет
в PATH: проверки выполнены контейнерными инструментами, native запуск не
проверен. Firefox/Safari, TLS/LAN, будущая серверная инфраструктура и AI-качество
не проверялись. Независимого ревью не было. Job deployment добавлен в GitHub
workflow, но новый удалённый CI не запускался и не объявляется прошедшим.
Исторические результаты Ф1а/Ф1б выше описывают прежнюю раздачу FastAPI;
текущая проверка готовой сборки — только через Nginx. Очередь/lease И2б здесь
не проверялись: их код и миграции отсутствуют.

## Управление участниками — DEC-012, 2026-10-23

Добавлены 22 сценария в `frontend/tests/access.spec.ts`; 18 существующих
сценариев workspace/materials сохранены. Используются реальные API/PostgreSQL,
отдельная БД feedback2req_access_test в собственном контейнере и уникальные
схемы через существующий isolated_database; размер страницы 2.

Покрытие: Owner-only маршрут, собственный UUID/реальный Clipboard API и отказ
копирования, пагинация/reload/Back/Forward, отсутствие изменения владельца,
добавление без Approver и с ним, известный UUID за пределами первой страницы
без неявного PUT, назначение/отзыв Approver с проверкой независимой сессией,
подтверждение/отмена/повторное удаление, реальные 403 Member/Approver и 404
постороннему. Проверяются конкурентные изменения другой сессией владельца,
изменение прав и отзыв членства при возврате фокуса в отдельном браузерном
контексте, 401/CSRF, ошибки загрузки/повтор, удержание ввода и защита от
двойной отправки, поздние ответы после смены проекта/пользователя/logout.

Потерянные PUT/DELETE проходят через настоящий API (route.fetch), после чего
ответ обрывается. Проверяются отсутствие автоповтора и ложного успеха,
сверка через страницы, сохранение неопределённости при focus во время
отправленной записи. Ошибка чтения после подтверждённой записи показывается
отдельно. Синтетические 500/CSRF/Owner-only 403 используются только для
клиентской обработки ошибок; они не заменяют серверные проверки авторизации.

Фактические результаты в Docker Desktop/Linux containers на Windows:

- TypeScript/Vite build и отдельный frontend Docker build — PASS.
- Chromium/Playwright: **40 passed через Vite** и **40 passed через Nginx**,
  включая 22 новых сценария и все 18 регрессий. Nginx проверен существующим
  test-only TCP relay с неизменными HTTP/Origin; ответы API не подменяются.
- `pytest backend/tests/test_projects.py backend/tests/test_security.py
  -q -W error`: **11 passed**, без предупреждений, на собственной PostgreSQL 17.
- Просмотрены desktop/mobile скриншоты, keyboard/input focus проверен,
  горизонтального переполнения на 390 px нет. git diff --check — PASS.

Первоначальный новый прогон: 15 passed / 1 failed — подготовка пагинации могла
закончиться до начальной загрузки списка. Исправлены начальный busy и ожидание
списка в setup; целевой повтор и оба итоговых полных прогона прошли.
Полный backend suite, restart, Firefox/Safari, native Node/Python, TLS и
удалённый CI в этом этапе не запускались; независимого ревью не было.
Общие Docker image tags и окружения других агентов не менялись; рабочая БД
не использовалась. Существующие DEC и поведение backend не изменены.

Реальные ограничения: каталог пользователей отсутствует; чтение перед PUT
не исключает последующую гонку без условной записи на сервере. Результат
сверки отражает текущее состояние, но не доказывает результат прошлого запроса.

## Единая проектная рабочая область — DEC-013

Добавлены 8 browser-сценариев в `frontend/tests/project-layout.spec.ts`.
Проверяются два уровня приложения, открытие проектов из списка и возврат,
переход между разными проектами, шесть разделов Owner/пять Member,
aria-current, reload, прямой маршрут материала и существующий access,
некорректные/неизвестные маршруты, поздний ответ прежнего проекта,
ошибка чтения проекта с рабочим возвратом и отзыв членства на информационном
экране. Обзор не запрашивает списки для счётчиков, неподключённые разделы
не обращаются к вымышленным API и не содержат фиктивных операций/метрик.

Фактически выполнено 2026-10-23 в собственном Docker-окружении:

- TypeScript/Vite build и production frontend Docker build — PASS.
- Chromium/Playwright: **48 passed через Vite**, **48 passed через Nginx**,
  настоящий backend/PostgreSQL 17, отдельная feedback2req_layout_test,
  уникальные схемы и page_size=2. Используется существующий TCP relay
  с неизменными HTTP/Origin; API-ответы не имитируются для успешных сценариев.
- Все 40 прежних тестов workspace/materials/access сохранены без правок,
  включая неопределённые записи, сессии, CSRF, реальные права и поздние ответы.
- Desktop 1280×720 и mobile 390×844/320×844: скриншоты просмотрены;
  клавиатура/видимый focus/skip-link/aria-current и отсутствие горизонтального
  переполнения проверены. git diff --check — PASS.

Оба полных browser-прогона прошли с первого запуска. Новые проверки используют
реальные API/PostgreSQL; обрыв/задержка транспорта моделируются отдельно.
Собственная сеть/контейнеры/тег f2r-layout-adf660ee не меняют общий Compose,
рабочую БД, порты и image tags других агентов. Backend, его контракты и код
материалов/доступа не изменены. Полный backend suite/restart, Firefox/Safari,
TLS и удалённый CI не запускались. Native Node/Python и независимое ревью
не выполнялись. Подробности и следующие итерации: [план](plans/project-workspace.md).

## Разрешённая проверка контрактных артефактов

DEC-005 разрешает JSON Schema, демонстрационные запросы/ответы и автономные
проверки их корректности. Основная спецификация, команды и границы проверок —
[AI_CONTRACTS.md](AI_CONTRACTS.md). Python/jsonschema — инструменты этой
проверки; стек приложения позднее выбран DEC-006. DEC-005 сам по себе не
разрешал backend/frontend; тесты backend И1 разрешены последующим DEC-007.
Действующий автономный набор проверяет диалект,
ссылки, позитивные/негативные примеры, закрытость объектов и выбранные свойства
локальных пар; не заявляет проверку БД, прав, живых состояний или качества AI.
