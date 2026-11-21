# Исправление оценщика и граница серверного подключения

2026-11-21. Ветка `fix/ai-evaluation-acceptance`, отдельный worktree
`.local/worktrees/ai-evaluation-acceptance`. `git fetch origin` выполнен.
Исходная интеграционная база `integration/ai-foundation` остаётся на
`410b936e451629a53ca1eb0fb15a4908961155b6`. Более полная согласованная
`integration/full-workflow-ui`/origin совпали с
`600065626be5e671223c8a8afd696a14bb4c20e5`; новый worktree создан от неё.
Основание этой линии — INT-2026-11-06. Она уже содержит автономные компоненты
из `ab34793a06db660e158f3320f36533467d35bf66`, повторная реализация не создавалась.
Открытая preview/workspace для разработки не использовалась.

## Воспроизведение до исправления

Из QA-коммита `7f9fca437b8c11b51b21d7f4452833a1adebf705` перенесён
`evals/ai/regressions/test_known_defects.py` в обычный
[tests/test_known_defects.py](tests/test_known_defects.py). До изменения
оценщика выполнено:

```text
python -B -W error -m unittest discover -s evals/ai/tests -p test_known_defects.py -v
```

**4 tests, 4 failures**, 3.395 s. В каждом случае оценщик вернул пустой список
ошибок: неправильные quote, locator, reliability прежнего фрагмента и
содержательные issues по not_processed-цели с пустыми considered_keys.
Это воспроизведение на выбранной интеграционной базе, а не только ссылка на
прежний QA-отчёт. Четыре исходных теста и их ожидания сохранены; изменено
описание файла и добавлены отдельные регрессии.

## Исправления

- [check_request](checks.py) пропускал previous_fragments в цикле сверки с
  trusted.texts. Теперь к ним применяются те же проверки точной подстроки,
  абсолютных Unicode code point координат, source/text mapping, reliability и
  интервала, что к текущим фрагментам/сегментам. Пропавший trusted text отклоняется.
- [check_response](checks.py) проверял необработанность только через непустые
  considered_keys, оставляя обход для issues. Теперь issues по необработанной
  target запрещены независимо от considered/conclusion. Необработанные checks
  должны оставаться inconclusive с пустыми considered; чистые содержательные
  выводы также отклоняются кодом RESULT-FROM-UNREVIEWED.
- Все регрессии находятся в обычном discovery, без skip/xfail/opt-in.
  [CI](../../.github/workflows/ai-components.yml) получил обязательный evaluation
  step. Дополнительные проверки покрывают прежнюю речь/интервалы, повышение
  надёжности, UTF-16 ошибку смещения, приватность и отсутствие ремонта входа.
- Восемь [независимых пограничных тестов](tests/test_independent_review.py)
  перенесены из того же QA-коммита без изменения (Git blob
  `1faf5388b372bd0d7e50ce26be8b9ccd1e75f3dd`). Это переиспользование тестов,
  не новое независимое ревью этой реализации.

## Выполненные проверки

Все запуски локальны: `--pull never --network none --read-only`, read-only
исходники, отдельный `/tmp` tmpfs. Только replay-отчётам разрешена запись в
собственный `.local/ai-acceptance-validation`. Чужие контейнеры/БД не менялись.
Новый образ, зависимости и веса не скачивались. Native venv не работает:
ссылается на отсутствующий Python другого пользователя; оно не ремонтировалось.

Оценщик/основные unit/replay: существующий image
`sha256:0c154beef3fd4f49181dafba8fabc4f4c3211aa2110e4c966bf686cdc23b9379`,
Python 3.12.15, jsonschema 4.26.0, referencing 0.37.0, Ruff 0.17.1.
Полная автономная команда CI использует готовый image
`sha256:da3a309e0cc45b09759e559fb8ed53512b67a510884b73d945ad4dd49baa4999`.

| Проверка | Результат |
|---|---|
| Evaluation unittest discovery, `-W error` | **65 tests OK**, 69.863 s: 47 прежних + 8 QA + 10 регрессий |
| Исходный AI unittest discovery, `-W error` | **113 tests OK**, 81.708 s: grouping + generation + verification |
| Новые server-handoff тесты, `-W error` | **4 tests OK**, 4.094 s; оба сервиса, реальные проверки синтетических trusted facts, отказ до провайдера, отсутствие retry |
| Полная автономная команда CI | **Не подтверждена**: прогон начат и выдавал успешные промежуточные результаты; после смены окружения process handle потерян, Docker daemon недоступен, финального exit code/отчёта нет |
| Validator AI-контрактов | PASS: 9 схем, 88 refs, 38 positive / 34 negative, 399 mutations, 20 fixture pairs |
| Verification replay | 18 исходных + 22 контроля + 2 смысловых контрпримера, 0 технических диагностик, exit 0 |
| Generation replay | 11 исходных + 15 контролей + 2 смысловых контрпримера, 0 технических диагностик, exit 0 |
| Grouping replay | 3 исходных + 8 контролей, 0 технических диагностик, exit 0 |
| Controls CLI replay | 46 записей, 46 expert pending, exit 0 |
| Faults CLI replay | 24 намеренные ошибки, ожидаемый exit 1; исходные тесты подтверждают ожидаемые diagnostic codes |
| Ruff check / format --check | PASS для изменённых Python и evaluation tests; 5 файлов отформатированы |

