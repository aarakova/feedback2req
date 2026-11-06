# Проверки автономного Qwen → bridge → Z3 контура

Дата: 2026-11-06. База `9f3a1a0b440535ae1513e2bd64a7c9d1c62d58ee`.
Ветка `experiment/qwen-z3-expectations`. Реальный inference не выполнялся;
человеческая смысловая разметка не получена. Проверен инструмент на синтетике,
а не качество Qwen. References имеют статус PRELIMINARY_ENGINEERING_CONTROL.

## Среда и воспроизведение

Python 3.12.15, z3-solver/Z3 4.15.4.0, jsonschema 4.26.0,
referencing 0.37.0, Ruff 0.11.13. Зависимости production не менялись.
Команды из собственного worktree с установленными
[изолированными зависимостями](requirements.txt):

```text
python -B -m unittest discover -s experiments/qwen_z3/tests -v
python -B -m unittest discover -s ai/formal_expectations/tests -v
python -B -m unittest discover -s ai/formal_expectations_bridge/tests -v
python -B -m unittest discover -s ai/tests -v
ruff check --no-cache experiments/qwen_z3
ruff format --no-cache --check experiments/qwen_z3
```

На машине host Python отсутствовал как рабочий interpreter. Проверки запускались
в имеющемся Docker image
`sha256:0c154beef3fd4f49181dafba8fabc4f4c3211aa2110e4c966bf686cdc23b9379`,
без сети (`--network none`). Имеющееся отдельное Linux окружение прежнего
формального модуля подключалось **read-only** в `/env`, собственный worktree —
в `/workspace`; `PYTHONPATH=/env/lib/python3.12/site-packages:/workspace`.
Python entrypoint — `python`, Ruff — `/env/bin/ruff`. Другие worktree не менялись.

## Результаты

| Проверка | Результат |
|---|---|
| Новый эксперимент | 28 тестов PASS, 75.599 s |
| Прежний formal engine | 33 теста PASS, 28.779 s |
| Прежний bridge | 27 тестов PASS, 18.594 s |
| ai/tests: группировка и AI regression | 37 тестов PASS, 8.766 s |
| Итого | 125 тестов PASS |
| Ruff check и format | PASS |
| AI contract validator | 9 schemas, 88 local refs; 38 positive, 34 negative; 399 unknown-field mutations, 20 fixture pairs — PASS |
| Защищённые AI/backend/frontend/contracts/results-proposal | Нулевой diff относительно базы |
| Независимое read-only ревью | Завершено; замечание P2 устранено, новых findings нет |

Старые 97 тестов запускались отдельно; старый код/его зависимости затем не менялись.
После двух заключительных исправлений полностью повторён новый suite 28 тестов.
Contract validator проверяет схемы и fixtures, не права доступа и реальную БД.

Новый suite включает: закрытую схему и запрет self-approval/origin, сохранение
байтов, exact state/evidence/full-position links, отсутствие исправления
выдуманных чисел и ложного K/D, decimal и единицы, неполное Ω, привязку review
к raw/model/attempt/dataset/packet, pending/rejected/uncertain, технические
unknown/timeout/resource без U, escape через пути/symlink, лимиты до чтения,
CLI и сохранённый ответ → отдельный review → прежний Z3. Смоделированное
принятие экспертом существует только внутри теста; оно не является реальной
экспертной разметкой и не предоставляет CLI auto-approve.

## Воспроизводимая контрольная серия

Экспорт/синтетические manifest/replay сохранены локально в
`.local/qwen-z3-validation-01/`; команды CLI — в [README](README.md).
Dataset SHA-256:
`9e2d3648bd827da7e1355fd65dc066d091015f0fddc25ac0406cfbf9171224ed`.
Идентификаторы и raw hashes фиксируются в каждом manifest/report.

| Серия | Записи | Исходы |
|---|---|---|
| Exact registered engineering controls | 22 | 19 formal_conclusion: D=1, K=9, S=7, U=2; 2 model_abstained; 1 incomplete_omega |
| Негативные предложения | 9 | 1 formalization_error, 4 review_required, 2 provenance_error, 1 structure_error, 1 syntax_error; формальных классов нет |

В каждом результате `semantic_accuracy=null`; все смысловые критерии
unreviewed. Совпадение Z3 с ожидаемым классом структуры не доказывает верность
извлечения из текста. У control replay ожидаемый exit 1 из-за incomplete_omega;
у negative replay exit 1 из-за ошибок/pending, а не из-за падения unit suite.

Негативы покрывают неверный параметр, потерю условий, выдуманное значение,
ложное disjoint, усечённое Ω с заявлением полноты, сокращение позиции до одной
находки, self-approval, подмену state и повреждение JSON. Семантически ложные,
но структурно допустимые ответы остаются pending; эксперт может их отклонить.
Автоматического детектора смысла здесь нет.

## Ревью и границы доказательств

Независимый reviewer прочитал реализацию, тесты и документацию; тесты сам
не запускал. Выявленное P2: collect ограничивал число записей после чтения.
Теперь bounded islice читает максимум 257 ID и проверяет лимит 256, уникальность,
известность и attempt **до** файлов; добавлен тест. Дополнительно исходная
syntax/structure/preparation ошибка сохраняется при неверном review, который
записывается отдельно как review_diagnostic; добавлен тест.

Первоначальная гипотеза reviewer о decimal-regex отозвана после проверки
escaping: дефекта не было. Не учитывается как исправленная ошибка.

Не проведены реальные inference, человеческая семантическая оценка,
проверка живого F2/HTTP/постоянного хранения/permissions и production интеграция.
Результат попарный в прежней ограниченной модели; не доказательство глобальной
совместимости, полноты реального мира или правильности интерпретации отзывов.
Локальный review file требует доверенного назначения вызывающим человеком;
криптографической аутентификации эксперта инструмент не предоставляет.
