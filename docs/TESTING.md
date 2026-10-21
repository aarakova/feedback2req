# Testing

Статус: проверки И1/И2а/Ф1а разрешены DEC-007/DEC-008/DEC-009 от 2026-10-21; автономная валидация
AI-контрактов — DEC-005. Остальная стратегия приложения остаётся незавершённой.
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
команды — в [README](../README.md#frontend-ф1а). Прогон API-only тестов
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

## Разрешённая проверка контрактных артефактов

DEC-005 разрешает JSON Schema, демонстрационные запросы/ответы и автономные
проверки их корректности. Основная спецификация, команды и границы проверок —
[AI_CONTRACTS.md](AI_CONTRACTS.md). Python/jsonschema — инструменты этой
проверки; стек приложения позднее выбран DEC-006. DEC-005 сам по себе не
разрешал backend/frontend; тесты backend И1 разрешены последующим DEC-007.
Действующий автономный набор проверяет диалект,
ссылки, позитивные/негативные примеры, закрытость объектов и выбранные свойства
локальных пар; не заявляет проверку БД, прав, живых состояний или качества AI.
