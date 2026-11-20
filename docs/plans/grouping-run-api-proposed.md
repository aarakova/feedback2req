# Публичный запуск group_findings — PROPOSED

**Пакет A, окончательная редакция 2 от 2026-11-21 — PROPOSED.**
**Не утверждено и не реализовано в HTTP.** Основание подготовки — продолжение
F2/F3 пользователем, не разрешение нового API. Утверждён внутренний enqueue/worker
(DEC-017), а INT-2026-11-06 явно оставляет публичный запуск несогласованным.
Интеграционная база: 600065626be5e671223c8a8afd696a14bb4c20e5.
Редакция 1 сохранена в be328080cbeb484b3e2b77866709775627884d98; редакция 2
заменяет её только как предложение пакета A. Пакеты B/C не меняются.
AI JSON Schema 1.0, хранилище и очередь не меняются.

[Передача frontend и критерии приёмки](../proposals/grouping-launch-frontend.md),
[синтетические примеры](../proposals/grouping-launch-examples.json).

## Команда

Расширить POST `/api/v1/projects/{project_id}/runs` закрытой discriminated union
по operation. Старые inspect_text/extract_feedback DTO остаются прежними.
Новая ветка:

```json
{
  "operation": "group_findings",
  "finding_refs": [{"kind": "finding", "id": "<UUID>", "state_id": "<UUID>"}],
  "document_refs": [{"kind": "product_document", "id": "<UUID>", "state_id": "<UUID>",
                     "locator": {"start": 0, "end": 120}}],
  "previous_group_refs": [{"kind": "finding_group", "id": "<UUID>", "state_id": "<UUID>"}]
}
```

FindingRef: kind/id/state_id обязательны; сейчас immutable F1 state_id=id.
DocumentRef: kind/id/state_id обязательны, locator необязателен (весь выбранный
документ); start/end — целые смещения Unicode [start,end), 0 ≤ start < end ≤ len.
PreviousGroupRef: kind/id/state_id обязательны; состояние принадлежит именно этой
группе. document_refs/previous_group_refs по умолчанию []; null запрещён.
UUID канонизируются; неизвестные поля отклоняются. Тексты, provider/model,
synthetic/инициатор, lease и permanent output IDs клиент не задаёт.
В новой ветке все refs — JSON-объекты, id/state_id — строки UUID в записи
8-4-4-4-12 (регистр hex незначим). kind — точный литерал из примера.
Отсутствие finding_refs, null вместо массива/объекта, строка/boolean вместо
целого locator и дополнительные поля дают 422 invalid_request. В HTTP DTO
locator.start/end принимаются как целые JSON-числа без coercion из строк/boolean;
записи с десятичной точкой/экспонентой (включая 1.0 и 1e0) отклоняются как
422 invalid_request. После разбора в enqueue передаются Python int. Отрицательный/пустой/выходящий
за текст диапазон — 422 invalid_input. Для F1 новые ограничения не вводятся.

## Лимиты и доверенный контекст

- 1–100 уникальных findings, 0–16 document excerpts, 0–16 previous groups.
- Finding/group UUID не повторяются; одинаковые разрешённые document ranges,
  включая алиас «весь документ»/явный полный range, отклоняются. Разные excerpts
  одного документа разрешены; перекрытие само по себе не ошибка.
- Все refs одного проекта, доступны инициатору; выбранные source/document/
  previous-group states должны оставаться ожидаемыми и свежими. Исторический
  state никогда не подменяется текущим. Отсутствующие зависимости не дозагружаются.
- Members previous_groups должны входить в явный finding_refs. Findings несут
  сохранённые fragments/source refs. Документы/группы — контекст, не evidence.
- HTTP body ограничен действующим F2R_MAX_BODY_BYTES (16 KiB по умолчанию):
  достижение лимитов количества не гарантирует, что тело поместится. Расширение
  общего HTTP лимита этим предложением не требуется.
- Серверный канонический group_findings request и ответ компонента — максимум
  1 MiB каждый; данные не обрезаются и не сегментируются автоматически.
  Непригодный контекст отклоняется до enqueue, а изменение после enqueue
  проверяется worker и финальным приёмом. Каждый finding рассматривается целиком.

## Доступ, idempotency и ошибки до 202

Текущая сессия Member/Owner/Approver проекта; can_approve не требуется для
технического запуска. Для POST действуют прежние Origin/X-CSRF-Token и UUID
Idempotency-Key. Session token используется только для аутентификации и не
сохраняется в очереди. Инициатор сохраняется в Run.

