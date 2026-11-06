# Backend F2: группы находок

Область: DEC-016, AI-контракты 1.0 неизменны. Сервис принимает результаты
group_findings. Последующий DEC-017 добавляет [внутреннюю очередь F3](GROUPING_ORCHESTRATION.md);
публичная команда запуска по-прежнему отсутствует.
Миграция M03 следует после M02b, сохраняет данные F1 и добавляет 11 таблиц:
finding_groups, group_states, group_members, group_scope, group_context,
group_conflicts, conflict_positions, position_members, grouping_inputs,
grouping_documents, grouping_previous_groups.

## Чтение

Префикс `p=/api/v1/projects/{project_id}`. Существующая сессия и членство
в проекте обязательны для каждого GET. Owner/Approver читают на тех же условиях.
JSON UTF-8, UUID строками, даты UTC RFC3339, no-store и X-Request-ID.

| Метод / путь | Ответ |
|---|---|
| GET p/groups | 200 `{items:[GroupSummary],next_cursor}` |
| GET p/groups/{group_id} | 200 GroupDetail текущего состояния |
| GET p/groups/{group_id}/states/{state_id} | 200 GroupDetail точного состояния |

Список: необязательные UUID `cursor` и `attempt_id`, порядок group UUID ASC,
исключительный cursor, серверный page_size (50 по умолчанию). Следующая страница
не является продолжением единого snapshot. Неизвестный/чужой attempt_id фильтр
возвращает пустой список. Пустой результат: `{items:[],next_cursor:null}`.

```text
GroupSummary = {id,state_id,title,summary,authorship,synthetic,attempt_id,
                created_at,freshness}
StateRef = {kind,id,state_id}
GroupDetail = GroupSummary + {
  previous_state_id,author_id,
  members:[{ref:StateRef,finding:Finding}],
  considered_findings:[StateRef],
  context:[{ref:StateRef,locator:{start,end}}],
  conflicts:[{id,description,positions:[{id,description,findings:[StateRef]}]}],
  coverage:[CoverageItem],annotations:{questions:[],uncertainties:[]},
  provider,model,ai_performed
}
```

Nullable: previous_state_id, author_id, attempt_id для будущего самостоятельного
human-state, provider/model/ai_performed по происхождению. Текущий сервис создаёт
только ai-state. Finding — точный существующий detail
[F1](TEXT_PROCESSING_API.md), включая fragments с source_ref, quote и locator.
Состояния находок и фрагментов F1 пока неизменяемы, state_id=id; состояние
группы имеет собственный UUID, отдельный от идентичности группы.

Цепочка чтения: GroupDetail.members.ref → member.finding.evidence →
Fragment.source_ref. Conflict.positions.findings указывает на те же exact
members, а не создаёт копии находок. considered_findings хранится отдельно
от members. Документы используются только как контекст.

Списки не содержат evidence/исходных текстов; title/summary — производные
сведения. freshness=current/requires_update вычисляется по сохранённым
зависимостям (рассмотренные находки, их source states, контекст документации
и предыдущие группы). Текущий текст источника не заменяет выбранный старый
state. Freshness не является оценкой достаточности или человеческим решением.

401 unauthenticated; неизвестные/чужие project/group/state → одинаковая
404 not_found, включая state другой группы; неверный UUID/cursor →422
invalid_request; ошибка БД →500 internal_error. Общий error envelope —
[API](API.md). GET не требует Origin/CSRF и не запускает вычисление.

## Чтение Run

Существующие GET p/runs и p/runs/{run_id} поддерживают внутренние
group_findings runs. Изменение DTO относится только к этой operation:

```text
Unit.input = {kind:"finding_set",findings:[StateRef],documents:[StateRef],
              previous_groups:[StateRef]}
Attempt.grouping_result = null | {
  group_ids:[UUID],ungrouped_findings:[StateRef],
  input_findings:[{key,ref:StateRef}]
}
```

