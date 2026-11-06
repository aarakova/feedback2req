# Внутренний запуск группировки F3

Реализовано по разрешению Backend F3 от 2026-11-06 (DEC-017).
HTTP POST `/runs` пока принимает только F1 операции. Будущий контракт —
[PROPOSED](plans/grouping-run-api-proposed.md), требует отдельного утверждения.
F2 хранение, DTO чтения, AI 1.0 и правила annotations сохранены.

## Создание и выполнение

```python
from feedback2req.grouping.service import enqueue_grouping

handle = enqueue_grouping(
    sessions, identity, session_token, project_id, command_key, finding_refs,
    document_refs=document_refs, previous_group_refs=previous_group_refs,
)
# run_id, unit_id, attempt_id=None, request=None, owner_token=None, replayed
```

Session token аутентифицируется только при создании. В БД сохраняются
Run.initiated_by, fingerprint, queued Unit и typed exact refs. Attempt/capability
и provider metadata отсутствуют до claim. GET Run доступен сразу: одна Unit
на весь набор, attempt=null. Пределы: 1–100 findings, 0–16 document excerpts,
0–16 previous groups; 1 MiB канонического контекста без урезания/дозагрузки.
Внутренние refs совпадают с prepare F2 (kind необязателен в Python интерфейсе).
Повтор enqueue после unknown COMMIT использует прежний ключ; enqueue не вызывает AI.

Entry point `python -m feedback2req.processing.worker` и bounded child `--once`
переиспользованы. execute_pass сначала обслуживает одну F1 unit; если F1 работы
нет — пробует grouping. При непрерывной F1 нагрузке справедливость не гарантируется.
Worker не получает пользовательскую сессию. Для явного disposable test сценария
задаётся одно значение F2R_GROUPING_SYNTHETIC_SCENARIO:

| Значение | Результат |
|---|---|
| one | Одна synthetic группа; тестовые противоположные позиции при двух findings |
| many | Две synthetic группы; M:N membership |
| ungrouped | Успех без групп, все findings явно негруппированные |
| invalid | Невалидный ответ, failed/invalid_response |
| error | Ошибка транспорта, failed/provider_error |

Метки synthetic=true/ai_performed=false. Эти fixtures не выполняют смысловую
группировку. По умолчанию UnconfiguredGrouping завершает attempt как
failed/provider_not_configured, ai_performed=false. F1 AI-настройки не включают
реальную группировку. Fallback на synthetic при ошибках отсутствует.

Claim выбирает только queued finding_set с operation=group_findings. Под
Project → Unit → Attempt locks повторно проверяется queued и создаётся
единственная running Attempt с provenance и SHA-256 capability. UNIQUE(unit_id),
locks и recheck исключают второй захват. При конкуренции проигравший может
подождать и вернуть no work; порядок блокировок не заменён SKIP LOCKED.
БД сохраняет существующие connection/statement/transaction/lock timeouts.

До COMMIT claim проверяет инициатора и контекст F2 current/build_request;
F1 current_input не используется. Только подтверждённый COMMIT возвращает
capability. Затем execute_prepared_grouping использует обязательный DB verifier,
heartbeat 5 s / lease 30 s / deadline 120 s и атомарные F2 accept/fail.
Inference проходит без Project lock. Предыдущие группы/человеческие решения
не обновляются; completed не означает полный semantic coverage.

## Прерывания и совместимость

Unknown claim COMMIT запрещает вызов provider. Если claim сохранился, Attempt
остаётся running до recovery; если откатился — будущий worker может выполнить
первый claim. Unknown final COMMIT выходит из child без второй записи исхода.
recover_one завершает истёкшие Attempt failed/lease_expired или deadline_exceeded,
не возвращая их в queued. Повторного inference нет; потерянный ответ не восстанавливается.
Replay enqueue или synchronous execute читает прежнюю Unit без capability.
Retry finding_set через HTTP по-прежнему запрещён.

Очередь не имеет TTL; deadline начинается при claim. Прежний supervisor
PASS_SECONDS=135 ограничивает зависшее вычисление через terminate/kill.
Lease loss запрещает publish позднего ответа. Удалённая модель может продолжать
вычисление после закрытия клиента: серверная отмена требует отдельной проверки.

Миграция не нужна: M03 поддерживает queued finding_set, typed inputs до Attempt
и UNIQUE(unit_id). Общая подготовка выделена в один helper, compute переиспользуется
синхронной F2 и queued F3. Дополнительно исправлен duplicate document range после
раскрытия default locator: 422 вместо конфликта SQL для одинаковых excerpts.

## Подключение будущего проверенного Qwen

Точка настройки — [grouping_provider](../backend/feedback2req/grouping/provider.py).
Тесты передают provider в execute_queued_grouping напрямую. После отдельного
утверждения фабрика сможет вернуть существующий
`ai.group_findings.provider.Ollama(OllamaConfig(...))` или совместимый адаптер.
Production не импортирует experiments/qwen и не выбирает реальную модель.

| Область | Требование к адаптеру |
|---|---|
| Разрешение/адресат | Явно согласованные endpoint/model/условия и transfer_enabled; запрет ambient proxy/redirect и credentials в URL, согласованный TLS/локальный transport |
| Происхождение | provider/model/version/config revision однозначно идентифицируются в metadata (длины 64/128); synthetic не зависит от успешности ответа |
| Время | Один вызов без auto retry; timeout ≤60 s и в пределах оставшегося deadline, включая startup/IO/accept и supervisor 135 s |
| Размер | Request/response ≤1 MiB; ограничивать чтение до decode, проверять envelope и canonical JSON, ничего не обрезать |
| Данные | Только доверенный group_findings 1.0 после DB verifier; без автоматического добавления чужих проектов/групп; контент — данные, не инструкции |
| Ошибки | Без raw source/URL/SQL; безопасные GroupingError; нет скрытых retry/fallback, в том числе библиотечных |
| Отмена | Respect timeout и закрытие transport; kill child ограничивает клиент, серверную отмену проверить отдельно; lost capability всегда запрещает publish |
| Проверка | Failure injection, затем отдельно разрешённые реальные испытания с provenance и semantic evaluation; эксперименты не импортируются в production |

Реальная модель/параметры/адресат и разрешение передачи данных остаются отдельными
решениями. Результаты и ограничения — [отчёт F3](plans/backend-grouping-orchestration.md).
