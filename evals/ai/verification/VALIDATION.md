# Результаты verify_requirement 1.0

Дата: 2026-11-06. Ветка `feat/ai-verify-requirement`, свой worktree
`.local/worktrees/ai-verify-requirement`. После fetch локальная и опубликованная
база генератора совпали с `866b3c6333770efaf275177173627509b7defcd9`.
Проверены локальные/удалённые ветки: конкурирующей реализации не было.

Утверждённые schemas, evaluator, исходный набор S01–S14, группировка,
генератор, backend/F2, frontend, worker и PostgreSQL не изменены.
Новый модуль переиспользует общий парсер/transport и common input checks;
расширения существующих модулей в этой итерации не потребовались.

## Фактические результаты

Среда: существующий Docker image
`sha256:0c154beef3fd4f49181dafba8fabc4f4c3211aa2110e4c966bf686cdc23b9379`,
Python 3.12.15, jsonschema 4.26.0, referencing 0.37.0, Ruff 0.17.1.
Тесты/replay выполнялись с `--network none`, read-only исходниками и
отдельным write-mount только для локальных отчётов. Новые зависимости,
образы и веса не скачивались. Runtime не обращался к реальному провайдеру.

| Проверка | Результат |
|---|---|
| `python -B -W error -m unittest discover -s ai/tests -v` | **113 tests, OK**, 44.892 s: 44 verify + 32 generation + 37 grouping |
| `python -B -W error -m unittest discover -s evals/ai/tests -v` | **47 tests, OK**, 27.661 s |
| Исходный validator контрактов | PASS: 9 схем, 88 local refs, 38 positive / 34 negative examples, 399 unknown-field mutations, 20 пар |
| Новый verification replay | 18 исходных записей + 22 новых контроля + 2 смысловых контрпримера; 0 технических диагностик, exit 0 |
| Generation replay | 11 исходных записей + 15 контролей + 2 контрпримера; 0 технических диагностик, exit 0 |
| Grouping replay | 3 исходные записи + 8 контролей; 0 технических диагностик, exit 0 |
| Исходный controls replay | 46 записей, 46 экспертных листов pending, exit 0 |
| Исходный faults replay | 24 намеренные ошибки; ожидаемый exit 1; ожидаемые коды подтверждены исходными тестами |
| Ruff check / format --check | PASS; новые исходники и документация отформатированы |

Суммарно **160 unit-тестов**. Первый полный запуск до добавления проверки
insufficient/clean содержал 111 тестов и прошёл. После усиления приёма один
тест нарушал одновременно два ограничения и получил другой корректный код
отказа; условия теста разделены (completed + открытый новый вопрос), исходное
ожидание отказа не ослаблено. Дополнительно закреплён запрет чистого support
при полном отсутствии доступных фрагментов. Итоговые 113 тестов прошли.
Проверка evaluator повторно не запускалась после этой изолированной правки:
её код не менялся, финальный verification replay также прошёл.

В lint исключается только EXE002: Windows bind-mount показывает executable
независимо от Git mode. Python warnings не подавлялись. Диагностика не
выводит исходные тексты, сырые ответы или значения неизвестных полей.

Локальные результаты (не включены в Git):

- [Verification summary](../../../.local/verification-validation/verification-checked/summary.json).
- [Исходные verify-примеры](../../../.local/verification-validation/verification-checked/evaluation/report.md).
- [Экспертные листы новых контролей](../../../.local/verification-validation/verification-checked/additional-review.json).
- [Generation regression](../../../.local/verification-validation/generation-regression/summary.json).
- [Grouping regression](../../../.local/verification-validation/grouping-regression/summary.json).
- [Все controls](../../../.local/verification-validation/all-controls/report.md).
- [Намеренные faults](../../../.local/verification-validation/all-faults/report.md).

Существующая предварительная разметка не менялась. Намеренные смысловые ошибки
не превращены в позитивный эталон. Экспертные листы остаются pending.

## Воспроизведение

Из корня этого worktree с установленными зависимостями:

```text
python -B -W error -m unittest discover -s ai/tests -v
python -B -W error -m unittest discover -s evals/ai/tests -v
python -B scripts/validate_ai_contracts.py
python -B evals/ai/verification/replay.py --output evals/ai/results/verification-run
python -B evals/ai/generation/replay.py --output evals/ai/results/verification-generation-regression
python -B evals/ai/grouping/replay.py --output evals/ai/results/verification-grouping-regression
python -B evals/ai/cli.py replay --input evals/ai/datasets/synthetic-ru-v1/replays/controls.json --output evals/ai/results/verification-controls
python -B evals/ai/cli.py replay --input evals/ai/datasets/synthetic-ru-v1/replays/faults.json --output evals/ai/results/verification-faults
python -m ruff check --no-cache --ignore EXE002 ai evals/ai/verification
python -m ruff format --no-cache --check ai evals/ai/verification
```

