# Проверка generate_requirements 1.0

Проверки выполнены 2026-11-04; документальное завершение — 2026-11-06.
Ветка `feat/ai-generate-requirements`, отдельный worktree
`.local/worktrees/ai-generate-requirements`. После `git fetch origin` локальная
и удалённая `integration/ai-foundation` совпали с заданным SHA
`410b936e451629a53ca1eb0fb15a4908961155b6`. Рабочая ветка создана от него.
В базе подтверждены F1, evaluator и автономная группировка.

F2 изучен только через `git show` опубликованного
`20656819aad3a857875ec0d91a263d903c85638b`: контракт чтения групп,
prepare/accept, точные states, lease/deadline и граница публикации.
Во время работы remote-tracking ref F2 обновился до `ee65b9a…` параллельно
работе в общем Git-хранилище; этот новый код не использован и не объявляется
проверенным. F2 не изменён и не объединён. Чужие worktree, backend/frontend
и схемы 1.0 в этой задаче не изменяются.

## Фактически выполненные проверки

Использован существующий image
`sha256:0c154beef3fd4f49181dafba8fabc4f4c3211aa2110e4c966bf686cdc23b9379`
(короткий ID `0c154beef3fd`): Python 3.12.15, jsonschema 4.26.0,
referencing 0.37.0, Ruff 0.17.1. Зависимости/образы/модели не скачивались.
Тесты и replay выполнялись с `--network none` и read-only mount исходников;
для отчётов был отдельный write-mount в локальный игнорируемый каталог.
Форматирование и генерация собственных контролей имели write-mount только
своего worktree, без доступа на запись к чужим рабочим каталогам.

| Проверка | Результат |
|---|---|
| `python -B -W error -m unittest discover -s ai/tests -v` | **69 tests, OK**, 17.751 s: 32 новых + 37 регрессионных grouping |
| `python -B -W error -m unittest discover -s evals/ai/tests -v` | **47 tests, OK**, 26.681 s |
| `python -B scripts/validate_ai_contracts.py` | PASS: 9 схем, 88 локальных ссылок, 38 положительных / 34 отрицательных примера, 399 мутаций неизвестных полей, 20 пар |
| `python -B evals/ai/cli.py validate-dataset` | PASS: S01–S14, 46 примеров, PRELIMINARY |
| Replay генерации через новый модуль и исходный runner | PASS: 11 исходных примеров + 15 новых контролей, 0 технических диагностик; 2 смысловых контрпримера сохранены отдельно, экспертные листы pending |
| Регрессионный replay группировки | PASS: 3 исходных примера + 8 контролей, 0 технических диагностик |
| Исходный replay controls | PASS: 46 записей, 46 экспертных листов pending, exit 0 |
| Исходный replay faults | 24 намеренные ошибки, **ожидаемый exit 1**; ожидаемые коды проверены исходными unit-тестами |
| Ruff check и format --check | PASS после форматирования новых исходников/примеров документации; финальный запуск 2026-11-06 |

Суммарно 116 unit-тестов. Предварительная разметка и семантические вердикты
не утверждались. Первоначальный format --check указал на пустые строки в
новом примере документации; формат исправлен до коммитов.
В lint исключено только EXE002: Windows Docker bind-mount представляет
файлы executable независимо от Git mode. Предупреждения Python не подавлялись.

Локальные воспроизводимые результаты (не входят в Git):

- [Сводка генерации](../../../.local/generation-validation/generation-1/summary.json).
- [Исходные generation-примеры](../../../.local/generation-validation/generation-1/evaluation/report.md).
- [Новые экспертные листы](../../../.local/generation-validation/generation-1/additional-review.json).
- [Регрессия grouping](../../../.local/generation-validation/grouping-regression/summary.json).
- [Все контроли](../../../.local/generation-validation/all-controls/report.md).
- [Намеренные ошибки](../../../.local/generation-validation/all-faults/report.md).

SHA-256 исходного набора не изменён:
`6926cb777854891d20727d868036e0e5fcfb0956952bf4e2ef566e224ea6169d`.
В оригинальные S01–S14, evaluator, schemas и их аннотации изменений нет.

## Повторение

Из корня этого worktree с уже установленными зависимостями:

```text
python -B -W error -m unittest discover -s ai/tests -v
python -B -W error -m unittest discover -s evals/ai/tests -v
python -B scripts/validate_ai_contracts.py
python -B evals/ai/cli.py validate-dataset
python -B evals/ai/generation/replay.py --output evals/ai/results/generation-run
python -B evals/ai/grouping/replay.py --output evals/ai/results/generation-grouping-regression
python -B evals/ai/cli.py replay --input evals/ai/datasets/synthetic-ru-v1/replays/controls.json --output evals/ai/results/generation-controls
python -B evals/ai/cli.py replay --input evals/ai/datasets/synthetic-ru-v1/replays/faults.json --output evals/ai/results/generation-faults
python -m ruff check --no-cache --ignore EXE002 ai evals/ai/generation
python -m ruff format --no-cache --check ai evals/ai/generation
```

