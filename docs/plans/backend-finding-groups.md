# F2: хранение, приём и чтение групп находок

**PROPOSED, ревизия 1, 2026-11-03.** Пакет для согласования перед этапами
B–D. Создание этого документа и коммита не утверждает предложенные DDL/API.
Основание задачи — вложение пользователя «Задача: реализовать следующий
backend-срез F2 — группировка находок». Снимок вложения не изменялся.

## 1. Проверенная база и границы разрешения

- Базовая локальная и удалённая ветки `agents/pasted-text-processing`:
  `1713498cf67f44c860adfa73d93642240c74daf6`. Удалённый HEAD проверен через
  `git ls-remote` 2026-11-03. Ветки `feat/backend-finding-groups` ранее не было.
- Созданы собственная ветка `feat/backend-finding-groups` от этого коммита и
  worktree `.local/worktrees/backend-finding-groups`. Исходный checkout
  `preview/workspace` чистый, HEAD `58f702f71d2fc2d0f403db6114e95040975e8a79`.
  Чужие checkout не изменялись. Удалённые ветки не обновлялись.
- DEC-001–005 утверждают смысл групп, M:N, отдельные позиции конфликтов,
  точные состояния, охват и внутренние AI-контракты 1.0. DEC-006 задаёт стек.
- DEC-015 разрешает самостоятельную детализацию первого extract-сценария;
  его область не распространяется автоматически на DDL/API группировки.
- [Проект backend](backend-prototype-support.md), §6, и
  [FIRST_TEXT_SLICE](../FIRST_TEXT_SLICE.md) оставляют физическую схему и API
  F2 предложениями. Требуемое согласование касается §3–6 этого документа.

Следующие этапы: после утверждения записать область и ревизию в
[DECISIONS](../DECISIONS.md), реализовать миграцию/приём, затем чтение и проверки.
Frontend, генерация/проверка требований, решения Approver и подключение
реального AI в текущий объём не входят.

## 2. Фактическое соответствие F1 и F2

Источники реализации:
[ORM](../../backend/feedback2req/persistence/processing.py),
[сервис](../../backend/feedback2req/processing/service.py),
[HTTP](../../backend/feedback2req/api/processing.py),
[M02b](../../backend/migrations/versions/m02b_processing_extract.py),
[контракт F1](../TEXT_PROCESSING_API.md).

| Область | Реализовано F1 | Что требуется F2 |
|---|---|---|
| Finding/Fragment | Неизменяемые строки; `state_id=id`; evidence через FK | Точные ссылки на эти строки без переделки F1 |
| Run | Только inspect_text/extract_feedback | Внутренняя операция group_findings |
| Unit | XOR одного source state или document state | Третий вариант: фиксированный набор finding states |
| Attempt | Lease, token, deadline, coverage/annotations | Тот же протокол владения и атомарного приёма |
| Результат | Finding/Fragment, нет Group | Устойчивый header группы и отдельные состояния |
| Приём | Только atomic extract | Schema + AP-01–08/AP-11 для group_findings |
| Чтение | Findings, fragments, runs | Группы, состояния, результат попытки без готовых групп |

Схемы FindingView/FragmentView/GroupCandidate/CoverageItem уже существуют в
[common.schema.json](../contracts/ai/v1/common.schema.json). Это JSON-типы
внутреннего контракта, а не имеющиеся ORM-таблицы групп.

## 3. Предлагаемая физическая дельта

Одна новая миграция после M02b; существующие строки/результаты сохраняются.
UUID генерирует сервер, время — UTC timestamptz. У каждой таблицы есть
`project_id`; связи составные с проектом и идентичностью объекта.