Область ключа: project/initiator/command_kind=start, общая с F1. Fingerprint
включает operation и канонические refs/ranges, порядок наборов несущественен.
Отсутствие locator и явный полный range в двух разных командах считаются разными
телами (409 при том же ключе), поскольку fingerprint не зависит от загрузки текста.
Тот же ключ/тело возвращает текущий прежний Run, даже terminal, без повторного
AI-вызова; доступ проверяется заново. Сетевой отказ/неизвестный enqueue COMMIT:
повторить ту же команду/ключ либо прочитать известный run_id; новый ключ не создавать
автоматически. Повтор может найти queued Run — это не команда повторить inference.

Пропущенные optional массивы и [] канонизируются одинаково. Регистр UUID и
перестановка элементов не меняют команду; дубликаты не удаляются молча, а
отклоняются. Запрос replay сначала проходит действующую аутентификацию,
проверку членства и структурную валидацию; совпавший сохранённый fingerprint
возвращает прежний Run **без** повторной проверки свежести его исторических
входов. После изменения source/state такой replay остаётся чтением результата.
Свежесть обязательна для нового start и worker/publish, а не для переписывания
истории. Выполнение от другого initiator — другая область ключа, поэтому
frontend никогда не повторяет pending команду автоматически под другой учётной записью.

| HTTP / code | Условие |
|---|---|
| 401 unauthenticated | Нет действующей сессии |
| 403 origin_rejected | Отсутствующий/неверный Origin |
| 403 csrf_rejected | Отсутствующий/неверный X-CSRF-Token |
| 404 not_found | Недоступный/неизвестный проект, объект, state или state другой группы |
| 409 input_changed | Выбранный контекст уже устарел |
| 409 idempotency_conflict | Тот же ключ, другая команда/состав |
| 413 body_too_large | Превышен общий HTTP body limit |
| 422 invalid_request | Неверный DTO/UUID/header/тип, неизвестные поля, размеры массивов вне bounds |
| 422 invalid_input | Дубликаты, диапазоны, предел canonical context, незамкнутые previous groups |
| 500 internal_error | Ошибка БД, включая неподтверждённый COMMIT; исход неизвестен |

Сохраняется общий envelope `{error:{code,message,details:{},request_id}}`, безопасные тексты,
no-store/X-Request-ID. Чужой объект не отличается от отсутствующего.
Таблица предполагает корректность остальных prerequisites. При нескольких
нарушениях сохраняется приоритет текущих middleware/dependencies: нельзя
использовать ошибку DTO для раскрытия существования недоступного объекта.

## Ответ 202 и чтение

Ответ — существующий Run DTO; 202 означает сохранённую команду, не успех AI.

```text
Run = {id,operation:"group_findings",created_at,execution_kind:"semantic",state,units:[Unit]}
Unit = {id,input:{kind:"finding_set",findings:[StateRef],documents:[StateRef],
                 previous_groups:[StateRef]},state,retry_of_attempt_id:null,attempt:null|Attempt}
StateRef = {kind,id,state_id}
Attempt = {id,request_id,state,started_at,finished_at,reason_code,provider,model,
           synthetic,ai_performed,coverage,annotations,finding_ids:[],fragment_ids:[],
           technical_result:null,grouping_result:null|GroupingResult}
GroupingResult = {group_ids:[UUID],ungrouped_findings:[StateRef],input_findings:[{key,ref:StateRef}]}
```

Ровно одна Unit на весь набор. Тело 202 — snapshot Run внутри транзакции команды:
для нового start queued/attempt=null, для replay — сохранённое состояние на момент
чтения. HTTP 202 отправляется только после подтверждённого COMMIT, как в F1.
К получению тела клиентом worker уже может продвинуть состояние, поэтому
последующие GET авторитетнее старого 202. Дополнительный post-commit GET внутри
обработчика не требуется; replay terminal Run тоже возвращает HTTP 202.
Поля coverage/annotations nullable до приёма; видимые StateRef не содержат capability.
Точные CoverageItem/annotations/GroupDetail — действующая
[спецификация F2](../FINDING_GROUPS_API.md). Doc excerpt ranges сохраняются
в typed inputs и читаются в GroupDetail.context, если включены в результат;
Unit.input.documents отражает refs без ranges (существующий DTO, не полный echo команды).

GET `/runs` и `/runs/{run_id}` возвращают состояние, coverage, вопросы и
ungrouped даже при group_ids=[]. GET `/groups` и exact-state GET показывают
принятые группы с evidence. Фильтр attempt_id связывает список с попыткой.
Новый endpoint чтения/альтернативное хранилище не нужны.

