# Backend F3: внутренняя orchestration группировки

Статус: внутренняя orchestration реализована и проверена;
2026-11-06. Основание: явное поручение пользователя
«Backend F3: подготовка фонового запуска группировки на основе готового F2».
База 4c62684e7769d2c3a71de3264aa15e954a1262d0, чистый F2 checkout.
Коммит реализации: f84b91e61ad6b11eb215d279c8c9b632b6c54ac8.
Рабочая ветка feat/backend-grouping-orchestration; отдельный worktree.
Удалённый main cfb96f45ecbe2ef8487c1dd145cb081f3a90aec9 проверен 2026-11-06:
7 коммитов только в базе F2, 10 только в main; merge не выполняется.

## Разрешённая реализация

1. Аутентифицированный enqueue сохраняет Run и queued finding_set Unit с
   существующими typed refs. Session token не сохраняется. Attempt отсутствует.
2. Worker под блокировками Project → Unit → Attempt создаёт единственную
   running Attempt и capability; только подтверждённый COMMIT разрешает compute.
3. F2 build_request/heartbeat/accept/fail и общий recover_one переиспользуются.
   Claim не вызывает F1 current_input. Блокировок во время inference нет.
4. Истёкшая/прерванная попытка становится failed; автоматического повторного
   model call нет. Неизвестный claim/final COMMIT выходит из worker pass.
5. Worker использует явный synthetic test adapter либо provider_not_configured.
   Переключаемая граница готовится без выбора реальной модели и экспериментов.
6. Публичный POST и retry не меняются; будущие DTO документируются PROPOSED.

Новая миграция не нужна: M03 уже поддерживает queued finding_set, typed input
tables и отдельное создание Attempt с UNIQUE(unit_id). Provenance появляется
в момент назначения конкретному worker; второй lifecycle/таблица очереди не нужны.
Совместимость существующего prepare/execute F2 и queued replay проверяется отдельно.

## Проверки

На собственном изолированном PostgreSQL: несколько findings/контекстов, разные
формы успешного результата, конфликт/ungrouped, idempotency, конкурирующие worker,
отзыв прав, stale source/previous group, перезапуск процесса, lease/deadline,
неизвестный enqueue/claim/final COMMIT, invalid/provider error, GET read и
недоступность нового POST. Затем полный F1/F2/backend suite, AI contracts и
standalone tests. Реальные AI-вызовы и смысловое качество не проверяются.

## Реализовано

- [enqueue_grouping](../../backend/feedback2req/grouping/service.py) переиспользует
  общую с prepare подготовку, но сохраняет queued Unit без Attempt/capability.
  Лимиты 100 findings / 16 excerpts / 16 previous groups и 1 MiB проверяются
  до COMMIT. Для проверки канонического контекста до Attempt используется
  unit.id как временный request_id; в AI он не передаётся. При claim появляется
  настоящий Attempt.request_id.
- [claim/execute_queued_grouping](../../backend/feedback2req/grouping/queue.py)
  переиспользуют locks/ownership и общий recover_one. Executor F2 выделен для
  новой подтверждённой capability без повторной аутентификации пользовательской сессии.
- [worker.execute_pass](../../backend/feedback2req/processing/worker.py) сохраняет
  F1 приоритет и отдельно обрабатывает queued finding_set. Один compute на pass.
- [provider factory](../../backend/feedback2req/grouping/provider.py) имеет только
  явные synthetic test сценарии и UnconfiguredGrouping. Никаких real calls или
  fallback; эксперименты Qwen не импортируются.
- Duplicate whole-document/explicit-full-range alias теперь даёт invalid_input
  вместо SQL-конфликта. Это техническая проверка целостности, не смена правил.

Подробный [внутренний интерфейс](../GROUPING_ORCHESTRATION.md), требования к
сменному Qwen-адаптеру и ограничения описаны отдельно. [Публичный POST](grouping-run-api-proposed.md)
полностью специфицирован, но остаётся PROPOSED и не включён в routing/DTO.

## Фактические проверки

- PASS: начальный целевой прогон queue + F2 execution — 38 tests, 240.08 s.
- PASS: уточнённые queue tests с процессным restart/контекстом/лимитами —
  23 tests, 158.99 s. Затем добавлены ещё три проверки rollback/no fallback.
- PASS: полный backend — **213 tests**, failures=0/errors=0/skipped=0,
  416.263 s, PostgreSQL 17, `-W error`. Включены 26 F3 tests и прежние F1/F2,
  включая совместимость M02b→M03, security/materials/processing/worker/API.
  Результат прочитан из /state/f3-backend-final.xml собственного snapshot volume
  после утраты terminal session; полный отчёт существует, незавершённый прогон
  не объявлялся успешным.
- PASS: Ruff check backend и git diff --check.
- PASS: 37 автономных AI-компонент tests, 6.295 s, `-W error`, без сети;
  read-only исходники и отдельный tmpfs /tmp.
- PASS: AI contracts — 9 Draft 2020-12 schemas / 88 refs, 38 positive и
  34 negative examples, 399 unknown-field mutations, 20 APP fixture pairs.
- PASS: сборка f2r-f3-runtime-4c62684:local; импорт enqueue/claim/worker из
  установленного runtime-образа и synthetic fixture replay без сети.

Собственный стенд f2r-f3-20261106: отдельные db/snapshot volumes и сеть,
чужие контейнеры/volumes/checkout не менялись. После прерывания среды новые
команды build/standalone/contracts сначала не запускались из-за сбоя auto-review
(лимит использования, не unsafe verdict). После пользовательского продолжения
они запущены заново и успешно завершены. Ошибок тестов в финальном прогоне нет;
после него рабочий код и тесты не менялись, актуализировалась только документация.

## Ограничения и следующий шаг

В очереди нет TTL, при непрерывной F1 нагрузке нет гарантии справедливости.
После потерянного/истёкшего running Attempt нет автоматического повторного AI;
ответ может быть потерян. Публичные retry/cancel grouping не добавлены.
Supervisor ограничивает клиентский child, но не обещает серверную отмену Qwen.
Независимое ревью, реальные AI/semantic evaluation и отдельная прежняя extraction
Compose fault-матрица NOT RUN. Backend worker/runtime regressions входят в 213.
Frontend/AI 1.0/публичные POST не менялись; merge не выполнялся.

Для согласования остаётся только будущий публичный контракт (его DTO/лимиты,
deferred provider_not_configured, отсутствие TTL/retry/cancel) и отдельный
выбор модели/адресата/условий. Внутренняя реализация дополнительного согласования
не требует. Следующий этап после утверждения: DTO union → delegate enqueue →
HTTP acceptance/security tests → отдельное frontend-подключение выбора exact refs,
idempotency, GET polling/history, coverage/questions/groups.