| Таблица | Поля и ограничения сверх project_id |
|---|---|
| finding_groups | id PK, current_state_id NOT NULL, created_at; UNIQUE(project_id,id); deferred FK current → собственный group_states |
| group_states | id PK, group_id, previous_state_id nullable, title TEXT, summary TEXT, authorship, author_id nullable, attempt_id nullable, local_id nullable, created_at; UNIQUE(project_id,group_id,id), UNIQUE(attempt_id,local_id); previous → состояние той же группы |
| group_members | group_state_id, finding_id, finding_state_id; PK(project_id,group_state_id,finding_id); FK → group_states и findings; CHECK finding_state_id=finding_id для неизменяемой F1 |
| group_scope | group_state_id, finding_id, finding_state_id; те же точные FK и уникальность; рассмотренные находки отдельно от members |
| group_context | group_state_id, document_id, document_state_id, start, end; PK по state/document/state/locator; FK → точный document state; CHECK 0≤start<end |
| group_conflicts | id PK, group_state_id, local_id, description TEXT; UNIQUE(project_id,group_state_id,id), UNIQUE(attempt_id,local_id); attempt_id FK и проверка соответствия attempt состояния |
| conflict_positions | id PK, group_state_id, conflict_id, ordinal, description TEXT; UNIQUE(project_id,group_state_id,conflict_id,ordinal); составной FK → conflict того же group_state |
| position_members | group_state_id, position_id, finding_id, finding_state_id; PK(project_id,position_id,finding_id); FK → position того же state и group_members того же state/finding |
| grouping_inputs | unit_id, key, finding_id, finding_state_id; PK(project_id,unit_id,key), UNIQUE(project_id,unit_id,finding_id); FK → unit/finding; CHECK state_id=id |
| grouping_documents | unit_id, key, document_id, document_state_id, start, end; PK(project_id,unit_id,key); точный FK и CHECK границ |
| grouping_previous_groups | unit_id, key, group_id, group_state_id; PK(project_id,unit_id,key), UNIQUE(project_id,unit_id,group_id); FK → точный state своей группы |

Последние три таблицы — типизированные входы существующей Unit, не новые
предметные сущности. Фрагменты восстанавливаются по неизменяемым evidence F1;
сырой request/response и исходный текст не копируются в историю группировки.

`group_states` допускает происхождение ai/human/ai_and_human с CHECK:
ai требует attempt/local_id и не имеет author_id; human требует author_id;
ai_and_human требует author_id и AI lineage. Сейчас сервис создаёт только ai.
Человеческих write endpoints в F2 нет. Непустые title/summary и descriptions
проверяются схемой и приложением; минимум один member/две позиции/один member
позиции проверяются сервисом в транзакции, простого FK для этого недостаточно.

Run.operation расширяется group_findings; command_kind остаётся start/retry.
Unit получает input_kind=source/document/finding_set: существующим строкам
значение выводится из заполненных FK. CHECK сохраняет прежний XOR для первых
двух видов, для finding_set оба material FK пусты, набор хранится в grouping_inputs.
Приложение проверяет совместимость Run.operation и Unit.input_kind.

Охват хранится в Attempt.coverage, annotations — в Attempt.annotations с
типизированной прикладной привязкой input → finding id/state, output → group
id/state. Негруппированные находки — отдельный JSONB массив точных StateRef
в новом nullable поле Attempt.ungrouped_findings; это ссылки, без текстов.
NULL означает отсутствие принятого group-результата, [] — принятый пустой набор.

## 4. Внутренняя граница и публикация

Предлагаемый прикладной интерфейс (не HTTP и не включение провайдера):

```text
prepare_grouping(sessions, actor_id, project_id, command_key,
                 finding_refs, document_refs=[], previous_group_refs=[],
                 provenance) -> {run_id, unit_id, attempt_id, owner_token, request}
renew_grouping(sessions, unit_id, owner_token) -> owned: bool
accept_grouping(sessions, unit_id, owner_token, response) -> accepted result
fail_grouping(sessions, unit_id, owner_token, reason_code) -> terminal outcome
```

provenance задаёт доверенный серверный адаптер: provider/model/synthetic;
ai_performed имеет существующую семантику F1 и фиксируется сервером при исходе.
Никакой клиент не назначает provenance/token. prepare проверяет текущую сессию
инициатора через доверенный Actor и его membership в той же транзакции;
внутренний вызов не принимает произвольный actor_id от неаутентифицированного клиента.
command_key — UUID; replay с тем же составом/инициатором возвращает прежний run,
другое тело → idempotency_conflict. Токен владельца не выдаётся второму исполнителю.

prepare под блокировкой Project создаёт Run/Unit/Attempt сразу running;
затем адаптер вычисляет вне транзакции. Lease/deadline — существующие 30/120 с,
heartbeat явно вызывает renew. Истечение обрабатывает существующий recovery;
обычный claim не подхватывает внутренние grouping units. Публичные start/retry
group_findings не добавляются: POST /runs продолжает разрешать только две
существующие операции; retry grouping unit →409 retry_not_allowed.

Request точно соответствует [group_findings.request 1.0](../contracts/ai/v1/group_findings.request.schema.json):
findings → FindingView по выбранным сохранённым состояниям; fragments → только
доступные evidence этих находок; documents → выбранные excerpts; previous_groups
→ выбранные точные GroupView с замкнутыми ссылками. Нет скрытой загрузки
недостающих finding states или автоподстановки новых состояний.
Сборщик сохраняет соответствие ключей реальным FK; keys уникальны во всём входе.