## Lifecycle, недоступный провайдер и retry

Действующие states: Unit/Run queued → running → completed/failed/cancelled.
Attempt создаётся running; queued относится к Unit. У общего Run также есть
partial для других операций, но одна grouping Unit его не создаёт.
Lease 30 s, heartbeat 5 s, deadline 120 s от claim; очередь пока не имеет TTL.
После неизвестного claim COMMIT provider не вызывается; истёкшая running Attempt
становится failed, не возвращается в queued. После unknown final COMMIT читать
сохранённый исход; автоматического inference/requeue нет.

Без настроенного провайдера задание принимается, затем failed/provider_not_configured,
ai_performed=false. Ошибки transport/timeout → provider_error, невалидный ответ →
invalid_response, прочие compute-ошибки → execution_error. Истечение → lease_expired/
deadline_exceeded. Изменение контекста/отзыв доступа → cancelled/input_changed или
access_revoked. Ни ошибка, ни отсутствие провайдера не включают synthetic fallback.
synthetic=true/ai_performed=false допустимы только при явном тестовом адаптере.
Реальный provider/model не включаются публичным DTO и требуют отдельного решения.

completed — успешный технический приём; semantic coverage читается отдельно,
даже если все findings insufficient/not_processed или нет групп.
Retry grouping пока **не предлагается**: существующий POST `/units/{id}/retries`
для finding_set сохраняет 409 retry_not_allowed. После failed/cancelled человек
может явно создать новый start с новым ключом и свежими refs; это сознательный
новый model call. Старые группы и человеческие решения не переписываются.
Нового публичного cancel API в этой ревизии нет.

## Транзакционный стык после утверждения

Нельзя просто вызвать sessions-based enqueue из существующего handler с открытыми
Actor/Tx. Identity.authenticate обновляет Session.last_seen_at; новая отдельная
сессия с повторной аутентификацией может ждать блокировку внешней транзакции.
Это выявленный по коду риск подключения, не новый воспроизведённый PG-дефект.

Конкретный способ подключения: сохранить существующие Actor/Tx и Origin/CSRF;
добавить тонкий transaction-aware вход в существующую подготовку enqueue,
принимающий уже проверенный actor_id и текущий tx. Внутренний sessions/token
enqueue остаётся wrapper для F3. Общая подготовка Run/Unit/typed refs используется
одна, новый lifecycle или очередь не создаются. В ветке group handler:
require_project(write=True) → lookup fingerprint/replay либо queued creation →
run_view(tx, run). COMMIT выполняет существующая function-scoped Tx dependency
до отправки ответа. Actor берётся только из сессии; token не сохраняется.
После неясного COMMIT не создавать второй outcome или новый ключ.

Worker видит только committed Unit, а transport запускается после подтверждённого
COMMIT claim. HTTP-транзакция не держит блокировки во время inference.
Тест стыка должен проверять успешный POST под настоящей сессией без self-wait,
rollback без queued строк и unknown COMMIT в обоих исходах. Этот вход, DTO и
handler будут реализованы **только после** утверждения редакции 2.

## Изменения относительно редакции 1

Уточнены: snapshot 202 и граница COMMIT вместо post-commit чтения; стык Actor/Tx
без вложенной auth-транзакции; строгие типы refs/locator; default=[] и UUID/order
канонизация; replay исторических входов и привязка pending команды к initiator.
Лимиты, набор refs, error codes, provider_not_configured, отсутствие retry/cancel/
TTL, AI 1.0 и worker lifecycle сохранены. Это предложение целиком заменяет A.1;
утверждение только части требует явного перечисления принятой области.

## Что согласовать и следующий этап

Нужно отдельно утвердить эту ветку POST DTO и семантику целиком, включая лимиты,
необязательные excerpts, deferred provider_not_configured, отсутствие TTL/retry/
публичной отмены. Открытых вариантов внутри документа нет: выше предложено
конкретное поведение. Qwen/model/адресат/условия передачи — отдельное согласование.

После утверждения: добавить discriminated DTO и route delegation в enqueue,
контрактные HTTP/CSRF/idempotency tests, затем отдельную frontend-итерацию:
выбор exact refs → ключ/команда → GET polling/history → groups/coverage/questions.
После unknown outcome frontend повторяет тот же ключ; не повторяет model call
новым ключом автоматически и не выдаёт completed за полноту анализа проекта.
