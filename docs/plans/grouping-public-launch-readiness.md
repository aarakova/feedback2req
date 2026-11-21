# Готовность публичного запуска группировки — 2026-11-21

Задача: продолжить F2/F3, проверить пакет A и существующие согласования;
подготовить окончательный контракт до отдельного утверждения, не включать
несогласованный POST. Пользователь отдельно запретил push, merge в main и
внешние AI-вызовы. Этот отчёт не расширяет согласования.

## База и уже выполненная работа

Проверены ветки и рабочие деревья; preview/workspace a866b4e не содержит полного
интеграционного результата и не используется для новой работы.
Проверенные удалённые SHA (read-only ls-remote, 2026-11-21):

| Ветка | SHA | Назначение |
|---|---|---|
| main | 410b936e451629a53ca1eb0fb15a4908961155b6 | Общая AI foundation, не полный Observer workflow |
| integration/full-workflow-ui | 600065626be5e671223c8a8afd696a14bb4c20e5 | Согласованная INT база с F1/F2/F3 и чтением групп |
| feat/backend-grouping-orchestration | be328080cbeb484b3e2b77866709775627884d98 | Готовые internal enqueue/worker и предложение POST A.1 |

Новая локальная ветка feat/backend-grouping-public-contract и отдельное worktree
созданы **от 6000656**, без переноса чужих незакоммиченных изменений. Исходные
ветки/рабочие деревья, контейнеры и БД не изменялись. Удалённых изменений нет.
Для создания своей git ref/worktree использовано обычное tool approval, поскольку
sandbox не разрешил запись в .git; защиты/политики не отключались.

DEC-016 разрешил F2 storage/read/приём, поправка от 2026-11-06 — annotations
на явно переданные previous_groups. DEC-017 разрешил внутреннюю очередь F3.
INT-2026-11-06 разрешил интеграцию готовых компонентов и **явно не утвердил**
POST group_findings. Пакет A в integration HEAD по-прежнему PROPOSED. Другого
утверждения публичного запуска в проверенном журнале нет.

## Выполнено в этой ветке

- Пакет A сверен с кодом интеграционной базы и оформлен как
  [окончательная редакция 2](grouping-run-api-proposed.md), всё ещё PROPOSED.
- Уточнены closed DTO/types/bounds, snapshot 202/COMMIT, default arrays, UUID/
  order canonicalization, replay после смены states и привязка к initiator.
- Зафиксирован transaction-aware стык с уже проверенным Actor/Tx: нельзя открывать
  вложенную сессию с повторной auth, когда внешняя транзакция обновляет last_seen.
  Это риск, выявленный статически; PG-воспроизведение в этой работе не выполнялось.
- [Frontend handoff](../proposals/grouping-launch-frontend.md) содержит точные
  ошибки, pending/same-key recovery, терминальные states и 27 сценариев приёмки.
- [JSON-примеры](../proposals/grouping-launch-examples.json) показывают request,
  queued Run, completed без групп с questions/ungrouped/coverage, provider failure
  и безопасный envelope неизвестного исхода. Все UUID и данные синтетические.
- Пакет A/B/C ссылается на A.2; части B/C сохранены без изменений.

Runtime handler/DTO и storage/queue не реализовывались заново. После отдельного
утверждения A.2 требуется только HTTP-стык с существующей подготовкой, не новый
Run lifecycle, endpoint чтения или provider. Current POST остаётся F1-only.

## Проверки этой подготовки

PASS, 2026-11-21, встроенные read-only команды PowerShell/Git, собственные fixtures:

- JSON синтаксис, UUID записей, точность selected states в queued input,
  coverage/input mapping и ungrouped refs в completed без групп.
- Точная previous-group ссылка вопроса, synthetic/ai_performed, отсутствие
  принятого coverage при provider_not_configured и согласованность X-Request-ID.
- 27 отдельных строк сценариев A01–A27 и 12 локальных Markdown targets.
- Публичный Start.operation в проверенном исходнике по-прежнему F1-only.
  Это статическая проверка source gate, не выполненный HTTP-тест.