Остальные поля сохраняются, включая coverage, annotations, synthetic и
ai_performed. input_findings связывает CoverageItem.input_key с точным state.
grouping_result=null до принятия и при техническом отказе; принятый пустой
результат имеет group_ids=[] и отдельный ungrouped набор. Отсутствие групп
не подменяет успешный приём ошибкой. Questions сохраняются и без групп.
Related annotations сохраняет origin/key и добавляет kind/id/state_id.
Для questions и uncertainties допустимы input-ссылки только на явно
переданные findings либо previous_groups этой Unit; output-ссылки — на группы
принятого результата. Например, `{origin:"input",key:"g1",kind:"finding_group",
id:<selected-group-id>,state_id:<selected-state-id>}` ссылается на прежнюю
группу, а output/g1 — на новую, даже если локальные ключи совпадают.
Идентичность и state берутся из сохранённых typed inputs, не из ответа AI.
Run и GroupDetail возвращают эту точную ссылку и после появления нового state
прежней группы. Автоматической загрузки/подмены состояния нет; прежние вопросы
и конфликты такая ссылка не изменяет.

Одна finding может быть в нескольких группах; grouped и ungrouped не
пересекаются. Coverage различает completed, insufficient_information и
not_processed. Technical failed не содержит принятого coverage. Для отдельной
finding partially_processed отклоняется: доверенного плана подединиц нет.
Общий результат может быть неполным. Глобальная аналитика не вычисляется,
overview.semantic_metrics остаётся not_implemented.

POST p/runs по-прежнему разрешает только inspect_text/extract_feedback;
retry grouping unit →409 retry_not_allowed. Для групп нет write endpoints.

## Подключение AI-компонента

Внутренний модуль: [grouping/service.py](../backend/feedback2req/grouping/service.py).

```python
provenance = Provenance(provider="<adapter>", model="<version>", synthetic=False)
h = prepare_grouping(
    sessions, identity, session_token, project_id, command_key, finding_refs,
    document_refs=document_refs, previous_group_refs=previous_group_refs,
    provenance=provenance,
)
if not h["replayed"]:
    # Передать h["request"] компоненту group_findings 1.0 вне транзакции.
    # Каждые несколько секунд вызывать renew_grouping(sessions, unit_id, token).
    # При False прекратить работу: публикация по утраченной lease запрещена.
    result = accept_grouping(sessions, h["unit_id"], h["owner_token"], response)
```

Подготовка/приём доступны отдельно. Реализован также внутренний исполнитель
[execute_grouping](../backend/feedback2req/grouping/execution.py), соединяющий
их с перенесённым без изменения компонентом `ai.group_findings`:

```python
receipt = execute_grouping(
    sessions, identity, session_token, project_id, command_key, finding_refs,
    provider=explicit_provider,
    document_refs=document_refs, previous_group_refs=previous_group_refs,
)
# receipt: run_id, unit_id, attempt_id, replayed, result
# result: attempt_id, state, reason_code, group_ids, ungrouped_findings
```

Провайдер обязателен и не выбирается по умолчанию. Внешняя модель этой
итерацией не подключается: все выполненные вызовы использовали synthetic Replay.
Реальная конфигурация по-прежнему требует отдельного разрешения. Исполнитель
не является новым HTTP endpoint или частью публичной очереди.

Перед вызовом компонента callback открывает короткую транзакцию и сверяет
весь request с заново собранными доверенными данными, project membership и
владением попыткой. Блокировки освобождаются перед provider.group. Heartbeat
каждые 5 секунд вызывает renew_grouping; потеря lease/прав запрещает публикацию.
После остановки heartbeat кандидат проходит независимый финальный приём F2.
Синхронный исполнитель не обещает принудительно прервать чужую функцию:
переданный адаптер должен иметь timeout в пределах deadline попытки.

Compute-ошибки сохраняют безопасные существующие reason codes:
invalid_response → invalid_response; provider_not_configured сохраняется;
transport/timeout → provider_error; непригодный запрос/ошибка исполнения →
execution_error. Если изменились входы или права, итог cancelled input_changed/
access_revoked имеет приоритет. Технический отказ не создаёт coverage.
Ошибка записи/COMMIT не попадает в этот обработчик и выходит вызывающему коду.
Повтор execute с прежним command_key только читает прежний run; provider
повторно не вызывается, в том числе после неизвестного prepare/final COMMIT.