Для воспроизведения в проверенном Docker-образе, PowerShell из корня worktree:

```powershell
docker run --rm --network none `
  --mount "type=bind,source=$((Get-Location).Path),target=/work,readonly" `
  -w /work --entrypoint python 0c154beef3fd `
  -B -W error -m unittest discover -s ai/tests -v
```

Replay требует отдельного write-mount каталога отчётов и нового имени результата;
повторная запись существующих отчётов запрещена. Прямой CLI и примеры:
[инструкция модуля](../../../ai/generate_requirements/README.md).

## Покрытие и границы

| Область | Свидетельство |
|---|---|
| Один кандидат, несколько независимых, несколько оснований, одна находка → несколько кандидатов | single, independent, several-findings, several-from-one |
| Недостаточно определённое изменение | insufficient: вопрос вместо выдуманного сохранения фильтров |
| Ограниченное условие и неизвестное вне него | bounded-export: только при наличии отметок; вопрос про отсутствие отметок не блокирует этот случай |
| Потребность и способ решения | need-vs-solution: inferred-потребность в rationale; unsupported-solution — намеренная смысловая ошибка |
| Конфликт/разные условия/независимое продолжение | conflict-with-independent, different-conditions |
| Документ против отзыва, ненадёжная речь | document-discrepancy, uncertain-speech: уточнения без произвольного выбора версии |
| Пустой результат, неполный набор, повтор | successful-empty, mixed-coverage, regeneration |
| Недоверенные инструкции | injection: отзыв/документ/change_reason остаются user-данными; transport test подтверждает отделение system prompt |
| Ссылки и охват | Мутации evidence/considered/context/related, чужие/отсутствующие ключи, глобальные IDs, пропущенные finding, отсутствие причины при пустом результате |
| Существенное ограничение | lost-condition — явно смысловой контрпример, а не позитивный эталон |

Оригинальные generation-примеры относятся к S01–S08 и S11; остальные
сценарии S09/S10/S12/S13/S14 дают критерии unsupported claims, речи,
пропусков, утраты, прежних результатов и injection, перенесённые в новые
контроли/программные тесты без переписывания исходных сценариев.

Детерминированный приём не обнаруживает смысловую ошибку по одной правильной
ссылке: оба контрпримера проходят технические проверки и помечены
`intentional_semantic_error`. Тест специально подтверждает эту границу.
Сохранение режима/надёжности во входе не доказывает правильную интерпретацию
моделью; gate verifier не доказывает настоящие права/состояния backend.

Частичный охват набора поддержан смесью dispositions. Внутренний
`partially_processed` отклоняется без проверяемого доверенного плана подединиц.
Не реализованы автоматическая сегментация, агрегация нескольких вызовов,
retry, хранение, публикация, идемпотентность или отмена. Технический сбой
не создаёт вымышленный coverage. Ограничение JSON — 1 MiB без усечения;
токенизация и отсутствие усечения на реальном сервере не проверены.

Модель не выбиралась и не запускалась, её качество не измерялось. Внешних
AI-вызовов, загрузки весов, изменений worker/БД/API F2 и frontend нет.
Backend/DB/F2-интеграционные тесты не запускались: код этих компонентов
не менялся. Независимого ревью нового кода в этой сессии не было;
выполнены самопроверка, unit, replay, schema и lint.
Четыре статьи не доступны; сопоставление их текстов остаётся невыполненным,
ограничение и аналитическая записка —
[generation-contract-evolution](../../../docs/research/generation-contract-evolution.md).

## Изменённые файлы

- [Общий Ollama transport](../../../ai/group_findings/provider.py): только выбор prompt/schema при сохранении прежних defaults.
- [Публичный интерфейс](../../../ai/generate_requirements/__init__.py).
- [Сервис](../../../ai/generate_requirements/service.py).
- [Prompt](../../../ai/generate_requirements/prompt.py).
- [Провайдеры](../../../ai/generate_requirements/provider.py).
- [Подготовка и приём](../../../ai/generate_requirements/validation.py).
- [CLI](../../../ai/generate_requirements/__main__.py).
- [Инструкция и интерфейс backend](../../../ai/generate_requirements/README.md).
- [Unit-тесты](../../../ai/tests/test_generate_requirements.py).
- [Генератор контролей](build_cases.py).
- [Контроли и контрпримеры](cases.json).
- [Пример входа](bounded.request.json).
- [Пример выхода](bounded.response.json).
- [Replay](replay.py).
- [Этот отчёт](VALIDATION.md).
- [Аналитическая записка](../../../docs/research/generation-contract-evolution.md).
- [План](../../../docs/plans/ai-generate-requirements.md).
- [Корневой README](../../../README.md): навигационная ссылка.

Реализация и тесты: `0e1cf75` — `feat(ai): implement standalone requirements generation`.
Документация и результаты фиксируются отдельным коммитом.
Оба SHA приводятся в итоговом сообщении и доступны через
`git log 410b936..feat/ai-generate-requirements`. Push и merge этой задачи
не выполняются. Следующий предложенный этап — автономный verify_requirement
после отдельного поручения; его реализация сюда не включена.
