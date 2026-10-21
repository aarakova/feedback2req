# Testing

Статус: проверки И1 разрешены DEC-007 от 2026-10-21; автономная валидация
AI-контрактов — DEC-005. Остальная стратегия приложения остаётся незавершённой.
Исходные критерии среза: [FIRST_TEXT_SLICE.md](FIRST_TEXT_SLICE.md), ревизия 1.

## Testing strategy

Cover approved functionality and applicable acceptance criteria with meaningful
checks. Choose the order of test writing, implementation, and debugging within
the authorized scope; tests need not invariably precede implementation.
Separate defects from design-change proposals; follow
[AGENTS.md](../AGENTS.md) when an approved artifact is insufficient.
И1 использует pytest, FastAPI TestClient, отдельные процессы Python/Uvicorn,
настоящую PostgreSQL 17 и Alembic. Версии зафиксированы в
backend/requirements-test.lock. Никаких SQLite или подмены проектных прав.

## Test levels

API-тесты проходят через HTTP-обработчики, прикладные сервисы и реальную БД.
На каждый тест создаётся уникальная пустая PostgreSQL-схема в явно заданной
тестовой БД, к ней применяется M01. Отдельно создаётся новая пустая БД и
проверяется upgrade head в public. Проверяются UNIQUE/FK/CHECK и повторный
upgrade head без потери записей. Проверка нового Python-процесса отдельно
от проверки полного stop/start БД. Настоящий restart выполняет
scripts/check_i1_restart.py на отдельной БД, никогда на пользовательской.

## Mapping tests to requirements

До реализации зафиксировано [FR → AC → сценарий → тест](plans/i1-backend.md).
FR-001/FR-003/FR-032 и AC-01 покрыты только в части регистрации, проектов и прав.
Материалы, обработка, межпроектный контекст AI, решения Approver и остальной
AC-01 не реализованы и не покрыты И1. Для AI остаётся [AI_VALIDATION.md](AI_VALIDATION.md).

## Execution commands once known

Точные команды, конфигурация и изоляция: [README](../README.md#тесты-с-изолированной-postgresql).
Из корня, после установки backend и requirements-test.lock:

```text
python -m pytest backend/tests -q
python scripts/check_i1_restart.py
python -m ruff check backend scripts/check_i1_restart.py
python scripts/validate_ai_contracts.py
```

Первые две команды требуют F2R_TEST_DATABASE_URL; restart — запущенную БД из
compose.test.yaml либо --pg-ctl для выделенного .local/i1-postgres.
При отсутствии URL pytest завершается ошибкой, не сообщает фиктивный PASS.
CI: [.github/workflows/i1.yml](../.github/workflows/i1.yml), PostgreSQL 17,
миграции/API/ограничения, Ruff, исходный валидатор AI. Полный stop/start
контейнера выполняется отдельным локальным скриптом. Тестовой роли нужны
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

Остаётся одно предупреждение Starlette о deprecated-интеграции с httpx;
его не подавляли. Полный pytest выполнялся на native PostgreSQL, Docker —
отдельный HTTP smoke. Независимое ревью и workflow на GitHub не запускались.
Default Compose-ветка restart-скрипта отдельно не проверена; native-ветка
и прямой Compose restart проверены. Детали, исходные сбои окружения и границы
готовности — в [плане И1](plans/i1-backend.md#фактическая-валидация).

## Разрешённая проверка контрактных артефактов

DEC-005 разрешает JSON Schema, демонстрационные запросы/ответы и автономные
проверки их корректности. Основная спецификация, команды и границы проверок —
[AI_CONTRACTS.md](AI_CONTRACTS.md). Python/jsonschema — инструменты этой
проверки; стек приложения позднее выбран DEC-006. DEC-005 сам по себе не
разрешал backend/frontend; тесты backend И1 разрешены последующим DEC-007.
Действующий автономный набор проверяет диалект,
ссылки, позитивные/негативные примеры, закрытость объектов и выбранные свойства
локальных пар; не заявляет проверку БД, прав, живых состояний или качества AI.