Приём проверяет schema request/response локальным Registry, затем:

1. Все exact refs принадлежат проекту и доверенному набору, тексты/диапазоны
   совпадают с БД; нет повторных aliases одной finding или неизвестных ключей.
2. Все output local_id (группы, конфликты, вопросы, uncertainties) уникальны
   совместно; строки пригодны для PostgreSQL UTF-8; технические ограничения
   F1 256 символов на local_id/32768 на строку сохраняются и документируются.
3. Members непусты, уникальны, входят в considered_keys своей группы;
   considered_keys указывает только на reviewed inputs, context_keys — documents.
4. Каждый конфликт имеет минимум две позиции. Members каждой позиции входят
   в группу; одинаковая позиция (description + набор members) не дублируется.
   Пересечение разных позиций само по себе не запрещено контрактом 1.0.
   Семантическую несовместимость backend не объявляет доказанной.
5. Coverage содержит ровно одну запись на каждую входную finding. grouped и
   ungrouped не пересекаются, их ключи принадлежат reviewed inputs; каждая
   completed finding обязательно представлена одним из этих способов.
   Одна finding в нескольких группах допустима. not_processed не становится member.
   Причины и отсутствие содержательного результата проверяются по AP-07.
6. **Ограничение первого серверного контура для согласования:** каждая finding
   рассматривается целиком. partially_processed для отдельной finding без
   доверенного плана подединиц отклоняется как неопределимый охват (AP-07).
   Частичный общий результат возможен через completed/insufficient_information/
   not_processed разных findings и сохраняется без объявления полноты проекта.
7. Related input у questions/uncertainties указывает на основную finding,
   related output — группу; ссылки на conflict/документ/fragment не подменяют
   scope затронутого объекта. Тексты и blocking сохраняются без разрешения вопросов.

В финальной транзакции порядок блокировок Project → Unit → Attempt;
после ожидания заново читаются membership, owner token, lease/deadline,
выбранные finding refs, evidence/source current states, document refs и
previous group current states. Любое изменение отменяет публикацию input_changed
либо access_revoked. Новые группы создаются с новыми идентичностями;
previous_groups — контекст, не команда заменить существующий current_state.
Поздний AI не двигает человеческие указатели.

Все group states/members/scope/context/conflicts/positions, coverage, ungrouped,
annotations и completed attempt коммитятся вместе. Невалидный ответ фиксируется
failed invalid_response без групп. Ошибка записи откатывает весь приём;
неизвестный COMMIT проверяется чтением прежней попытки, не повторным AI-вызовом.
Повтор accept завершённой попытки возвращает сохранённый результат без записи;
failed/cancelled/чужой token не публикуются. Другие успешные units не изменяются.

## 5. Предлагаемый точный read API

Все GET: текущая session + Member (Owner/Approver включены), no-store,
X-Request-ID, существующий безопасный error envelope. 401 unauthenticated;
неизвестный/чужой проект/group/state/attempt → одинаковая 404 not_found;
невалидный UUID/cursor →422 invalid_request; сбой БД →500 internal_error.
Origin/CSRF не требуются для GET. При state другого group также 404.

```text
GET /api/v1/projects/{project_id}/groups?cursor=<UUID>&attempt_id=<UUID>
  ->200 {items:[GroupSummary],next_cursor:UUID|null}
GET /api/v1/projects/{project_id}/groups/{group_id}
  ->200 GroupDetail текущего state
GET /api/v1/projects/{project_id}/groups/{group_id}/states/{state_id}
  ->200 GroupDetail ровно выбранного state

GroupSummary = {id,state_id,title,summary,authorship,synthetic,attempt_id,
                created_at,freshness}
StateRef = {kind,id,state_id}
GroupDetail = GroupSummary + {
  previous_state_id:UUID|null, author_id:UUID|null,
  members:[{ref:StateRef,finding:Finding}],
  considered_findings:[StateRef],context:[{ref:StateRef,locator:{start,end}}],
  conflicts:[{id,description,positions:[{id,description,findings:[StateRef]}]}],
  coverage:[CoverageItem], annotations:{questions:[],uncertainties:[]},
  provider:string|null,model:string|null,ai_performed:boolean|null
}
```

Finding — существующий detail F1 с точными Fragment и source refs, прочитанный
по member state, без подмены текущим. UUID в JSON — строки, даты RFC3339 UTC.
authorship — ai/human/ai_and_human; первоначально ai. freshness=current либо
requires_update: проверяются все considered findings/evidence и context,
не только выбранные members. Независимое добавление другой finding само по себе
не делает ограниченный scope устаревшим или полным охватом проекта.