Нативный Python в этой среде заменён запуском существующего image ID
`0c154beef3fd`, с bind-mount worktree → `/work,readonly`, `-w /work`,
`--entrypoint python`, `--network none`. Для replay отчёты имеют отдельный
write-mount. Каждый output — новый каталог. Точные CLI-примеры полного
и частичного результата: [README модуля](../../../ai/verify_requirement/README.md).

## Трассировка сценариев

| Требование задания | Синтетическое свидетельство |
|---|---|
| Поддержанная редакция, завершённое отсутствие замечаний | supported, full-scope |
| Неподтверждённое поведение и противоречие отзыву | unsupported, contradiction; исходные S09 |
| Разные условия и неоднозначность | different-conditions, ambiguity; S07 |
| Дубль другого требования, собственная редакция, pending_change | other-requirement-duplicate, own-revision; S13; мутации requirement_id/ролей/proposal_ref |
| Project snapshot / selected / пропущенное сравнение | full-scope, selected, empty-selected, missed-comparison |
| Утрата, ненадёжная речь, недостаток основания | all-deleted, uncertain-speech, insufficient-evidence; S12 |
| История, followup, решение, отдельная новая редакция | previous-open-blocker, followup, prior-decision, approved-change |
| Независимые обнаружения при partial | partial-found; найденное issue сохраняется при пропуске other2 |
| Нерассмотренная цель | not-processed; отдельный регрессионный тест unreviewed issues при пустых considered |
| Чужие/несовместимые ссылки и состояния | Schema/reference mutations и отказ обязательного verifier до провайдера |
| Инструкции в target/document | injection и transport separation; семантическая устойчивость модели не проверена |
| Severity отдельно от blocking | low-severity-blocker и тест high/false, low/true; программной таблицы преобразования нет |

Два явных смысловых контрпримера: пропущенное неподтверждённое положение и
ошибочный дубль разных поведений при корректных IDs. Они проходят технический
приём; отсутствие автоматического обнаружения этих ошибок проверено тестом.
Это демонстрация ограничения, а не вывод о качестве реального AI.

Из независимого ревью `7f9fca4` повторён сценарий дефекта evaluator:
substantive issues при not_processed с пустыми considered. Новый модуль его
отвергает. Старый инструмент и его четыре opt-in регрессии не исправлялись
и не объявляются прошедшими; исправление — отдельная задача.

## Непроверенное и граница ответственности

Нет реальной модели, внешних AI-вызовов, оценки русского языка, смысловой
поддержки каждого положения, достаточности, истинности конфликта/дубля или
обоснованности severity/blocking. Не проверена устойчивость реального inference
к injection, лимиты токенов, отсутствие серверного усечения и поддержка полной
схемы конкретной версией Ollama. Структурный PASS этого не доказывает.

Новый модуль не доказывает настоящие права, проектную принадлежность,
актуальность и достоверность истории: для этого обязателен backend verifier.
required_context — доверенная метаинформация обязательности полей, а не
самостоятельное обнаружение скрытой истории. Неизвестные refs решений/base
нужно проверять по хранилищу. ReviewPlan подтверждает только именованные
завершённые единицы, не частичное содержательное чтение текста.
Автоматических пакетов, агрегатора, retry, хранения или публикации нет.

Backend/F2/DB/worker/frontend интеграционные проверки не запускались: их код
не изменялся. Независимого ревью нового компонента в этой сессии не было;
выполнены самопроверка и перечисленные автоматические проверки.
Критерии будущей серверной интеграции и нового человеческого решения:
[PROPOSED handoff](../../../docs/proposals/verification-backend-handoff.md).

## Изменённые файлы

- [Публичный интерфейс](../../../ai/verify_requirement/__init__.py).
- [Сервис](../../../ai/verify_requirement/service.py).
- [Prompt](../../../ai/verify_requirement/prompt.py).
- [Провайдеры](../../../ai/verify_requirement/provider.py).
- [Приём](../../../ai/verify_requirement/validation.py).
- [CLI](../../../ai/verify_requirement/__main__.py).
- [Инструкция](../../../ai/verify_requirement/README.md).
- [Unit-тесты](../../../ai/tests/test_verify_requirement.py).
- [Генератор контролей](build_cases.py).
- [Манифест](manifest.json).
- [Завершённый вход](supported.request.json), [ответ](supported.response.json).
- [Частичный вход](partial.request.json), [ответ](partial.response.json), [план](partial.plan.json).
- [Replay](replay.py).
- [Этот отчёт](VALIDATION.md).
- [План](../../../docs/plans/ai-verify-requirement.md).
- [Предложение серверной интеграции](../../../docs/proposals/verification-backend-handoff.md).
- [Корневой README](../../../README.md): ссылка на новую операцию.

Логические коммиты разделяют реализацию/тесты и документацию/результаты.
Точные SHA и результат разрешённого push feature-ветки приводятся в итоговом
сообщении после выполнения. Merge не выполняется; production-готовность
и смысловое качество реальной модели не заявляются.
