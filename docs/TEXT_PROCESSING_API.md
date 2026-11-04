# HTTP первого сквозного извлечения текста

Контракт реализации по разрешению DEC-015 (2026-10-26). Это не утверждение И2б
rev3 или всего FIRST_TEXT_SLICE. Код: [маршруты](../backend/feedback2req/api/processing.py),
[сервис](../backend/feedback2req/processing/service.py);
[отличия и фактические проверки](plans/text-extraction-implementation.md).

Последующий DEC-016 добавляет backend F2; группа и условное расширение чтения
group_findings Run описаны в [FINDING_GROUPS_API](FINDING_GROUPS_API.md).
Публичные inspect/extract команды и их DTO сохраняются.

## Общие правила

`p=/api/v1/projects/{project_id}`. Все операции требуют текущую сессию и Member
(включая Owner/Approver). POST также требует Origin, X-CSRF-Token и UUID
Idempotency-Key. GET не запускает работу. JSON UTF-8, закрытые входы, UUID
строками, no-store, X-Request-ID и безопасные ошибки из [API](API.md).
Автор, provider/model, synthetic, lease/token не назначаются клиентом.
Списки `{items,next_cursor}`: UUID cursor, порядок ID по возрастанию, серверный
page_size по умолчанию50. Это история с created_at, не сортировка по дате и
не единый snapshot нескольких страниц. Последний run доступен в overview.

## Маршруты и команды

| Метод / путь | Вход → ответ |
|---|---|
| GET p/overview | 200 Overview без текстов |
| POST p/runs | Start →202 Run; команда сохранена, успех AI не обещан |
| GET p/runs | Страница полных Run |
| GET p/runs/{run_id} | 200 Run своего проекта |
| POST p/units/{unit_id}/retries | {expected_attempt_id} →202 новый Run с одной unit |
| GET p/findings | Страница Finding; необязательный attempt_id фильтрует внутри проекта |
| GET p/findings/{finding_id} | 200 Finding с exact evidence/provenance |
| GET p/fragments/{fragment_id}/states/{state_id} | 200 Fragment; сейчас immutable state_id=id |

Start, с Idempotency-Key в заголовке:

```json
{"operation":"extract_feedback","inputs":[{"kind":"source","id":"<UUID>","state_id":"<UUID>"}]}
```

1–32 независимых inputs одного проекта. Extract принимает только source;
каждый сохранённый text state — один целый атомарный TextSegment. Документы
как контекст, ASR и скрытая сегментация не добавляются; текст не обрезается.
Вторая допустимая operation — inspect_text, с source либо document input:
реальные len(text)/UTF-8 bytes, без AI или находок.

Повтор материала в одной команде422. UUID канонизируются перед fingerprint;
порядок inputs не меняет команду. Область ключа: проект/инициатор/start либо retry.
Тот же ключ/тело возвращает актуальный прежний Run; другое тело409
idempotency_conflict. Текущий доступ проверяется и при replay.

Retry: `{expected_attempt_id:"<UUID>"}` только для failed при прежних текущих
входах. Новый run/unit с retry_of_attempt_id; старые записи не переписываются.
Два разных ключа не создают две ветви retry. Ошибка преемника повторяется
по его собственной attempt. Автоматического retry failed/cancelled/completed
нет. Добавление материала никогда не создаёт run.

## Run, Unit и Attempt

```text
Run = {id,operation,created_at,execution_kind,state,units}
Unit = {id,input:{kind,id,state_id},state,retry_of_attempt_id,attempt}
Attempt = {id,request_id,state,started_at,finished_at,reason_code,
           provider,model,synthetic,ai_performed,coverage,annotations,
           finding_ids,fragment_ids,technical_result}
```

execution_kind=semantic для extract_feedback, technical для inspect_text.
Units отсортированы по id; queued имеет attempt=null. Время UTC RFC3339;
finished_at=null до окончания. technical_result=null либо
`{character_count,utf8_byte_count}`. Result IDs не имеют обещанного порядка.
owner_token/lease, сырой request/response, исходный текст и SQL не выдаются.
Annotations могут содержать производный текст; доступны только Member проекта.

States: queued/running/completed/failed/cancelled; у Run также partial.
Все queued →queued; есть queued/running →running; одинаковый конечный исход
всех units →этот исход; разные полностью конечные →partial.
Completed означает техническое выполнение и приём, а не полноту анализа всего
проекта или смысловую истинность AI. Охват читается отдельно из coverage.
Успешный пустой ответ хранит coverage и причину, не фиктивные находки.
not_processed/insufficient_information не показываются как полный semantic успех.

