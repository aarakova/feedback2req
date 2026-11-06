# Внутренняя интеграция F2 и group_findings

Статус: внутренняя интеграция реализована и проверена, 2026-11-04;
расширение ссылок annotations APPROVED и реализовано 2026-11-06.
Основание исходной интеграции: пользовательское
«продолжай» после предложения подключить AI-компонент к внутренней границе F2.
База backend: 20656819aad3a857875ec0d91a263d903c85638b.
Компонент: f5ffa486ccaee7ebefe169e7cca2430edda221c8 (feat/ai-group-findings).
Обе удалённые вершины проверены; чужие checkout не изменяются, merge нет.

Объём: перенести неизменённые runtime-файлы компонента и необходимые
автономные тестовые фикстуры; добавить внутренний исполнитель с обязательной
проверкой живого контекста, heartbeat, детерминированным приёмом F2 и
безопасным отображением ошибок. Нет публичного запуска, новых моделей,
сетевых AI-вызовов, генерации требований или изменения JSON Schema 1.0.

## Совместимость

Негруппированная finding является содержательным результатом (AI_CONTRACTS §7.2).
Дополнительная обязательная reason для completed+ungrouped в F2 — техническая
ошибка валидатора; её удаление восстанавливает совместимость, не меняя схему,
coverage, основание или права. Причины insufficient/not_processed сохраняются.

## Утверждённое расширение ссылок annotations

**APPROVED 2026-11-06**, явное сообщение пользователя, зафиксированное в
[DEC-016](../DECISIONS.md). Пакет F2 §4 п.7 ранее ограничивал related input
основной finding; компонент 1.0 уже допускает previous_groups и для questions,
и для uncertainties. Теперь оба типа поддерживаются финальным приёмом F2:

- Key проверяется только по findings/previous_groups этой Unit, без дозагрузки.
- Binding берётся из typed input: origin=input/key и точный kind=finding_group/id/state_id.
- Prepare проверяет project/group/state; build_request повторно проверяет
  membership, ожидаемый current state и свежесть зависимостей перед публикацией.
- Историческая ссылка остаётся точной после смены current state. Прежняя группа,
  её вопросы и конфликты не меняются, противоречия автоматически не разрешаются.
- Существующие finding/output ссылки сохранены, включая совпадающий key g1
  в разных origin. SQL-миграция и изменение AI Schema 1.0 не нужны.

## Реализованное подключение

[execute_grouping](../../backend/feedback2req/grouping/execution.py) принимает
явный provider и использует prepare → обязательный DB verifier → компонент →
accept/fail. Compute идёт без Project lock; heartbeat продлевает только живую
попытку, в пределах deadline. Финальный приём повторно проверяет права и входы.
Ошибки вычисления переводятся в безопасные существующие reason codes; ошибки
публикации/COMMIT выходят вызывающему коду. Replay прежнего command_key читает
сохранённую попытку и не вызывает provider заново.

Исправлен fail_grouping: при техническом отказе заново проверяется канонический
запрос, чтобы изменение входов давало cancelled/input_changed, как при accept.
Структура БД, HTTP endpoints и JSON Schema 1.0 этой интеграцией не меняются.
Точная инструкция вызова и result DTO — [спецификация API](../FINDING_GROUPS_API.md).

## Фактические проверки

Изолированный стенд: PostgreSQL 17, контейнер f2r-f2-dbf365b-01-db, отдельная
task-сеть/volume. Чужие контейнеры, volumes и checkout не изменялись.

| Проверка | Результат |
|---|---|
| Все backend PG/API/unit-тесты, включая F1 и M02b → M03 | PASS: 167, 285.18 s, `-W error` |
| Включённые в этот прогон тесты нового исполнителя | PASS: 18 |
| Исходные автономные тесты компонента, без сети | PASS: 37, 14.935 s, `-W error` |
| Git blob hash всех 13 перенесённых исходных файлов/фикстур | PASS: точное совпадение с f5ffa486 |
| Ruff backend | PASS |
| Контракты AI 1.0 | PASS: 9 схем, 88 refs, 38 positive / 34 negative, 399 mutations, 20 APP-пар |
| Сборка f2r-f2-integration-2065681:local | PASS |
| Синтетический CLI replay внутри нового образа, без сети | PASS |
| Импорт backend execute_grouping внутри нового образа, без сети | PASS |

