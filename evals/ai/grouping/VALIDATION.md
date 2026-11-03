# Проверка автономной group_findings 1.0

Дата: 2026-11-03. Ветка `feat/ai-group-findings`, база `800d9fb` актуальной
`origin/agents/ai-feedback2req-testing-preparation` после `git fetch origin`.
Worktree: `.local/worktrees/ai-group-findings` основного репозитория.
F1 изучена на `1713498`, независимое ревью контура — `7f9fca4`.
Слияния веток, изменения backend/F2 и контрактов 1.0 не выполнялись.

Результат: [самостоятельный модуль](../../../ai/group_findings/README.md),
[подготовка и приём](../../../ai/group_findings/validation.py),
[сменные адаптеры](../../../ai/group_findings/provider.py),
[интеграционный интерфейс](../../../ai/group_findings/service.py).

## Фактически выполнено

Локальный Docker image ID `0c154beef3fd` (`feedback2req-checks:latest`),
Python 3.12.15, jsonschema 4.26.0, referencing 0.37.0, Ruff 0.17.1.
Сеть контейнеров отключена (`--network none`), репозиторий read-only при
тестах, для отчётов отдельный write-mount. Установка пакетов и загрузка
новых образов не потребовались. Форматирование выполнялось с write-mount
только выделенного worktree, для новых Python-файлов задачи.

| Проверка | Фактический результат |
|---|---|
| `python -B -W error -m unittest discover -s ai/tests -v` | **37 tests, OK**, 20.545 s, exit 0 |
| `python -B -W error -m unittest discover -s evals/ai/tests -v` | **47 tests, OK**, 38.865 s, exit 0 |
| `python -B scripts/validate_ai_contracts.py` | 9 схем, 88 локальных ссылок, 38 положительных / 34 отрицательных примера, 399 мутаций полей, 20 пар; exit 0 |
| `python -B evals/ai/cli.py validate-dataset` | 14 сценариев, 46 примеров; разметка PRELIMINARY; exit 0 |
| Исходный replay `controls.json` | 46 записей, 46 экспертных листов pending; exit 0 |
| Исходный replay `faults.json` | 24 намеренных ошибки; **exit 1 ожидаем**; диагностики проверены исходными тестами |
| `python -B evals/ai/grouping/replay.py --output <новый каталог>` | 3 примера S05/S06 + 8 добавочных контролей через новый модуль; 0 технических диагностик, exit 0 |
| Ruff check/format | PASS для `ai/` и `evals/ai/grouping/` |

Новые тесты сначала выявили две ошибки в настройке HTTP-заглушек (`Mock`
вместо `MagicMock` для context manager). Они исправлены, итоговый запуск
полностью прошёл. Первоначальный lint не смог создать кеш на read-only mount;
повтор выполнен с `--no-cache`, исправлены замечания к коду/формату.
Правило EXE002 исключено только в команде lint: Windows bind-mount отображает
все файлы как executable. Проверки поведения и ожидаемые результаты не ослаблены.

Повторение в уже существующем окружении с зависимостями:

```text
python -B -W error -m unittest discover -s ai/tests -v
python -B -W error -m unittest discover -s evals/ai/tests -v
python -B scripts/validate_ai_contracts.py
python -B evals/ai/cli.py validate-dataset
python -B evals/ai/cli.py replay --input evals/ai/datasets/synthetic-ru-v1/replays/controls.json --output evals/ai/results/grouping-controls
python -B evals/ai/cli.py replay --input evals/ai/datasets/synthetic-ru-v1/replays/faults.json --output evals/ai/results/grouping-faults
python -B evals/ai/grouping/replay.py --output evals/ai/results/grouping-component
python -m ruff check --no-cache --ignore EXE002 ai evals/ai/grouping
python -m ruff format --no-cache --check ai evals/ai/grouping
```

Исходный набор не изменён: SHA-256
`6926cb777854891d20727d868036e0e5fcfb0956952bf4e2ef566e224ea6169d`.
Локальные отчёты этого запуска (не отслеживаются Git):

- [Сводка группировки](../../../.local/grouping-validation/grouping-run-1/summary.json).
- [S05/S06 и экспертный шаблон](../../../.local/grouping-validation/grouping-run-1/evaluation/report.md).
- [Все контроли](../../../.local/grouping-validation/all-controls/report.md).
- [Намеренные ошибки](../../../.local/grouping-validation/all-faults/report.md).

## Что покрыто

Сценарии [cases.json](cases.json) — контролируемые ответы, не модельный вывод:
совместимые ожидания; кандидат конфликта с двумя позициями и вопросом;
разные условия без искусственного конфликта; неопределённая проблема;
находка в двух группах; сохранение успешной группы при пропуске другой находки;
встроенная инструкция; прежняя группа и документ как контекст.

