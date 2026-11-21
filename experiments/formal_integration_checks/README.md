# Сохранённые F1/F2 данные → формальный bridge

Автономные интеграционные тесты, не product exporter/review API. Они создают
собственные синтетические источники через существующий API, выполняют F1 с
явным Synthetic provider, принимают F2, читают GET exact group/state и Finding
DTO и сравнивают их с оригинальным подготовленным canonical входом.
Backend/worker/схемы/AI JSON 1.0 не меняются. Внешняя модель не вызывается.

Тестовый куратор явно задаёт known local→persistent associations только для
контролируемой fixture; этот способ не доступен через CLI и не является
алгоритмом восстановления mapping из произвольных DTO. Без mapping audit
возвращает missing. Exact synthetic receipt в одном тесте относится только
к его packet hash и не регистрируется как product verifier.

## Проверяемые границы

- Принадлежность evidence, source/text states, quote/locator/reliability,
  тексты/типы/direct-vs-inferred, весь состав группы и конфликтующих позиций.
- Подмена текста/состояния/позиции не создаёт Verification или класс.
- GroupDetail без canonical snapshot не превращается во вход bridge.
- Совпавшие кешированные DTO не доказывают доступ: отозванный обычный Member
  получает 404, а audit по старому кешу всё равно требует current revalidation.
  Owner имеет отдельный доступ и не используется как отозванный Member.
- Без trusted verifier нет Z3. Условная тестовая K и технический resource failure
  не изменяют уже completed F2 Run и не создают человеческое решение.

Все схемы создаются/удаляются стандартной fixture backend в **явно указанной
test PostgreSQL**. Старые БД и контейнеры не используются. Данные вымышленные.

## Воспроизведение

Python 3.12, backend [test lock](../../backend/requirements-test.lock) плюс
[bridge runtime](../../ai/formal_expectations_bridge/requirements.txt).
Из собственного worktree с установленными изолированными зависимостями:

```powershell
$env:PYTHONPATH = (Get-Location).Path + ';' + (Join-Path (Get-Location) 'backend')
$env:F2R_TEST_DATABASE_URL = '<own-postgresql+psycopg://.../database_with_test_in_name>'
python -B -m pytest experiments/formal_integration_checks -q -W error -p no:cacheprovider
python -B -m unittest discover -s ai/formal_expectations_bridge/tests -v
python -B -m unittest discover -s ai/formal_expectations/tests -v
python -B -m unittest discover -s experiments/qwen_z3/tests -v
ruff check --no-cache ai/formal_expectations_bridge experiments/formal_integration_checks
ruff format --no-cache --check ai/formal_expectations_bridge experiments/formal_integration_checks
```

Linux PYTHONPATH использует `:`. Не указывать рабочую/чужую БД. Тестовая fixture
требует PostgreSQL и `test` в имени; SQLite не заменяет проверку FK/транзакций.
При read-only контейнере нужен writable собственный `/tmp` для temporary files.

Выполненный прогон использует immutable offline AI-checks image, собственные
internal network `f2r-formal-c-20261121` и PostgreSQL
`f2r-formal-c-pg-20261121`, БД `f2r_formal_c_test` на tmpfs, без host ports,
bind исходников read-only и tmpfs `/tmp` у checks. Существующие images читаются
по ID, не пересобираются и не меняют общие tags. Сборка зависимостей с нуля и
реальный inference в этот прогон не входят.

Фактические результаты — [отчёт](../../docs/plans/formal-package-c-readiness.md).
Следующая product-граница описана в [C1 PROPOSED](../../docs/proposals/formal-package-c1.md).