В Ruff исключён только EXE002 из-за executable metadata Windows bind-mount;
проверки поведения и warnings не отключались. Первые lint/format проверки
новых тестов выявили незакреплённые переменные замыкания и форматирование;
исправлены. Первый запуск новых handoff-тестов использовал несуществующую
пару S01/verify; исправлена тестовая привязка на имеющуюся S06/verify, без
изменения ожидаемого поведения. Повторные проверки прошли.

Подтверждены **182 теста**: 65 evaluation + 113 основных AI + 4 новых handoff.
Они не зависят от результата расширенного pytest-прогона. Полный автономный
CI (включая неизменённые formal/experiments) нужно повторить при доступном
Docker и сохранить финальный отчёт. Daemon/чужие сервисы ради этого не
перезапускались; незавершённый прогон не объявляется PASS.

Схемы, исходный S01–S14, аннотации и старые тесты не переписывались.
Runtime генерации/проверки/группировки, backend/F2/F3, очередь, migrations,
frontend и модели данных не изменены. Новых API/AI-полей/ролей нет.
Изменение checker означает, что отчёты следует привязывать также к коммиту
оценщика, а не сравнивать версии только по неизменившемуся hash схем.

## Воспроизведение и результаты

Из собственного worktree с рабочим Python 3.12 и существующими зависимостями:

```text
python -B -W error -m unittest discover -s evals/ai/tests -v
python -B -W error -m unittest discover -s ai/tests -v
python -B scripts/validate_ai_contracts.py
python -B evals/ai/verification/replay.py --output .local/replay-verification-new
python -B evals/ai/generation/replay.py --output .local/replay-generation-new
python -B evals/ai/grouping/replay.py --output .local/replay-grouping-new
```

Точная автономная команда CI (PYTHONPATH=backend:.):

```text
python -B -m pytest ai/tests ai/formal_expectations/tests ai/formal_expectations_bridge/tests experiments/qwen/tests experiments/qwen_z3/tests -q -W error -p no:cacheprovider
```

Ruff:

```text
python -m ruff check --no-cache --ignore EXE002 evals/ai/checks.py evals/ai/tests ai/tests/test_server_handoff.py
python -m ruff format --no-cache --check evals/ai/checks.py evals/ai/tests ai/tests/test_server_handoff.py
```

Локальные отчёты, не включённые в Git:
[verification](../../.local/ai-acceptance-validation/verification/summary.json),
[generation](../../.local/ai-acceptance-validation/generation/summary.json),
[grouping](../../.local/ai-acceptance-validation/grouping/summary.json),
[controls](../../.local/ai-acceptance-validation/controls/report.md),
[faults](../../.local/ai-acceptance-validation/faults/report.md).
Output каждого запуска — новый каталог, прежние отчёты не перезаписываются.

## Готовность и ограничения

[Общее описание серверной границы](../../ai/SERVER_HANDOFF.md) фиксирует
действующие входы/выходы, сигнатуры, обязательный verify_context, trusted
required_context/ReviewPlan, приём и безопасные ошибки. Примеры запуска сохранены
в README обоих компонентов. Тесты подтверждают возможность вызова библиотек и
отказов на фиксированных синтетических состояниях.

Для реального подключения остаются отдельно согласованные серверные снимки,
права/проектные проверки/цитаты по хранилищу, неизменяемые редакции, атомарный
приём/идемпотентность и управление попытками, история блокеров и решений.
Конкретное предложение уже существует как [пакет B, PROPOSED](../../docs/proposals/workflow-contracts.md#b-требования-редакции-и-проверки-минимальный-серверный-срез).
Его статус не менялся; новая таблица/endpoint этой работой не утверждаются.
Callback оценщика работает с фикстурой и не заменяет настоящий backend verifier.

Нет реального inference, экспертной оценки, нового независимого ревью,
PG/API/worker/UI/гонки/unknown-COMMIT тестов. Смысловая поддержка, достаточность,
конфликты/дубли, severity/blocking, injection и поведение реального Ollama не
проверены. Намеренные смысловые контрпримеры продолжают проходить технический
приём и остаются для эксперта. Синтетический PASS не означает качество модели
или production-готовность. Внешние AI-вызовы, push и merge не выполнялись.

Изменения фиксируются локальным коммитом; точный SHA приводится в итоговом
сообщении. До публикации удалённый CI не запускался и не объявляется прошедшим.