Новый PG/API прогон подтверждает полный путь prepare → настоящий модуль с Replay
→ accept → GET с evidence и конфликтами, полностью ungrouped без дополнительной
reason, нулевое число групп при insufficient/not_processed, изменение входов до
и во время compute, heartbeat/lease/recovery, безопасные ошибки и неизвестный
prepare/final COMMIT без повторного provider call. На 2026-11-04 проверка
previous_groups подтверждала прежнюю политику; она заменена тестами ниже
после явного утверждения расширения.

Seed/restart/verify PostgreSQL и HTTP readiness ранее проверены в основной F2
итерации; в этой интеграции отдельно не повторялись. Старый Compose fault-прогон
живого F1-worker, внешний CI после push, независимое ревью и реальные AI-вызовы
в этой итерации NOT RUN. Synthetic fixtures не подтверждают смысловое качество.

## Ограничения и следующий шаг

Публичный запуск/очередь, frontend, human edits и генерация требований остаются
вне объёма. Реальный provider требует отдельного разрешения и настройки;
синхронный адаптер обязан ограничивать timeout deadline попытки. Компонент
ограничивает размер request/response 1 MiB, без урезания данных.

Открытых согласований в рамках этого расширения нет. Следующая небольшая
итерация может отдельно определить внутренний запуск группировки из worker
с ограничениями размера/timeout и синтетическим провайдером; до её утверждения
новая публичная команда или автоматический запуск не добавляются.

## Проверка расширения от 2026-11-06

В рабочем коде изменены только F2 validator и annotation binding. Новые
[PG/API tests](../../backend/tests/test_grouping_previous_annotations.py)
проверяют оба типа annotations, совместные finding/input-group/output-group
ссылки, невыбранные группы/ключи, чужой проект, отсутствующую группу/state,
state другой группы, устаревший контекст, отзыв доступа, replay и историческое
чтение после создания нового human state. Прямые INSERT проверяют составные FK.
[Тесты исполнителя](../../backend/tests/test_grouping_execution.py) проверяют
оба типа через неизменённый standalone компонент.

Проверки от 2026-11-06 на том же собственном стенде:

- База расширения: ee65b9ac5fd5e12b3936fb14c1432543bfcbf1ab.
- PASS: полный backend PG/API/unit-прогон — **187 tests**, 412.53 s,
  PostgreSQL 17.11, `-W error`, без пропусков. Включены F1, M02b → M03,
  lease/deadline, access/input changes, replay/unknown COMMIT и recovery.
- PASS: целевые PG/API проверки и исполнитель — 38 tests, 85.57 s, `-W error`.
  Они входят в полный backend-прогон, не прибавляются к 187.
- PASS: автономные upstream tests — 37 tests, 8.706 s, `-W error`, без сети,
  source mount read-only, отдельный tmpfs /tmp.
- PASS: контракты AI 1.0 — 9 схем / 88 refs, 38 positive / 34 negative examples,
  399 unknown-field mutations, 20 APP-пар; AI-файлы и Schema не менялись.
- PASS: Ruff check backend, format --check для изменённых Python-файлов,
  git diff --check.

Первый автономный прогон: 36 успешных тестов / 1 ERROR, потому что read-only
контейнер не имел writable temporary directory для CLI-теста. Исправлена только
команда тестового окружения (добавлен tmpfs /tmp); тесты и AI-компонент не менялись.
Повторный полный автономный прогон успешен. Ошибок в PG/API и полном backend
прогоне не было; после них рабочий код и тесты не менялись.

Повторяемые команды из собственного checkout (PostgreSQL-контейнер и сеть
должны принадлежать этой задаче):

```powershell
docker run --rm --network f2r-f2-dbf365b-01 -e PYTHONPATH=/workspace/backend -e F2R_TEST_DATABASE_URL=postgresql+psycopg://f2r_test@f2r-f2-dbf365b-01-db/feedback2req_f2_test --entrypoint python --mount "type=bind,source=$PWD,target=/workspace" -w /workspace feedback2req-checks:latest -m pytest backend/tests -q -W error --tb=short
docker run --rm --network none --read-only --tmpfs /tmp:rw --entrypoint python --mount "type=bind,source=$PWD,target=/workspace,readonly" -w /workspace feedback2req-checks:latest -B -W error -m unittest discover -s ai/tests -q
```

Независимое ревью, реальные AI-вызовы, повтор seed/restart, runtime image build/
HTTP readiness и отдельный Compose fault-прогон worker в этом расширении NOT RUN.
Результаты сборки/перезапуска выше относятся к предыдущей итерации, не к 2026-11-06.