Программные тесты проверяют закрытые схемы, строгий JSON (дубликаты свойств,
NaN/Infinity/overflow, неверная кодировка, размер), глобальные ключи/ID,
coverage и потерю completed-находок, роли ссылок, состав конфликтов, scope
вопросов, неизвестные ссылки неопределённости, Unicode code points,
интервалы речи и отсутствие изменения входной надёжности. Проверены
исторические ссылки удаления без восстановления фрагментов, many-to-many,
ошибки verifier до AI-вызова, изоляция копий, gate передачи, параметры
транспорта, timeout, неполная оболочка, запрет redirect и перезаписи CLI-файла.
Отдельный тест показывает, что вымышленный пересказ может пройти структурные
проверки: это намеренная демонстрация границы, а не семантический PASS.

## Применимость S01–S14

| Сценарии | Связь с группировкой и дополнительная проверка |
|---|---|
| S05, S06 | Уже имеют group_findings: повторяющиеся пожелания, перестановка, конфликтующие позиции. Все три ответа пропущены через новый компонент и существующий runner |
| S01–S03 | Перефразы, direct/inferred, несколько смыслов: prompt сохраняет эти различия; добавлены совместимость и many-to-many. Семантику должна проверить модель/эксперт |
| S04, S07 | Отсутствие достаточного основания и неоднозначность: допустимы ungrouped, insufficient_information, uncertainty и scoped-вопрос |
| S08 | Документация как контекст и расхождения: добавлен случай previous-and-document; истинность интерпретации не доказана |
| S09 | Неподтверждённые выводы/ложные конфликты: отдельный контроль разных условий и тест ограничения структурного приёма |
| S10, S11 | Пропуски, речь, ссылки, координаты и надёжность: mixed-coverage и технические тесты. Нет заявления о чтении моделью всего контекста |
| S12 | Утрата оснований: историческая deleted_source допустима без восстановления доступного фрагмента; достаточность требует эксперта |
| S13 | Прежние результаты и человеческая работа: previous_groups передаются как контекст; актуальность, старые блокеры и публикация принадлежат F2 |
| S14 | Добавлен group-вход со встроенной инструкцией; проверено разделение system/user. Устойчивость настоящей модели не испытана |

Оригинальные сценарии, их предварительная разметка и результаты ревью
сохранены. Новые случаи не превращают PRELIMINARY в утверждённую истину.

## Ограничения и непроверенное

Реальная модель/провайдер не согласованы и не вызывались. Оценки смысловой
правильности, русского языка, конфликтов, качества вопросов и устойчивости
к injection **не проводились**. Экспертные листы остаются pending.
Отдельная [рекомендация модели](../../../ai/group_findings/MODEL_SELECTION.md)
учитывает проверенное оборудование и первичные карточки, но не результаты inference.

Исполнитель поддерживает `completed`, `insufficient_information`,
`not_processed` и их смеси. `partially_processed` внутри одной находки
отклоняется без доверенного плана подединиц. Автоматическая сегментация,
агрегация нескольких вызовов, retry, отмена, worker, публикация, БД и API
не реализованы в этой задаче. Нет доказательства отсутствия усечения контекста
на реальном сервере. Интеграционные проверки F2/прав/гонок не запускались.

Независимого ревью нового компонента в этой сессии не было; выполнены
самопроверка и автоматические проверки. Изучено существующее независимое
ревью `7f9fca4`: его два известных дефекта касаются `previous_fragments`
извлечения и `not_processed` проверки требований. Они не исправлялись и
не объявляются устранёнными; четыре строгих регрессии той ветки сюда не
переносились. Существующие схемы и evaluator не менялись.

## Изменённые файлы

- [README](../../../README.md) — ссылка на автономный компонент.
- [ai/__init__.py](../../../ai/__init__.py) — пакет независимых AI-компонентов.
- [requirements.txt](../../../ai/requirements.txt) — зависимости модуля.
- [публичный интерфейс](../../../ai/group_findings/__init__.py).
- [CLI](../../../ai/group_findings/__main__.py).
- [prompt](../../../ai/group_findings/prompt.py).
- [provider](../../../ai/group_findings/provider.py).
- [service](../../../ai/group_findings/service.py).
- [validation](../../../ai/group_findings/validation.py).
- [инструкция и граница F2](../../../ai/group_findings/README.md).
- [сравнение моделей](../../../ai/group_findings/MODEL_SELECTION.md).
- [тесты компонента](../../../ai/tests/test_group_findings.py).
- [план](../../../docs/plans/ai-group-findings.md).
- [генератор контролей](build_cases.py).
- [контроли](cases.json).
- [пример запроса](compatible.request.json).
- [пример ответа](compatible.response.json).
- [интеграция replay с существующим runner](replay.py).
- [этот отчёт](VALIDATION.md).

Git-результат фиксируется отдельным feature-коммитом; его точный SHA доступен
через `git log -1 feat/ai-group-findings` и в итоговом сообщении. Push и merge
не выполнялись. Схемы/сохранённые одобрения/таблицы/API F2 не менялись.