Coverage соответствует atomic extract 1.0. Annotations: questions/uncertainties;
related сохраняет origin/key и добавляет id (input→unit UUID, output→finding UUID).
local_id имеет область одной попытки. Evidence хранится отдельными typed FK.

synthetic=true — тестовый ответ, не доказательство работы AI. ai_performed:
false для inspect_text, synthetic и запрещённой передачи; true при полученном
ответе реального адаптера (даже если позднее отклонён валидацией); null, когда
реальное выполнение не удалось подтвердить. Это не учёт биллинга и не
обещание отсутствия внешнего вызова при null.

Reason codes: provider_not_configured, provider_error, invalid_response,
execution_error, lease_expired, deadline_exceeded; отмены input_changed и
access_revoked. Не сохраняются исключения провайдера/SQL и исходный ввод.
Неизвестный COMMIT не вызывает повторного AI или второй публикации: сохранённый
completed остаётся успехом, незавершённый running истекает в failed для ручного retry.

## Finding и Fragment

```text
Finding = {id,state_id,text,types,mode,authorship:"ai",synthetic,attempt_id,
           created_at,freshness,evidence:[Fragment],coverage,annotations,
           provider,model,ai_performed}
Fragment = {id,state_id,attempt_id,source_ref,text_ref,quote,locator,reliability}
```

Source/text refs: `{kind:"feedback_source",id,state_id}`. Locator `{start,end}`
по Unicode code points точного state, [start,end). Quote точная; occurrence
считает перекрытия; LF/CRLF/Unicode не меняются. У текста нет time_range.
Reliability=usable наследуется от сохранённого человеческого text input.
Types: непустое уникальное подмножество problem/request/observation/need;
mode direct/inferred. Несколько fragments могут поддерживать одну finding.

Результаты этого среза неизменяемы, state_id=id. Человеческих write endpoints
пока нет; новый явный анализ создаёт новые результаты, а не заменяет прежние.
Freshness current/requires_update определяется по выбранному source state;
новый текст не подставляется вместо exact evidence. Human history, удаление
и tombstones не эмулируются этим read API.

## Overview O1

```json
{
  "project_id":"<UUID>","calculated_at":"2026-11-02T10:00:00Z",
  "material_counts":{"text_sources":2,"product_documents":1},
  "semantic_metrics":{"availability":"not_implemented"},
  "processing":{"availability":"available","latest_run_id":null}
}
```

Один SELECT проверяет membership и считает заголовки обоих видов, без текстов
или states. Пустой поддержанный набор даёт0. latest_run_id=null — запусков нет;
иначе последний по created_at DESC,id DESC, включая failed. Semantic metrics
означает будущую агрегирующую аналитику: находки читаются отдельным API,
группы читаются отдельным F2 API, требования/решения ещё не реализованы.
SQL/сетевая ошибка не подменяется
нулём или not_implemented. Ошибка загрузки и отсутствие результатов различаются.

## Ошибки и frontend

Общие 401 unauthenticated, 403 origin_rejected/csrf_rejected, 413 body_too_large,
422 invalid_request и безопасная500 internal_error сохраняются. Неизвестный
или чужой проект/материал/state/result →одинаковая404 not_found. State другого
материала своего проекта422 invalid_input; старый state нужного409 input_changed.
Поиск state ограничен проектом. Неверный/отсутствующий ключ422; retry не failed
или не та attempt409 retry_not_allowed, существующий преемник409 retry_already_requested.

Клиент хранит run_id/key, опрашивает GET run, восстанавливает историю через
GET runs/overview. После202 фоновые ошибки видны в attempt. При failed отдельный
ручной retry, при input_changed новый явный start по новому state. Сетевой отказ
не доказывает rollback: можно явно повторить ту же команду с прежним ключом.
Не выдавать synthetic/inspect_text за AI и не рисовать проценты из демо.
Finding/fragment/source counts не число независимых участников.

## Провайдер

Ollama: POST /api/chat, stream=false, self-contained approved JSON Schema в
format, затем локальные schema/application checks. Документация транспорта:
[chat](https://docs.ollama.com/api/chat),
[structured outputs](https://docs.ollama.com/capabilities/structured-outputs).
Без F2R_AI_TRANSFER_ENABLED=true, F2R_AI_PROVIDER_URL и F2R_AI_MODEL запрос
не отправляется; попытка provider_not_configured. Включать только после
отдельного согласия на provider/model/условия. Redirect/proxy environment
не используются, endpoint должен быть доступен из сети worker. Internal data
network не обещает внешний интернет. Модель и API key не выбраны по умолчанию.
F2R_PROCESSING_TEST_MODE=true — только disposable synthetic стенд.