Список сортируется по group UUID ASC, cursor исключительный, page_size из
существующих настроек (50), next_cursor по прежнему правилу limit+1; пусто →
items=[], next_cursor=null. Фильтр attempt_id ищет только свой проект,
неизвестный/чужой фильтр даёт пустой список. В списке нет evidence/исходных текстов;
title/summary являются производными данными. Глобальные counts не вычисляются.

Чтобы не терять ungrouped/вопросы/coverage при groups=[], существующий GET
runs/{run_id} расширяется **только для group_findings**:

```text
Unit.input = {kind:"finding_set",findings:[StateRef],documents:[StateRef],
              previous_groups:[StateRef]}
Attempt.grouping_result = null | {
  group_ids:[UUID],ungrouped_findings:[StateRef],
  input_findings:[{key,ref:StateRef}]
}
```

Остальные поля Run/Unit/Attempt и derived run states сохраняются. До принятия
grouping_result=null; принятый результат с нулём групп содержит [] и точные
ungrouped refs. Coverage/annotations читаются из существующих полей Attempt.
inspect/extract DTO остаются прежними. Чтение runs списка учитывает новую
операцию; GET не запускает её. Обзор O1 сохраняет semantic_metrics=not_implemented.

## 6. Проверки после согласования

FR-011–013/AC-04: одна/несколько групп, индивидуальная идентичность, конфликт
«отправлять автоматически»/«отправлять только после подтверждения», ungrouped.
FR-015–016/AC-05 и AP-01–08: точная цепочка Finding → Group → Conflict →
Position → тот же Finding → Fragment → Source state; неверные refs/состояния,
local_id, coverage, ключи, позиции, questions и неопределённая частичность.
FR-021–023/AC-07 и AP-11: гонки current/access/lease, replay, rollback, unknown
commit, независимые units; будущая human state не заменяется AI.
FR-003/032: session/member/изоляция, cursor и безопасные ошибки HTTP.

Реальная PostgreSQL в собственном disposable Compose project: upgrade с M02b
с прежними F1 данными, составные FK/CHECK/UNIQUE, конкурентные транзакции,
перезапуск процесса и БД, все 12 обязательных сценариев из задания. Регрессии
F1 — существующие processing/provider/security/material/identity тесты.
Synthetic fixtures помечаются synthetic=true, ai_performed=false; runtime
не подставляет их вместо отсутствующего AI. Затем независимое ревью при наличии
доступного reviewer в рамках правил репозитория; его отсутствие раскрывается.

## 7. Уже выполнено и что остаётся

Этап A: проверены refs/worktree, код F1, статусы документов; подготовлен пакет
ревизии 1. Этапы B–D ещё не реализованы: таблиц, миграции и HTTP групп нет.
Утверждение §3–6 необходимо до их реализации согласно AGENTS.md и заданию.

2026-11-03 выполнена автономная проверка неизменённых контрактов:

```text
docker run --rm --network none --read-only --entrypoint python \
  --mount type=bind,source=<absolute-own-worktree>,target=/workspace,readonly \
  feedback2req-checks:latest /workspace/scripts/validate_ai_contracts.py
PASS jsonschema 4.26.0; 9 Draft 2020-12 schemas; 88 local refs
PASS 38 schema-positive and 34 schema-negative examples; 399 unknown-field mutations
PASS 20 offline fixture pairs (APP-* checks only)
```

Это проверка контрактных артефактов, не F2, PostgreSQL, HTTP, регрессий F1 или
качества AI. Docker Engine доступен; локальные python/python3 — Windows aliases,
поэтому использован отдельный контейнер с read-only mount и без сети/БД.
Чужие контейнеры/volumes не менялись. Независимое ревью пакета не выполнено.

После реализации frontend потребуются новые GET, загрузка точного detail и
evidence, чтение grouping_result даже при пустых groups, отдельное отображение
synthetic/freshness/coverage/вопросов/конфликтов. Подключение будущего адаптера:
prepare → request в group_findings 1.0 → heartbeat во время compute → accept
либо fail. До поддержки координатором публичного запуска группировки нет.

Перед генерацией требований нужны отдельно согласованный следующий срез,
координатор группировки, проверенный приём F2 и правила выбора exact evidence;
группы и документы остаются контекстом, находки/фрагменты — основаниями.
Реальный AI и его качество требуют отдельного подключения и оценки.
