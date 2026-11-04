# Общая интеграционная база AI — 2026-11-04

Основание: поручение пользователя собрать `integration/ai-foundation` для
дальнейших независимых направлений generate_requirements, Z3 и эксперимента Qwen.
Их реализация в задачу не входит. Утверждённые документы и AI-контракты 1.0
сохраняются; новая архитектура, API и модель данных не вводятся.

## Исходные состояния и способ интеграции

- После `git fetch origin` удалённый main:
  `cfb96f45ecbe2ef8487c1dd145cb081f3a90aec9`.
- Удалённая feat/ai-group-findings:
  `f5ffa486ccaee7ebefe169e7cca2430edda221c8`.
- Параллельная feat/backend-finding-groups:
  `dbf365b77f4b78f042b89bd7100eb5b014fa66d2`; её worktree содержит
  незакоммиченные изменения. В интеграцию не входит и не изменяется.
- Аналогичной локальной или удалённой интеграционной ветки до начала не было.
- Проверены все 10 исходных worktree: изменения были только в worktree F2.
- Создан собственный worktree `.local/worktrees/ai-foundation` от origin/main.
- История группировки содержит единственный уникальный коммит f5ffa48;
  применён `git cherry-pick f5ffa486ccaee7ebefe169e7cca2430edda221c8`.
  Получен `88ca281da339ca9e759d571af90d3a563cb71914` с 19 файлами.
  Конфликтов нет; README автоматически объединён.
  F1, backend, worker, frontend и прежние evals взяты из main без замены файлов.

## План проверки

1. Проверить зависимости, импорты, локальные схемы, адаптеры и CLI.
2. Запустить AI unit tests, grouping tests, S01–S14, contracts и replay.
3. Запустить доступные регрессии backend/F1 в собственной PostgreSQL,
   Ruff и форматирование. Не использовать чужие БД или контейнеры.
4. Получить независимое read-only ревью, записать фактические результаты и
   ограничения; создать итоговый коммит. В main не сливать и ветку не публиковать.

Использовать уже имеющиеся локальные Docker-образы с зафиксированным image ID.
Синтетические проверки AI запускать с отключённой сетью. Модели не скачивать,
внешние AI-сервисы не вызывать.

## Граница F2 и последующих направлений