- Части B/C сравнены с 6000656 и побайтно совпадают после нормализации CRLF/LF.
- git diff --check; runtime/backend/frontend/AI contracts не изменены.

Эти проверки подтверждают согласованность подготовленных артефактов, не работу
будущего POST. Политики запуска скриптов не отключались; отдельный ps1 checker
не включён в результат. Данные примеров не относятся к существующей базе.

При фиксации 639f1e4 PostgreSQL/API/worker/browser проверки не выполнялись:
Docker CLI не был найден в обычном PATH, root .venv ссылается на отсутствующий
Python312 другого пользователя. Это состояние исходного отчёта, не утверждение
о невозможности Docker-проверок после дополнительного поиска ниже. Зависимости,
execution policy и чужие тестовые стенды не изменялись.

## Дополнительная проверка готовых F2/F3 — 2026-11-21

После пользовательского «продолжи» повторно проверены refs и записи решений,
в том числе DECISIONS из integration/readiness-20261121. Публичный POST всё ещё
явно не утверждён. Запрошено одно подтверждение принятия A.2; отсутствие ответа
не трактуется как согласие. Контракт и runtime при этих проверках не менялись.

Docker CLI найден в установленном пользовательском Docker Desktop вне обычного
sandbox PATH. Собственный project `f2r-a2-639f1e4-20261121`, новая сеть/PG volume,
PostgreSQL без опубликованных портов. Чужие контейнеры не останавливались и
не пересоздавались. Исходники подключены read-only; результаты — в собственном
игнорируемом `.local/validation/a2-20261121/f2-f3-regression.xml`.

Тестовый образ закреплён по content ID:
`sha256:0c154beef3fd4f49181dafba8fabc4f4c3211aa2110e4c966bf686cdc23b9379`.
Python 3.12.15, jsonschema 4.26.0, Pydantic 2.14.1, SQLAlchemy 2.0.55,
pytest 9.1.1. Host venv не ремонтировался и не использовался.

- **PASS: 64 tests**, 440.52 s, `-W error`, PostgreSQL, без пропусков:
  `test_grouping_queue.py`, `test_grouping_execution.py`,
  `test_grouping_previous_annotations.py`.
- Проверены существующая очередь с настоящими worker-процессами, конкуренция,
  idempotency/replay, запись и rollback при неизвестном COMMIT, revoke/stale
  context, restart/recovery, lease/deadline, exact historical annotations и GET.
  Сохранён существующий запрет публичного grouping POST. Tests не изменялись.
- **PASS:** canonical AI projection примера completed без групп из JSON fixtures
  проверена по неизменённой group_findings.response Schema 1.0. Из backend DTO
  related исключены добавляемые сервером kind/id/state_id; это проверка формы
  AI-response, не валидация нового HTTP request и не semantic evaluation.
- Внешние AI-вызовы не выполнялись: offline fixture-check без сети, PG tests
  используют явные synthetic/injected adapters. Вся работа без push и merge.

**NOT RUN:** A01–A27 через новый публичный POST, browser acceptance,
полный backend/F1 suite, независимое ревью и реальная модель. 64 существующих
F2/F3 теста не объявляются приёмкой неутверждённого HTTP-контракта. Данные и
серверные файлы других агентов не менялись; собственный тестовый стенд сохранён.

## Зависимости и следующий шаг

Для реализации нужно одно явное решение: утверждение пакета A редакции 2,
включая HTTP shape/types/limits, transaction snapshot, deferred provider failure
и отсутствие TTL/retry/cancel. Для synthetic приёмки не нужны B/C, генерация
требований или реальная модель. Не решённые B/C не являются разрешением их менять.

После утверждения: transaction-aware reuse enqueue → discriminated POST DTO с
сохранением F1 → изолированные PG/HTTP проверки матрицы и неизвестного COMMIT →
handoff для отдельного подключения frontend. Synthetic отмечается явно;
Qwen/model/передача данных требуют собственного решения. Push/merge по-прежнему
запрещены текущим заданием.