Модуль компонента ограничивает request/response 1 MiB, без урезания.
Передача более крупного запроса завершает attempt технической ошибкой до
вызова провайдера. JSON Schema 1.0 этим ограничением не меняется.

Совместимость: явное ungrouped — содержательная классификация, поэтому
completed+ungrouped не требует дополнительной reason. Текущая согласованная
политика F2 расширена утверждением от 2026-11-06: questions и uncertainties
могут ссылаться на явно переданную previous_group. Перед публикацией заново
проверяются точная пара group/state, project membership и свежесть контекста.
Неизвестная/чужая группа или чужой state отклоняются при prepare с 404;
устаревший выбранный state — 409 input_changed. Изменение ожидаемого контекста
после prepare отменяет публикацию с cancelled/input_changed; отзыв доступа —
cancelled/access_revoked. Related input key вне findings/previous_groups
отклоняется как invalid_response без частичного сохранения. Подробности —
[отчёт интеграции](plans/grouping-component-integration.md).

prepare аутентифицирует session_token через существующий Identity и заново
проверяет membership под Project lock; raw session token не сохраняется.
finding_refs — `{id,state_id}` (kind=finding необязателен), documents аналогично
с kind=product_document и необязательным locator, previous groups с kind=finding_group.
Отсутствующий locator означает весь сохранённый документ. Наборы канонизируются.
Previous groups должны замыкаться на явно выбранные findings; они являются
контекстом и никогда не назначают объект для перезаписи.

prepare возвращает run_id/unit_id/attempt_id, request и owner_token только
первому исполнителю после COMMIT. Повтор command_key с прежним составом даёт
replayed=true, request=null, owner_token=null; иной состав →409
idempotency_conflict. При неизвестном исходе prepare читать Run или повторять
prepare с тем же ключом, не запускать AI при replay.

Отказ адаптера фиксируется fail_grouping со стабильной причиной:
provider_not_configured/provider_error/execution_error/invalid_response/
deadline_exceeded. Реальные внешние вызовы этим модулем не выполняются.
Synthetic тесты обязаны использовать synthetic=true; ai_performed=false.
При получении реального ответа ai_performed=true, даже если ответ отклонён.

renew продлевает lease не дальше deadline. Lease/deadline — 30/120 секунд,
recovery существующего worker завершает истёкшие попытки. F1 claim исключает
grouping units; F3 worker отдельно забирает только queued finding_set.
Синхронный prepare сразу создаёт running Attempt, не очередь.
Приём сверяет token, lease/deadline, membership,
точные finding/source/document/previous-group states и проверяет схему/ссылки.
После этого вся публикация и completed фиксируются одной транзакцией.

Исключение записи, включая потерю подтверждения COMMIT, выходит вызывающему
коду. Нужно перечитать Run или повторить accept с прежним token. Completed
replay возвращает сохранённый результат, не создаёт вторые группы и не вызывает
AI. SHA-256 capability хранится отдельно, чтобы проверить completed replay
после очистки owner_token. Он и сам token не выдаются через HTTP.

## Синтетический пример трассируемости

Обозначения ниже заменяют реальные UUID теста. Источник S1/state1 содержит
«Отправлять автоматически», S2/state2 — «Только после подтверждения».
F1 сохраняет фрагменты E1/E2 и находки F1/F2 с отдельными идентичностями.
Группа G/stateG содержит точные refs F1/F2; конфликт C хранит две позиции:
«Автоматически» → F1 → E1 → S1/state1 и «С подтверждением» → F2 → E2 → S2/state2.
Третья находка F3 может остаться в ungrouped, а F1 одновременно войти в другую
группу. Этот пример проверяется синтетическими PG/API-тестами; backend не
объявляет одну позицию правильной и не доказывает смысловой конфликт.

## Ограничения

Нет human-write API, публичного запуска группировки, удаления источников/
проектов, глобальных метрик или генерации требований. Структура поддерживает
историю, но не объявляет эти сценарии реализованными. Программные проверки
не доказывают реальность смыслового конфликта или качество AI.
Фактические результаты и отличия от проекта — в
[пакете F2](plans/backend-finding-groups.md).