Группировка остаётся автономной Python-операцией. Обязанности будущего F2
(проверка доверенного контекста/прав, повторная проверка состояния, сохранение,
публикация и связь локальных ID) описаны в
[README группировки](../../ai/group_findings/README.md#граница-интеграции-с-f2).
Этот документ не утверждает миграции или API F2. Backend/worker не импортируют
новую операцию, новых обязательных AI-вызовов нет. Новые направления должны
ответвляться от итогового коммита этой базы и соблюдать существующие контракты;
подключение к продуктовому workflow требует отдельного согласованного объёма.

## Перенесённые файлы

Все файлы, кроме автоматически объединённого README, добавлены без изменений
относительно f5ffa48. Существующие файлы main не заменялись версиями старой ветки.

1. [README.md](../../README.md) — добавлен раздел группировки.
2. [ai/__init__.py](../../ai/__init__.py).
3. [ai/group_findings/MODEL_SELECTION.md](../../ai/group_findings/MODEL_SELECTION.md).
4. [ai/group_findings/README.md](../../ai/group_findings/README.md).
5. [ai/group_findings/__init__.py](../../ai/group_findings/__init__.py).
6. [ai/group_findings/__main__.py](../../ai/group_findings/__main__.py).
7. [ai/group_findings/prompt.py](../../ai/group_findings/prompt.py).
8. [ai/group_findings/provider.py](../../ai/group_findings/provider.py).
9. [ai/group_findings/service.py](../../ai/group_findings/service.py).
10. [ai/group_findings/validation.py](../../ai/group_findings/validation.py).
11. [ai/requirements.txt](../../ai/requirements.txt).
12. [ai/tests/test_group_findings.py](../../ai/tests/test_group_findings.py).
13. [docs/plans/ai-group-findings.md](ai-group-findings.md).
14. [evals/ai/grouping/VALIDATION.md](../../evals/ai/grouping/VALIDATION.md).
15. [evals/ai/grouping/build_cases.py](../../evals/ai/grouping/build_cases.py).
16. [evals/ai/grouping/cases.json](../../evals/ai/grouping/cases.json).
17. [evals/ai/grouping/compatible.request.json](../../evals/ai/grouping/compatible.request.json).
18. [evals/ai/grouping/compatible.response.json](../../evals/ai/grouping/compatible.response.json).
19. [evals/ai/grouping/replay.py](../../evals/ai/grouping/replay.py).

Дополнительно создан этот план/отчёт интеграции, а в корневой README добавлена
ссылка на него. Новых продуктовых контрактов или решений эти записи не вводят.

## Среда и реальные команды проверки

Native Python отсутствует (Windows Store alias не является интерпретатором).
Использован существующий образ
`sha256:0c154beef3fd4f49181dafba8fabc4f4c3211aa2110e4c966bf686cdc23b9379`:
Python 3.12.15, jsonschema 4.26.0, referencing 0.37.0, pytest 9.1.1,
Ruff 0.17.1. Проверка установленных версий против всех записей
backend/requirements-test.lock, ai/requirements.txt и evals/ai/requirements.txt
прошла; `python -m pip check` — PASS. Ничего не устанавливалось.

Каждая автономная команда из таблицы ниже запускалась так (PowerShell,
корень интеграционного worktree; короткий ID обозначает тот же закреплённый образ):

```powershell
docker run --rm --network none `
  --mount "type=bind,source=$((Get-Location).Path),target=/workspace,readonly" `
  -w /workspace --entrypoint python 0c154beef3fd <аргументы из таблицы>
```

Для CLI и replay добавлен отдельный write-mount
`.local/ai-foundation-validation` → `/results`; исходный код остался read-only.
Результаты replay — локальные диагностические файлы и в коммит не включены.

| Аргументы Python / проверка | Фактический результат |
|---|---|
| `-B -W error -m unittest discover -s ai/tests -v` | PASS: 37 tests, включая grouping invariants, CLI failure/no-overwrite и mocked Ollama transport |
| `-B -W error -m unittest discover -s evals/ai/tests -v` | PASS: 47 tests, включая ожидаемые коды всех ошибочных replay-записей |
| `-B evals/ai/cli.py validate-dataset` | PASS: S01–S14, 46 examples; dataset SHA256 `6926cb777854891d20727d868036e0e5fcfb0956952bf4e2ef566e224ea6169d` |
| `-B evals/ai/build_dataset.py` | PASS: 22 воспроизводимых синтетических артефакта, без записи |
| `-B scripts/validate_ai_contracts.py` | PASS: 9 Draft 2020-12 schemas, 88 local refs, 38 positive / 34 negative examples, 399 unknown-field mutations, 20 fixture pairs |
| `-B -m ai.group_findings --request evals/ai/grouping/compatible.request.json --synthetic-response evals/ai/grouping/compatible.response.json --output /results/grouping-result.json` | PASS, exit 0; `model=none`, `semantic_quality=not_evaluated` |
| `-B evals/ai/grouping/replay.py --output /results/grouping-component` | PASS: 3 S05/S06 records + 8 controls, 0 technical diagnostics |
| `-B evals/ai/cli.py replay --input evals/ai/datasets/synthetic-ru-v1/replays/controls.json --output /results/controls` | PASS: 46 records, 0 автоматических нарушений; 46 экспертных оценок pending |
| `-B evals/ai/cli.py replay --input evals/ai/datasets/synthetic-ru-v1/replays/faults.json --output /results/faults` | Ожидаемый exit 1: 24 намеренно ошибочные записи, в том числе 4 технических сбоя; не объявляется успешным replay |
| `-B -m ruff check --no-cache backend scripts/check_i1_restart.py ai evals/ai` | FAIL: 11 EXE002 из-за executable bit Windows bind-mount; в Git соответствующие файлы имеют mode 100644 |
| `-B -m ruff check --no-cache --ignore EXE002 backend scripts/check_i1_restart.py ai evals/ai` | PASS; документирован обход только ложного executable bit, исходники/конфигурация не изменялись |
| `-B -m ruff format --no-cache --check ai evals/ai/grouping` | PASS: 13 files already formatted |
| `-B -m ruff format --no-cache --check backend scripts/check_i1_restart.py ai evals/ai` | FAIL: 3 прежних файла main требуют форматирования; остальные 68 отформатированы |
| `git diff --check origin/main HEAD` | PASS |

Три унаследованных format-failure:
[persistence/processing.py](../../backend/feedback2req/persistence/processing.py),
[test_processing_provider.py](../../backend/tests/test_processing_provider.py),
[test_worker_probe.py](../../backend/tests/test_worker_probe.py).
Они побайтово совпадают с main; интеграция их не меняет и не скрывает сбой.

### Backend/F1

Созданы собственные internal-сеть `f2r-ai-foundation-20261104` и контейнер
`f2r-ai-foundation-20261104-db` с БД `feedback2req_ai_foundation_test`,
без host ports, на существующем PostgreSQL 17 image
`sha256:b8faeff7712663c2773a190181e1246e37e364b887611c04658c28b44e2408fe`.
Команда backend (тот же read-only mount, закреплённый checks image):

```powershell
docker run --rm --name f2r-ai-foundation-20261104-tests `
  --network f2r-ai-foundation-20261104 `
  --mount "type=bind,source=$((Get-Location).Path),target=/workspace,readonly" `
  -w /workspace -e PYTHONPATH=/workspace/backend:/workspace `
  -e F2R_TEST_DATABASE_URL=postgresql+psycopg://f2r_test@f2r-ai-foundation-20261104-db/feedback2req_ai_foundation_test `
  --entrypoint python 0c154beef3fd -B -m pytest backend/tests -q -W error -p no:cacheprovider
```

**PASS: 101 passed in 100.18s.** Ни skips, ни suppressed warnings.
PYTHONPATH указывает на текущие исходники интеграции, а не старую установленную
копию приложения внутри образа.

Дополнительный HTTP/worker/restart прогон использует существующий
[compose.extraction-test.yaml](../../compose.extraction-test.yaml) с отдельным
project `f2r-ai-foundation-extract-20261104`. Локальный override
`.local/ai-foundation-validation/extraction.override.yaml` только закрепляет
image ID, монтирует этот worktree read-only и задаёт `PYTHONPATH=/workspace/backend`
и команду API `python -m feedback2req.runtime backend` для checks image.
Исходный Compose и общие image tags не менялись; сборки и pull не выполнялись.
Сеть internal, host ports нет, провайдер — исключительно синтетический HTTP double.

```powershell
$foundationCompose = @('-p','f2r-ai-foundation-extract-20261104',
  '-f','compose.extraction-test.yaml',
  '-f','.local/ai-foundation-validation/extraction.override.yaml')
docker compose @foundationCompose up -d --wait --wait-timeout 90 --pull never db api provider worker
docker compose @foundationCompose run --rm --pull never checks seed
docker compose @foundationCompose exec -T worker python /checks/probe.py corrupt
$foundationWorker = docker compose @foundationCompose ps -q worker
$foundationRestartBefore = [int](docker inspect -f '{{.RestartCount}}' $foundationWorker)
docker compose @foundationCompose exec -T worker python /checks/probe.py hang
# Опрос RestartCount раз в секунду, не более 40 раз; требуется увеличение.
docker compose @foundationCompose up -d --wait --wait-timeout 60 --pull never worker
docker compose @foundationCompose run --rm --pull never checks verify
docker compose @foundationCompose stop api worker
docker compose @foundationCompose restart db
docker compose @foundationCompose up -d --wait --wait-timeout 60 --pull never api worker
docker compose @foundationCompose run --rm --pull never checks verify
docker compose @foundationCompose run --rm --pull never checks failure
docker compose @foundationCompose run --rm --pull never checks slow
```

**Все перечисленные шаги прошли, exit 0.** Seed подтвердил настоящую цепочку
HTTP → durable queue → worker → synthetic provider → accepted PG result.
Corrupt snapshot вернул unhealthy без убийства замороженного supervisor;
hang вызвал настоящий restart: RestartCount увеличился с 0 до 1.
Session/text/run/fragment/evidence/finding сохранились как после probe restart,
так и после stop/start API/worker и restart PostgreSQL. Provider failure
не создал фиктивных находок; явный retry прошёл проверку идемпотентности.
35-секундное вычисление завершилось с heartbeat за пределами короткого SQL budget.

## Совместимость и независимое ревью

- `git merge-base --is-ancestor` подтверждает наличие F1 (1713498) и AI-evals
  (800d9fb) в main. Нулевая разница с main для backend, worker, frontend,
  schemas/examples, AI_CONTRACTS, прежних evals/tests и dataset проверена Git.
- Импорты группировки и разрешение локальных схем успешно проверены отдельным
  reviewer в Docker с `--network none --read-only` и read-only bind mount.
  При импорте и приёме фикстуры backend/FastAPI/SQLAlchemy/psycopg отсутствуют
  в sys.modules. Самодостаточная provider schema также прошла валидацию.
- Адаптер F1 не изменён. Адаптер группировки использует тот же `/api/chat`,
  отдельные system/user messages, `stream=false` и локально собранный `format`.
  Unit tests обоих адаптеров проверяют payload/envelope/ошибки без реальной модели.
  Группировка по умолчанию запрещает передачу (`transfer_enabled=False`),
  redirects и ambient proxy; импорт не запускает AI.
- Независимое read-only ревью diff main..88ca281 не нашло существенных дефектов.
  Reviewer не повторял полный набор unit/evals/F1/Ruff и не проверял живую модель.

## Ограничения и готовность

Все AI-прогоны синтетические. Разметка S01–S14 остаётся PRELIMINARY,
семантическое качество и устойчивость реальной модели не оценивались.
Совместимость `think` и сложной schema с конкретной версией живого Ollama
не проверена. Нет скачивания моделей или вызовов внешних AI-сервисов.

Известные ограничения автономной группировки сохранены: 1 MiB на JSON,
отклонение `partially_processed` без доверенного плана подединиц; упаковка требует
соседних схем в docs/contracts/ai/v1. No-op verify_context допустим только для
синтетических фикстур; реальная проверка прав/состояний и публикация принадлежат F2.
Backend Dockerfile не упаковывает новый автономный модуль; продуктовое подключение
не входит в эту базу. Миграции/API F2 не перенесены и не утверждены.

Полный frontend/browser suite, пересборка production images, live Ollama и CI
в этой задаче не запускались. Frontend сохранён побайтово из main.
Полная проверка форматирования пока имеет три унаследованных сбоя; это известный
долг main, а не полностью зелёная проверка форматирования репозитория.

Итоговая ветка готова быть общей рабочей базой для трёх независимых
AI-направлений с перечисленными ограничениями проверок и сохранением текущих
продуктовых контрактов. От неё можно создать три независимые рабочие ветки.
Собственные тестовые сервисы остановлены; тестовые volumes сохранены.
Другие ветки и worktree не изменялись. Слияние в main и публикация ветки
не выполнялись. Итоговый SHA фиксируется завершающим коммитом этого отчёта
и сообщается пользователю отдельно (самоссылка на SHA в коммите невозможна).
