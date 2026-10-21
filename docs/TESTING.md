# Testing

Статус: проверки И1/И2а разрешены DEC-007/DEC-008 от 2026-10-21; автономная валидация
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

Текущий изменённый workflow добавлен, но на GitHub не запускался: push запрещён
запросом. Подтверждённый CI выше относится только к И1. Локальные результаты
И2а и фактический stop/start записываются в [плане И2а](plans/i2a-materials.md).

Локальный результат И2а от 2026-10-21: **51 passed с -W error, без предупреждений**,
PostgreSQL 17.11 в тестовом Compose, Python 3.12/Windows. Реально выполнены
два stop/start цикла Uvicorn и тестовой PostgreSQL (Compose-ветка скрипта) с
сохранением точного текста/id/state_id обоих материалов и проверкой отзыва прав.
Обновлён контейнерный API отдельного проверочного проекта m01 → m02a;
create/list/read обоих видов материалов через контейнерный HTTP — PASS.
Ruff check/format, pip check, AI-валидатор и git diff --check прошли.
Независимого ревью нет; новый запуск GitHub Actions остаётся неподтверждённым.

## Разрешённая проверка контрактных артефактов

DEC-005 разрешает JSON Schema, демонстрационные запросы/ответы и автономные
проверки их корректности. Основная спецификация, команды и границы проверок —
[AI_CONTRACTS.md](AI_CONTRACTS.md). Python/jsonschema — инструменты этой
проверки; стек приложения позднее выбран DEC-006. DEC-005 сам по себе не
разрешал backend/frontend; тесты backend И1 разрешены последующим DEC-007.
Действующий автономный набор проверяет диалект,
ссылки, позитивные/негативные примеры, закрытость объектов и выбранные свойства
локальных пар; не заявляет проверку БД, прав, живых состояний или качества AI.
