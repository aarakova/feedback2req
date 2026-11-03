# Backend для рабочей области прототипа: аудит и предлагаемые срезы

**PROPOSED, ревизия 1, 2026-10-26.** Это результат подготовки и пакет для
согласования, не разрешение новых API, таблиц, worker или AI-вызовов.
Текущий запрос разрешает исправлять подтверждённые дефекты действующих
контрактов; новые контракты должны быть представлены до реализации.

## 1. Объём, источники и фактическая база

Порядок работы: сверить ветки и утверждения → сопоставить шесть экранов →
подготовить минимальный read-контракт → разложить семантическое хранение и
операции на последовательные срезы → проверить согласованность и ограничения.

Основания: [требования](../REQUIREMENTS.md), [домен](../DOMAIN.md),
[архитектура](../ARCHITECTURE.md), [роли](../AGENT_ARCHITECTURE.md),
[модель](../DATA_MODEL.md), [API](../API.md), [решения](../DECISIONS.md),
[AI-контракты](../AI_CONTRACTS.md), [AI-инварианты](../AI_VALIDATION.md),
[тестирование](../TESTING.md), [проект первого среза](../FIRST_TEXT_SLICE.md),
[И2б](../I2B_SPEC.md) и [предыдущий аудит](backend-workspace-readiness.md).
Исходный референс — [прототип](../../prototype/index.html), а не его seed-данные.
Этот документ дополняет предыдущий аудит конкретизацией read-контракта,
таблиц и границ следующих срезов; прежний датированный отчёт не переписывается.

После успешного `git fetch origin` 2026-10-26:

| Ветка | Локальный / remote HEAD | Фактический состав |
|---|---|---|
| main | 6c01d81 / 6c01d81 | И1, И2а, frontend Ф1а/Ф1б, инфраструктура DEC-011 |
| agents/pasted-text-processing | f06e4d1 / f06e4d1 | И2б rev3 как документ; исправления AUD-01, CI AUD-02, предыдущий аудит |
| agents/pasted-text-processing-adf660ee | 9084a58 / 9084a58 | Frontend доступа, DEC-012; backend как в main |
| feat/project-workspace | 58f702f / 58f702f | Доступ → layout 637b02e → переименование/Unicode UI 58f702f; DEC-012–014; backend как в main |

Рабочее дерево при начале задачи чистое. Основной checkout использует
preview/workspace на 58f702f; его данные и чужие worktree не изменялись.
Сравнение backend и Compose между main и frontend-веткой не даёт изменений.
Исправления f06e4d1 пока не входят ни в main, ни во frontend-ветку. При будущей
интеграции нельзя терять серверную валидацию/регрессии и CI gate, полагаясь
на frontend-валидацию. В frontend-ветке также остался ранний снимок И2б:
при интеграции нужен осознанный выбор rev3, а не возврат к прежнему документу.
Merge, cherry-pick, rebase, commit и push этой задачей не выполнялись.

DEC-001–006 утверждают продуктовые правила, логическую модель, внутренние AI
DTO и стек. DEC-007/008 ограниченно разрешают физическую схему и HTTP И1/И2а;
DEC-009–011 — frontend и инфраструктуру. DEC-012–014 в frontend-ветке
не утверждают очередь, семантические таблицы или новые backend API.
Номер будущей записи DEC нужно выбирать с учётом этих записей, а не только
локального журнала. Новый DEC в рамках подготовки не добавляется.

И2б rev3: commit 766ac01; SHA-256 UTF-8/LF
`4337AC61B9D47B1A8DAF4BE371B28D2CC9CF6764B63DE66EA54325BC87689805`.
Статус остаётся PROPOSED. Публикация документа не была утверждением реализации.

## 2. Матрица шести экранов

`p=/api/v1/projects/{project_id}`. В таблицах «Member» включает Owner и
участника с can_approve. Полномочия подтверждает сервер при запросе.

| Экран | Нужные данные / действия | Уже существуют и доступны | Отсутствуют / предложены | Права, AI и достоверность |
|---|---|---|---|---|
| Обзор | Проект, количества материалов/находок/групп/требований, решения, блокеры, утрата оснований, последняя обработка | GET p; lists материалов с полными текстами; permissions | GET p/overview (§4); семантические модели и run discovery | Member; счётчики материалов можно вычислить без AI; остальные показатели сейчас недоступны |
| Материалы | Создание, список, точный текст, state_id; в прототипе также файлы, статусы, исправления, удаление | POST/GET p/sources и p/documents, GET карточки; только сохранённый текст | Файлы/ASR, редактирование и удаление, статус анализа по точному входу — отдельные срезы | Чтение/создание Member; будущее удаление Owner; сохранение не запускает AI; документ не отзыв |
| Находки | Список/карточка, фрагменты, группы, позиции конфликта, вопросы, правки, связанные требования | Исходные source states как вход; предметных результатов нет | §6: fragments/states, findings/states/evidence, groups/states/members, scope/context/questions; GET и условные записи | Member; извлечение и группировка требуют настоящего AI, чтение/правки сохранённого результата — нет |
| Требования | Устойчивая идентичность, редакции/основания, rationale, история, проверки/замечания, решения, предложения | Есть проектные Member/Approver; Requirement отсутствует | §7: requirements/revisions/evidence/context, проверки, proposals, decisions; отдельные read/write API | Member читает/исправляет Draft/предлагает; Approver решает; generation/verification — AI; Approved не результат проверки |
| Обработка | Явный start, units/attempts, текущие состояния/исходы, частичность, ручной retry, результаты | Только конечная диагностика runtime worker-check; HTTP запусков нет | Три операции И2б rev3; затем отдельное расширение под semantic inputs/coverage; discovery запусков отдельно | Member; inspect_text технический и ai_performed=false; этапы/проценты демо не данные |
| Доступ | Участники, Approver, своё ID, имя проекта; в демо также удаление проекта | GET p/access; PUT/DELETE p/access/{user_id}; PATCH p; текущая сессия | Каталога пользователей/передачи владения нет; preview/delete проекта пока предложение | Список/изменения доступа и rename Owner; Member читает собственные permissions; никакого переключателя роли |

Верхний уровень остаётся GET/POST /api/v1/projects. Навигация сама по себе
не требует новых endpoints. Board/list/modal — представления одних данных,
не отдельные серверные сущности. Название текстового отзыва, имя файла,
длительность записи, демонстрационные REQ-01 и RUN-01 не являются текущими
полями API. Нельзя добавлять их как якобы сохранённые метаданные.
«Добавить и обработать» в будущем — два явных шага с независимым исходом;
успех сохранения и неуспех запуска не должны дублировать материал.

## 3. Точный текущий контракт для frontend

Все пути имеют префикс `/api/v1`. UUID — строки. Закрытые формы, JSON UTF-8,
`Cache-Control: no-store`, `X-Request-ID`; списки `{items,next_cursor}`.
Cursor — UUID последнего объекта, порядок UUID, размер задаёт сервер
(по умолчанию 50), не номер страницы. Последовательность страниц не единый
снимок при конкурентном добавлении. Полного count в lists нет.

| Метод / путь | Request → response | Доступ |
|---|---|---|
| POST /auth/register | {login,password} → 201 {id,login}; без входа | Анонимный, точный Origin и JSON |
| POST /auth/session | {login,password} → 200 {user:{id,login},csrf_token} + cookie | Анонимный, точный Origin и JSON |
| GET /auth/session | → 200 та же форма сессии | Текущая сессия |
| DELETE /auth/session | → 204 | Сессия + Origin/CSRF |
| GET /projects | → 200 {items:[Project],next_cursor} | Сессия, только доступные проекты |
| POST /projects | {name} → 201 Project | Сессия + Origin/CSRF |
| GET p | → 200 Project | Member |
| PATCH p | {name} → 200 Project | Owner + Origin/CSRF |
| GET p/access | → 200 {items:[Access],next_cursor} | Owner |
| PUT p/access/{user_id} | {can_approve:boolean} → 200 Access, upsert | Owner + Origin/CSRF |
| DELETE p/access/{user_id} | → 204, в том числе если строки уже нет | Owner + Origin/CSRF |
| POST p/sources | {kind:"text",text} → 201 Source | Member + Origin/CSRF |
| GET p/sources; GET p/sources/{id} | → список / 200 Source | Member |
| POST p/documents | {title,text} → 201 Document | Member + Origin/CSRF |
| GET p/documents; GET p/documents/{id} | → список / 200 Document | Member |

```text
Project = {id,owner_id,name,execution_mode,
           permissions:{is_owner,is_member,can_approve}}
Access = {user_id,is_owner,is_member,can_approve}
Source = {id,state_id,kind:"text",text}
Document = {id,state_id,title,text}
```

Owner имеет Member/Approver через owner_id, его access нельзя изменить.
Approver без Owner не управляет участниками. Каталога login/email нет:
user_id получает сам зарегистрированный пользователь в registration/session.
PUT — upsert без версии, PATCH имени — без If-Match; UI не должен обещать
защиту от неизвестной конкурентной перезаписи. Изменяющие проектные операции
сериализуют Project FOR UPDATE и повторно проверяют права в транзакции.
Все материалы читаются через project_id, включая пользователя с двумя проектами.

Текст/title сохраняются точно, без trim, нормализации и смены LF/CRLF.
По умолчанию текст ≤8192 code points, body ≤16384 bytes; превышение не обрезается.
Пароль регистрации 12–1024 символа, входа 1–1024; пароль не нормализуется.
Имя проекта strip, 1–200 символов. Невалидный PostgreSQL-текст/Unicode
отклоняется безопасно, исходный ввод в ошибку не отражается.

| HTTP / code | Обработка frontend |
|---|---|
| 401 unauthenticated | Вход/восстановление сессии, не повторять mutation автоматически |
| 401 invalid_credentials | Неверные credentials без раскрытия существования login |
| 403 forbidden | Не хватает полномочия; Owner-only 403 не доказывает утрату Member; перечитать GET p |
| 403 origin_rejected / csrf_rejected | Сохранить ввод, восстановить корректную сессию/заголовки; не обходить защиту |
| 404 not_found | Проект/объект неизвестен, чужой или недоступен; одинаковое сообщение |
| 404 http_error | Маршрута пока нет; это не доказательство удаления проекта и не пустой список |
| 409 login_unavailable / owner_access_immutable | Показать соответствующий конфликт; не повторять вслепую |
| 413 body_too_large / text_too_large | Уменьшить ввод без молчаливой обрезки |
| 422 invalid_request / invalid_login / invalid_user / invalid_text / json_required | Исправить команду, не теряя ввод; details не раскрывает значения |
| 429 rate_limited | Ограничение register/login, без обхода и немедленного цикла повторов |
| 500 internal_error, транспортная ошибка | Не считать mutation неисполненной; сначала проверить доступное сохранённое состояние |

Ошибка: `{error:{code,message,details:{},request_id}}`. Cookie HttpOnly,
SameSite=Lax; GET session выдаёт CSRF. Origin проверяется до обработчика;
для защищённых изменений текущий X-CSRF-Token. Новый login не переносит токен
предыдущей сессии. Никакие будущие run/finding/revision команды не должны
посылаться только потому, что демонстрационная кнопка присутствует в референсе.

## 4. Предложение O1: минимальный read обзора без миграции

Это точный первый контракт для отдельного утверждения; не реализован.
Он уточняет необязательное предложение overview из предыдущего аудита.

### 4.1 HTTP и форма

`GET p/overview`, без body и специальных query-параметров, только текущий
Member. GET не запускает обработку. 200, JSON, no-store, X-Request-ID:

```json
{
  "project_id": "20dc9184-a506-46e7-a0e7-d7db29d8b54a",
  "calculated_at": "2026-10-26T10:00:00Z",
  "material_counts": {"text_sources": 2, "product_documents": 1},
  "semantic_metrics": {"availability": "not_implemented"},
  "processing": {"availability": "not_implemented"}
}
```

Числа иллюстративны, production вычисляет их запросом. Два count — целые ≥0,
без null. `calculated_at` — серверное время вычисления в UTC, не идентификатор
MVCC-снимка и не гарантия неизменности после ответа. project_id — UUID пути
в канонической форме. Никаких исходных text/title, sample findings, AI-оценок,
нулевых semantic counters или процентов обработки в ответе нет.

`semantic_metrics` и `processing` в O1 — закрытые одноэлементные объекты,
значение availability только `not_implemented`. Других вариантов O1 пока не
обещает. В отличие от прежнего эскиза добавлена явная недоступность processing,
чтобы UI не принял отсутствие последнего запуска за отсутствие истории.

401 unauthenticated; 404 not_found одинаково для неизвестного/чужого/утраченного
проекта; 422 invalid_request для неверного UUID; 500 internal_error при
внутреннем/SQL-сбое по текущей политике. Сетевой сбой не превращается в 200.
403 не нужен для различия Owner/Member: право чтения одинаково. Общие ограничения
транспорта/middleware сохраняются. Новый 503 и частично успешный response не вводятся.

### 4.2 Источник и конкурентное чтение

Считать `feedback_sources` WHERE project_id=:p AND kind='text' AND
availability='available' и `product_documents` WHERE project_id=:p.
И2а допускает только доступные текстовые отзывы и доступные документы;
ни states, ни sessions, ни fragments не участвуют в count.

Один SELECT должен одновременно установить существование Project и членство
actor (owner_id либо EXISTS project_access), получить оба коррелированных
COUNT и время statement_timestamp(). Отсутствие разрешённой строки →404.
Предварительная проверка доступа отдельным SELECT не заменяет эту проверку.
Авторизация сессии остаётся штатной. Членство и обе величины относятся к одному
statement snapshot READ COMMITTED; коммит отзыва до начала этого SELECT
исключает ответ. Отзыв после снимка не отзывает уже начатое чтение задним числом.
Ни Project FOR UPDATE, ни сериализуемая транзакция для этого read не нужны.

Это проект реализации на основе [PostgreSQL 17 MVCC](https://www.postgresql.org/docs/17/transaction-iso.html#XACT-READ-COMMITTED):
два последовательных SELECT в READ COMMITTED могут увидеть разные снимки.
Запрос выбирает только counts/ID/time, без ORM-загрузки text states.
Имеющихся UNIQUE с ведущим project_id достаточно для первого среза; не создавать
индекс до необходимости по плану запроса. COUNT не становится O(1): для большого
проекта может потребоваться отдельная оптимизация, а не кеш с устаревшими правами.

Миграционные последствия O1: отсутствуют. Изменяются только новый handler,
service/repository/read DTO и соответствующие тесты; старые lists/DTO не меняются.
После согласования синхронизируются API/TESTING/DEC в утверждённом объёме.
Для frontend это один read для обзора; имя/permissions по-прежнему из GET p.

### 4.3 Состояния UI и будущая аналитика

| Ситуация | Правдивое представление |
|---|---|
| Подсистема не реализована | Успешный O1 с availability=not_implemented; показатели недоступны |
| Поддержанный пустой набор материалов | Успешный O1 с count=0 |
| Будущая semantic подсистема реализована, запусков нет | Отдельно согласованный вариант no_results; сейчас он не принимается/не возвращается O1 |
| Будущая обработка успешно рассмотрела вход и нашла 0 | Сохранённый completed coverage с причиной, достоверный 0 в конкретной области; не no_results |
| Запуск failed/partial или данные устарели | Сохранённый исход и охват, независимые успехи видны; не полный нулевой анализ |
| HTTP/SQL/сеть не дали получить сведения | Ошибка загрузки; последние данные можно сохранить визуально с отметкой, не подменять нулями |

Появление новых вариантов availability и новых semantic metrics — отдельное
согласованное расширение; frontend должен различать неизвестный вариант и
свою ошибку чтения, а не считать его нулём. История обработки отсутствует
сейчас физически, а не просто не загружена.

### 4.4 Приёмка O1 после разрешения реализации

O1-T1: пустой проект →0/0; смесь материалов →точные раздельные counts;
несколько states того же header не увеличивают count (тестовые транзакции).
O1-T2: Owner/Member/Approver разрешены; anonymous401; outsider, чужой project,
отзыв доступа до SELECT →одинаковая404 без данных.
O1-T3: конкурентное добавление/отзыв с барьерами до/после SELECT; оба счётчика
из одного снимка; доступ не берётся из ранее прочитанного кэша.
O1-T4: SQL projection не выбирает text/title/state payload, ответ не содержит
их sentinel; нет обхода страниц/N+1 и создания run.
O1-T5: no-store/request_id; повреждённый UUID422; БД/SQL-сбой →безопасная ошибка,
не нули/not_implemented; число старых данных после restart сохраняется.
O1-T6: существующие 71 backend-проверка и обычные material/access сценарии
не регрессируют; миграционный head остаётся m02a.

## 5. Семантика будущих метрик и граница их согласования

| Показатель / определение | Будущий источник и зависимость | Сейчас / API | Риск и FR/AC |
|---|---|---|---|
| Доступные текстовые отзывы, документы | Заголовки И2а | COUNT возможен; O1 требует утверждения | Документ не отзыв; states не материалы; FR-002/004, AC-01/02 |
| Находки | COUNT DISTINCT Finding.id, выбранные текущие состояния | Таблиц нет; §6 и future aggregate | Несколько типов/групп не умножают count и не означают участников; FR-008–013, AC-03/04 |
| Группы | COUNT DISTINCT FindingGroup.id; точные group members | Таблиц нет; grouping | Сумма размеров групп может превышать число находок; FR-011/028, AC-04/09 |
| Требования | COUNT DISTINCT Requirement.id, proposals/revisions не самостоятельные требования | Таблиц нет; §7 | Для «действующих» согласовать фильтр; для общего количества предлагается все идентичности, включая Rejected; FR-014–016/029, AC-05/09 |
| Решения | По одному действующему представлению Requirement; Approved сохраняется до принятия proposal | Таблиц нет; decisions | Draft — отсутствие относящегося решения, не выдуманная HumanDecision; AI не Approved; FR-018/024/026/027, AC-08/09 |
| Открытые блокеры | Отдельно число открытых blocking VerificationIssue и число Requirements с ними; вопросы отдельно | Таблиц нет; verification/resolution | В прототипе stats.blockers считает требования; нельзя подписывать «число замечаний»; старые issues не закрываются новым AI; FR-019/025/030, AC-06/08/09 |
| Частичная/полная утрата оснований | Проекция выбранного evidence действующей revision; distinct удалённых source IDs и доступные выбранные пути | Нет evidence/удаления; §7 и deletion slice | История не доступное подтверждение; available не означает sufficient; Approved не отменяется; FR-021/023/029/031, AC-07/09/10 |
| Последняя обработка | Run по created_at DESC,id DESC, отдельно technical/semantic, состояние units | Runs нет; И2б не имеет list/latest endpoint | Самый новый run не обязательно успешный/полный/актуальный; inspect_text не semantic coverage; FR-007/023, AC-02/07 |

Для human decisions, blocker/loss фильтров и сравнения current/pending контекста
нужны явные определения до агрегирующего API. Прототип relatedIssues выводит
замечания связанных требований: это не обнаружения непосредственно на группе
и не уникальная сумма по проекту без DISTINCT issue.id.
Ни один показатель не считает независимых людей (FR-013).

## 6. Предложение F: фрагменты, находки, группы

Это проект физических пакетов и HTTP, **не окончательная исполнимая
спецификация семантического worker**. Каждому пакету перед кодом нужны
утверждённые DTO/DDL и точные правила исполнения. Внутренний AI 1.0 неизменен.

### 6.1 Общие правила таблиц

UUID приложения, timestamptz UTC, project_id NOT NULL, FK →projects,
UNIQUE(project_id,id); ссылки на state — составной FK с project_id и
идентичностью самого объекта, не только UUID состояния.
Исправляемый объект = header(current_state_id) + immutable states; current
ссылается на state своего объекта через deferred FK, как в И2а.
Состояние хранит id, project_id, object_id, previous_state_id?, created_at,
origin, author_id?, attempt_id?, local_id?. CHECK происхождения и автора:
ai требует attempt; human требует User; ai_and_human сохраняет AI lineage
и автора правки. Сервер определяет эти поля, клиент их не назначает.
UNIQUE(attempt_id,local_id) в каждой таблице защищает повторную вставку;
уникальность local_id во всём ответе проверяет AP-02 до записи. Сам по себе
набор UNIQUE разных таблиц не доказывает общую уникальность. Блокировка attempt
и однократный атомарный приём исключают независимое добавление второй части
того же ответа; отдельный универсальный реестр объектов не вводится.

Содержательный приём одного ответа атомарен; commit attempt и принятых
выходов — одна транзакция. Другая независимая unit сохраняет свой успех.
История не означает архив исходного текста в логах/JSON снимках.
Публикация AI никогда не передвигает человеческий current_state молча.

### 6.2 Пакеты хранения

| Пакет / таблица | Конкретные поля сверх общих / связи и ограничения |
|---|---|
| F1 feedback_fragments / fragment_states | Header: source_id, current_state_id; state: source_state_id, quote TEXT, start/end bigint, reliability usable/uncertain. Составной FK на source state своего source; CHECK 0≤start<end; при приёме exact quote и code-point границы; time_range для текстового среза отсутствует |
| F1 findings / finding_states | Header: current_state_id; state: text, types (непустое уникальное подмножество problem/request/observation/need), mode direct/inferred; авторство по истории. uncertainty_notes и open questions сохраняются отдельно от технической ошибки |
| F1 finding_evidence | Точный finding_state → fragment id/state, M:N; уникальная пара. На создании минимум один доступный фрагмент из принятого ответа; не достаточно простого FK, проверяет сервис |
| F1 finding_deleted_sources (в пакете удаления E) | finding_state → tombstone source_id; UNIQUE(finding_state_id,source_id). При удалении заменяет все evidence к удаляемым fragments этого source одной отметкой; не хранит fragment ID/quote/количество |
| F1 finding_scope / finding_context | Отдельные typed refs на рассмотренные source states и [start,end), disposition/reason; отдельно document id/state/locator. Scope не восстанавливается из цитат evidence |
| F1 result_uncertainties, open_questions и typed target tables | Текст/reason, attempt, blocking для вопроса; target на finding state либо primary unit. Отдельные FK-таблицы вместо нетипизированного object_id; добавляются target-типы при появлении groups/revisions. Неизвестный ответ человека не выдумывается |
| F2 finding_groups / group_states | Title, summary; header/current/история; group_scope по рассмотренным точным finding states, context отдельно document states |
| F2 group_members | group_state → finding id/state, M:N; UNIQUE пары. Состав не заменяет отдельные находки; поздняя правка finding не подставляется в группу автоматически |
| F2 group_conflicts / conflict_positions / position_members | Конфликт принадлежит group_state: description; минимум две позиции с description и точными member findings. Ссылки должны входить в допустимый рассмотренный состав; сохраняются все позиции |

Не вводятся транскрипты или файловое хранилище заранее. Для F1: один явный
TextSegment на один extract_feedback; минимальная предлагаемая политика —
весь сохранённый текстовый state как один сегмент при допустимом контексте.
Превышение вместимости не усекать; отказ с безопасной причиной либо отдельно
согласованная детерминированная сегментация. Числовые лимиты и модель нужно
утвердить перед реальными AI-вызовами. occurrence учитывает перекрывающиеся
совпадения; reliability наследуется, не повышается моделью.

F1 также сохраняет запись принятого coverage при fragments/findings=[] и
обязательной причине: отсутствие находок не потерянный результат.
F2 сохраняет covered/ungrouped наборы; каждую успешно рассмотренную finding
можно открыть отдельно. Вопрос без готовой группы не теряется: target=unit.

### 6.3 Предлагаемые HTTP-операции и примеры

Все read Member; write Member + Origin/CSRF. Списки UUID cursor и
{items,next_cursor}, без полного текста исходников ради списка.

| Операция | Предлагаемая форма / поведение |
|---|---|
| GET p/findings; GET p/findings/{id} | List summary: id,state_id,text,types,mode,authorship,freshness,basis_availability; detail добавляет evidence, uncertainty_notes, questions, considered_scope, context, group refs |
| GET p/findings/{id}/states/{state_id} | Точное сохранённое состояние/происхождение, без замены текущим |
| GET p/fragments/{id}/states/{state_id} | Только доступный exact fragment; quote/source_ref/text_ref/locator/reliability; 404 для удалённого/чужого |
| POST p/findings/{id}/states | {expected_state_id,text,types,mode} →201 новое состояние; evidence наследуется точно; origin назначается сервером |
| GET p/groups; GET p/groups/{id} | List: id,state_id,title,summary; detail: точные members, conflicts, questions, scope/context; history по states |
| GET p/groups/{id}/states/{state_id} | Точный сохранённый состав/позиции |
| POST p/groups/{id}/states | {expected_state_id,title,summary,finding_state_ids,conflicts} →201 state; ссылки/позиции проверяются; нет потери истории |

Пример чтения evidence находки (UUID в примерах обозначены именами):

```json
{
  "kind": "available",
  "fragment_ref": {"id": "<fragment UUID>", "state_id": "<state UUID>"},
  "source_ref": {"id": "<source UUID>", "state_id": "<source state UUID>"}
}
```

Цитата загружается по точной fragment ref, не по текущему source вместо неё.
После будущего удаления только `{kind:"deleted_source",source_id}` без
fragment ID/state/quote/позиции/хэша, по утверждённым AI-правилам.
Пример правки:

```json
{"expected_state_id":"<UUID>","text":"Уточнённая находка","types":["need"],"mode":"inferred"}
```

Предлагаемый ответ 201 этой правки включает новый state и provenance, например
`{id,state_id,text,types,mode,authorship:"ai_and_human",previous_state_id,
author_id,created_at,evidence,uncertainty_notes,questions,considered_scope,
context,group_refs,freshness,basis_availability}`. Здесь id находки прежний,
state_id новый, previous_state_id равен expected_state_id. История сохраняет
исходный AI state/attempt; group refs указывают, какое состояние действительно
было включено в группу, а не утверждают автоматическую перегруппировку.

201 возвращает detail нового state; stale expected_state →409 input_changed.
Неизвестный/чужой объект/state →404 not_found; state другого объекта своего
проекта →422 invalid_input; refs своего объекта, утратившие current →409.
Пустые/невалидные формы422, превышение лимита413 по согласуемым лимитам.
Expected_state не даёт exactly-once replay: повтор успешного сохранения
получит409; UI перечитывает, не создаёт новый state автоматически.
Отдельный idempotency store для правок сейчас не предлагается.

Источник/read/правка и group membership проверяются под Project lock с новыми
чтениями после ожидания; compute не держит lock. Поздний AI-ответ проверяет
свои ожидаемые состояния и human edits, иначе отменяется, а не перезаписывает их.
Новая находка не создаётся публичным POST с якобы AI origin: результаты принимает
только серверный путь validated attempt. Точные response DTO/лимиты F требуют
отдельной фиксации перед реализацией; эта таблица не является их утверждением.

## 7. Предложение R/V/H: требования, проверки, решения

### 7.1 Физические пакеты

Общие project/state FK и provenance из §6 применяются также здесь.

| Пакет / таблица | Поля, связи и ограничения |
|---|---|
| R requirements | id/project_id, current_revision_id, approved_revision_id?, effective_decision_id?; указатели на собственные revision/decision. Утверждённая редакция и рассматриваемый кандидат различаются |
| R requirement_revisions | requirement_id, revision_number, title/text/rationale, author/origin/attempt, created_at; UNIQUE(requirement_id,revision_number); неизменяемый контент; id одновременно state_id этой immutable revision |
| R revision_evidence | revision → exact finding id/state → выбранные fragment id/state. Проверка, что выбранный fragment действительно evidence выбранного finding state. Несколько findings/fragments и несколько требований на один finding допустимы |
| E revision_deleted_sources | revision + finding_state + source_id, UNIQUE тройки; отдельно от сохраняемого finding selection. Удаление стирает исходные fragment refs, оставляя одну отметку в выбранном основании |
| R revision_scope / revision_context | Рассмотренные finding states/coverage отдельно от выбранного evidence; typed document/group states и locators отдельно. Контекст не становится основанием |
| V verification_results | Точная revision, UNIQUE attempt_id, created_at, followup_previous_result_id?; четыре assessments без passed/Approved; сохранённые typed input/coverage и comparison_manifest |
| V comparison_manifest | result → точные revision refs/requirement_id/roles; proposal state при pending_change; required/considered ключи и extent project_snapshot/selected, причина selected. Набор фиксируется приложением |
| V verification_issues / issue_targets | result, local_id, category,text,reason,severity,blocking,blocking_reason; typed target links, question links; неизменяемое обнаружение со своим ID |
| H issue_resolutions | UNIQUE issue_id, kind, reason, author_id, created_at, followup_result_id?; not_applicable только Approver с обоснованием; исправление причины требует проверки затронутого вывода, не просто checkbox |
| H change_proposals / proposal_states | requirement, base_approved_revision, candidate_revision, author, reason, pending/approved/rejected. Header/current и история состояний; частичный UNIQUE(requirement_id) WHERE pending; draft этап не изменяет approved pointer |
| H human_decisions / decision_basis | Точная revision, author, action approve/reject, время, verification_result_id?, proposal_id?; review context refs, expected состояния и рассмотренные issues/resolutions/questions отдельно от факта решения; ключ/fingerprint идемпотентности команды |

Questions/uncertainties из §6 получают typed targets на revision/verification
и предложение по необходимости. Порядок миграций разрывает циклы
requirement↔revision↔decision через deferred constraints и добавление FK после
создания таблиц. Миграции append-only: сначала новые таблицы/ограничения,
никакого переписывания m01/m02a и сброса текстов. Номера пакетов окончательно
назначаются по актуальному head. R не требует немедленной реализации всего H.

Сохранение revision и evidence — одна транзакция; при повторе номер не
вычисляется без блокировки. Минимум одна finding с доступным путём к обратной
связи на создании, документ не удовлетворяет этому условию.
Проверка доступности не заменяет содержательной достаточности.

### 7.2 Предлагаемые операции и формы

| Операция | Request / response и права |
|---|---|
| GET p/requirements; GET p/requirements/{id} | Member; list/detail: id,current_revision,approved_revision,human_decision,verification,basis_availability,freshness,open_issues,open_questions раздельно |
| GET p/requirements/{id}/revisions | Member; сохранённые редакции с provenance, автором и временем, cursor; не универсальный event log |
| GET p/requirements/{id}/revisions/{revision_id} | Member; точный immutable контент, выбранные refs и контекст, текущее представление утраты без подмены refs |
| POST p/requirements/{id}/revisions | Member; {expected_revision_id,title,text,rationale,evidence} →201 revision; только неутверждённая текущая формулировка |
| POST p/requirements/{id}/proposals | Member; {base_revision_id,title,text,rationale,evidence,reason} →201 proposal+candidate revision; действующая Approved не меняется |
| GET p/proposals/{id} | Member; base/candidate, состояние и история указателей/решения |
| POST p/proposals/{id}/revisions | Member; {expected_proposal_state_id,title,text,rationale,evidence} →201 новый candidate revision/state; прежний сохраняется |
| GET p/requirements/{id}/verifications | Member; cursor, точная revision, scope, assessments, issues; старые блокеры не скрываются последним результатом |
| GET p/requirements/{id}/review-context | Member; точные revision/evidence/check/obstacles/proposal refs и непрозрачный review_token; без запуска AI |
| POST p/requirements/{id}/decisions | Approver + Origin/CSRF + Idempotency-Key; →201 HumanDecision; на повторе тот же факт после новой проверки доступа |
| POST p/issues/{id}/resolutions | Approver + Origin/CSRF; {kind:"not_applicable",reason,expected_issue_state_id} →201; исчезновение issue не разрешение |

Evidence в новой revision: `[{finding_state_id,fragment_state_ids:[...]}]`;
клиент не назначает origin, author или decision. Пример сохранения:

```json
{
  "expected_revision_id": "<UUID>",
  "title": "Сохранять выбранные фильтры",
  "text": "Пользователь может сохранить и повторно применить набор фильтров.",
  "rationale": "Повторная настройка описана в выбранной обратной связи.",
  "evidence": [{"finding_state_id":"<UUID>","fragment_state_ids":["<UUID>"]}]
}
```

Пример решения, с Idempotency-Key в заголовке:

```json
{"revision_id":"<UUID>","verification_result_id":"<UUID>","action":"approve","review_token":"<opaque>"}
```

Для proposal дополнительно proposal_id. Для reject verification_result_id
может отсутствовать: предварительная AI-проверка не становится обязательным
условием отклонения. Draft не хранится как решение AI или человека по умолчанию.
Review token не является правом и не заменяет повторную проверку Approver.
Нужны отдельные окончательные DTO/лимиты/replay rules/ошибки перед кодом H.

Иллюстрация предлагаемой read-модели после будущей утраты части оснований
и при открытом предложении (не production-данные и не дополнительное
утверждение окончательных enum):

```json
{
  "id": "<requirement UUID>",
  "current_revision": {"id":"<r1 UUID>","title":"Название","text":"Действующая формулировка","rationale":"Обоснование"},
  "approved_revision": {"id":"<r1 UUID>"},
  "human_decision": {"id":"<decision UUID>","revision_id":"<r1 UUID>","action":"approve"},
  "verification": {"revision_id":"<r1 UUID>","result_id":"<check UUID>","freshness":"requires_update"},
  "basis_availability": {"revision_id":"<r1 UUID>","status":"partial_loss"},
  "pending_proposal": {"id":"<proposal UUID>","candidate_revision_id":"<r2 UUID>","state":"pending"}
}
```

Полный detail также включает evidence/context, open_issues/open_questions,
considered_scope и provenance. Действующее решение по r1 сохранено;
candidate r2 не утверждён. При отсутствии решения/проверки/предложения
соответствующее поле null, а не синтетический Approved или успешная проверка.

Общие 401/403/404/422/413 из §3. Предлагаемые 409: input_changed для stale
expected refs; proposal_already_open; decision_not_allowed; review_context_changed;
idempotency_conflict. Чужие/неизвестные refs404, неверная принадлежность state
другому объекту своего проекта422. Одинаковый decision key с другим payload409;
тот же ключ после утраты доступа не возвращает сохранённые данные.
Число сообщений/названий ошибок окончательно фиксируется с точным H-контрактом.

### 7.3 Атомарность решения и ограничения

Под Project lock перечитать текущую сессию/Approver, requirement/proposal,
revision/check, состояния основания и comparison manifest, все относящиеся
старые открытые блокеры/существенные вопросы и review context. Для approve
нужны актуальная проверка и пригодное доступное основание; количество ссылок
не доказывает смысловую достаточность. Показать человеку assessments и охват.
Полнота охвата и ограниченность сравнения различаются; запрет Approved нельзя
выводить только из любого partial без остальных утверждённых условий.

Approve proposal атомарно меняет действующую редакцию и записывает новый факт
решения; reject proposal сохраняет прежние Approved/content. Новая revision
не наследует Approved. Никакой worker не вызывает human decision вместо человека.
Повторная verification создаёт свои issues; старое not_applicable не закрывает
новое обнаружение. Принятие риска не снимает блокер. Для исправленной причины
нужно явно связанное подтверждение followup, а не отсутствие issue в новом AI.
Полный workflow ответов на открытые вопросы ещё требует согласования:
нельзя реализовать approve при неразрешённом существенном вопросе, выдумав
способ его закрытия. Независимые находки/требования остаются доступны.

### 7.4 Утрата и удаление

Будущий Owner-only deletion slice должен согласованно менять текущую
availability и очищать source/transcript/fragment states, locators/quotes и
refs из **всех** исторических evidence/scope/context/attempt inputs/coverage,
comparison/review/decision basis и технических output refs, где они присутствуют.
Остаётся только source_id + факт удаления в соответствующем основании.
Available evidence и deleted-source отметки — разные типизированные строки:
изменение проекции доступности не переписывает сохранённый текст revision
и не подставляет новое выбранное основание. В пакете E нужны аналогичные
сворачиваемые отметки в scope/input/basis, без FK на удалённые fragment states.
Ссылки на несколько удалённых фрагментов одного source сворачиваются; их ID
и количество не сохраняются в tombstone. Производные формулировки/авторство
могут сохраниться; это не доступное свидетельство. Исторический Approved
сохраняется, новый approve без пригодного доступного основания запрещён.
Поэтому availability отдельно от sufficiency и freshness; partial_loss/all_lost
в списках не новый human decision. Реализация удаления не входит в И2б/O1.
До появления согласованного удаления API не принимает tombstone от клиента.
Поздний worker не публикует по удалённому входу и не восстанавливает проект.

## 8. Обработка: ближайший исполняемый срез только после утверждения И2б

Текущее [runtime](../../backend/feedback2req/runtime.py) делает check_schema
и завершает worker-check. [Compose](../../compose.yaml) задаёт restart=no.
Таблиц runs/units/attempts/results и HTTP start/retry нет. Рабочего фонового
цикла, lease, heartbeat, watchdog и интеграции AI-провайдера пока нет.
Автономные схемы/валидатор и evals другой ветки не доказывают runtime AI.

И2б rev3 остаётся ближайшим предложением к окончательному утверждению:

1. Новая m02b: processing_runs/processing_units/stage_attempts/technical_results,
   project/state FK, terminal checks, UNIQUE attempt result и retry predecessor.
2. Только POST p/runs, GET p/runs/{id}, POST p/units/{id}/retries. Обязательный
   Idempotency-Key POST, canonical UUID/fingerprint; ссылки на точный state.
3. Один реальный inspect_text: len code points и UTF-8 bytes сохранённого
   текста; execution_kind=technical, ai_performed=false. Ни находок, ни AI.
4. Claim/heartbeat/completion короткими транзакциями Project→unit→attempt;
   проверка прав инициатора/состояний и fencing до публикации. Успешные units
   сохраняются при соседнем failed. Независимые результаты не откатываются.
5. Lease/recovery и reconciliation неопределённого COMMIT по §5 rev3;
   failed не возвращается автоматически в очередь. Retry только ручной,
   с expected_attempt_id и новым run/unit, прежний исход неизменен.
6. Реальные Docker-тесты выхода/restart и минимальная согласованная Compose/CI
   интеграция. Отдельный recovery-сервис, Redis/Celery не добавляются.

10 s — бюджет короткого I/O, не всей compute; inspect_text compute ≤45 s,
deadline 60 s, heartbeat его не продлевает. Startup/reconnect/reconciliation/
shutdown имеют отдельные сроки. Временная недоступность БД с работающим backoff
не разрешает SIGKILL. При повреждённом канале состояния без доказательства
идентичности/фазы — unhealthy и операторский restart, а не угадывание PID.
Внешний probe с init/on-failure существует пока только в спецификации.

Цепочка рестарта не подтверждена экспериментом. Ранний startup, manual stop
и restart Engine требуют отдельных проверок; on-failure не обещает автозапуск
после restart Engine, как указано в [официальной документации Docker](https://docs.docker.com/engine/containers/start-containers-automatically/).
Наличие контейнера/unhealthy не доказательство восстановления worker.

И2б GET требует известный run_id; он не даёт журнал/последний run после потери
ID браузером. Для экрана истории позже отдельно предлагается GET p/runs с
cursor и порядком created_at/id, либо latest projection в overview. Выбор и
точный контракт согласуются после И2б; не расширяют три операции rev3 молча.

Семантическое расширение не сводится к добавлению значения operation:
текущие CHECK допускают inspect_text и один source/document input. Перед AI
нужны новая миграция для typed unit/attempt inputs (включая несколько findings,
groups, documents, revision/comparisons), сегменты/coverage, связь локальных
выходов, актуальность и длительные compute/deadline по операции. Сохранить
существующие технические runs и не ослаблять их инварианты. Граф всего MVP
и автоматическое продолжение не вводить заранее.

## 9. Последовательность реализации и отдельные точки согласования

| Срез | Данные / зависимости | Объём и результат | Необходимое согласование и проверка |
|---|---|---|---|
| O1 Обзор материалов | И1/И2а, без AI | Только GET overview §4; два COUNT без текстов | Точная форма O1 и разрешение реализации; O1-T1–T6, PG snapshot/isolation/restart |
| P1 И2б | Сохранённый точный текст | m02b, три HTTP, настоящий worker inspect_text | Утвердить rev3 и отдельно код/Compose/CI; все C1–C4/реальные Docker из И2б |
| P2 Подготовка semantic inputs | Проверенный исполнитель P1 | Typed inputs/сегмент/контекст/coverage и request binding; без provider вызова | Точная физическая дельта/лимиты и гранулярность, AP-01–05; никакого усечения |
| F1 Извлечение и чтение | P2, AI extract 1.0 | §6 fragments/findings/evidence/scope/questions, reads и human states | DDL/HTTP F1; provider/model/access/budget и содержательная оценка отдельно; exact quote/occurrence, partial reject, empty success |
| F2 Группы | Принятые finding states | Groups/M:N/conflicts, reads/условная правка | DDL/HTTP F2; no lost findings, ungrouped coverage, противоположные позиции и AP-06–08 |
| R Кандидаты | Findings/evidence, группы/документы как контекст | Requirement/revisions/rationale/история, generation 1.0, чтение/условная правка | Точная схема/HTTP; без document-only evidence и без автоматического изменения Approved |
| V Проверка | Точные revision/evidence/context, comparison manifest | verify 1.0, assessments/issues/questions, read checks | Manifest/scope/batching/DDL/HTTP; AP-09–11, own revision не дубль, старые issues остаются |
| H Решения/предложения | R/V, актуальный Approver | Proposal/revisions, review context/decision/resolution | Полный write/replay/вопросы и DDL; AP-12–14, гонки решений/отзыва прав/оснований, одно pending |
| E Удаление/актуальность | Все typed refs и утверждённые правила удаления | Owner preview/confirmation, очистка исходных refs, stale derived results | Точные HTTP/DDL/cleanup контракт; AC-10/11, поздний worker и исторические Approved |
| A Аналитика | Реальные F/R/V/H/E | Согласованные aggregates/groups/decisions/blockers/loss и latest run | Определения §5, no_results/coverage/freshness, single snapshot, unique identity counts |

O1 независим от И2б, его можно утвердить отдельно. Переход к P1 не утверждает
P2/F/R/V/H автоматически. Чтение результатов не требует AI-вызова на каждый GET.
Полноценный semantic UI принимается только на сохранённых настоящих результатах,
после содержательных оценок по шести AI-инвариантам. Внешние платные вызовы
этой подготовкой не разрешены. ASR/медиа остаются отдельным последующим срезом.

## 10. Проверки, ограничения и фактические изменения

### 10.1 Что проверено сейчас

- Состояние git/remote/worktree и различия указанных четырёх веток; исходное
  дерево чистое, backend/Compose frontend-ветки совпадает с main.
- Реальные маршруты/DTO, права и project locks, material service/repository,
  models, m01/m02a и Alembic env, runtime/Compose, профильные backend-тесты;
  референс prototype и статусы утверждений сопоставлены с предложениями.
- В текущей ветке уже есть f06e4d1: AUD-01 безопасно отклоняет NUL project
  и некодируемый SecretStr, AUD-02 проверяет exit конечного worker-check в CI.
  Повторно эти изменения не добавлялись; новых подтверждённых дефектов
  действующей реализации в этом проходе не установлено.
- Docker Engine недоступен: отсутствует pipe dockerDesktopLinuxEngine при
  docker version/image ls. Docker Desktop/Engine не запускался, чужие
  контейнеры не останавливались. Невозможность выполнить PG/Docker проверки
  не трактуется как PASS и не исправляется на рабочем окружении другого агента.

Результаты 71 passed, Ruff, HTTP/PG restart и CI gate из предыдущего аудита
относятся к прогонам 2026-10-23, а не новому запуску 2026-10-26. В этой задаче
нет изменений исполняемого кода/миграций, требующих выдавать такой прогон за новый.
Текущая валидация документа: git diff --check (включая no-index для нового
файла), локальные relative links, таблицы/JSON примеры, границы изменений
и SHA-256 исходной rev3 И2б. Все эти структурные проверки прошли;
они не проверяют исполнимость будущего API или SQL/Docker-протокола.
Независимое ревью этого нового предложения не проводилось.

### 10.2 Приёмка последующего кода, не пройденные сейчас тесты

| Уровень | Необходимые проверки |
|---|---|
| Документ / контракт | Закрытые DTO/request/response, FK/cardinality, FR/AC, role/error mapping; статус proposal не превращается в approval |
| Модульный | Канонизация UUID/fingerprint, transition/retry, Unicode/locator/occurrence, typed evidence и AI application checks; без внешних вызовов |
| Настоящая PostgreSQL / FastAPI | Empty и populated upgrade, composite FK/CHECK, atomic accept, неизвестные/чужие refs, сессии/Origin/CSRF, отмена прав, конкурентные writes/decisions и повтор команд; raw text не отражается |
| Настоящий Docker | API/PG/worker рестарты с собственным volume/network; сохранение IDs/text/result/decision; unknown COMMIT и потеря lease; C1–C4 И2б; restart policy/init/probe на реальном target, не симуляция unhealthy |
| AI содержательное качество | Настоящая модель по отдельному разрешению; все шесть инвариантов, конфликт/неопределённость/смысловая достаточность, scopes и рекомендации человеку; валидный JSON не достаточное доказательство |

Изменён только этот новый файл. Backend, frontend, migrations, Compose,
утверждённые документы, I2B_SPEC и evals/ai в этой задаче не менялись.

## 11. Конкретные решения перед продолжением

1. **O1:** утвердить §4 как ограниченный read-контракт и разрешить его реализацию
   без миграции. Это ближайшее независимое улучшение реального обзора.
2. **И2б:** окончательно утвердить точную rev3 с указанным SHA и отдельно
   разрешить m02b/три HTTP/worker/Compose/CI и приёмочные проверки. Публикация
   аудита или общий запрос поддержки прототипа этого согласования не заменяет.
3. **Перед semantic кодом:** отдельно утвердить точную физическую дельту P2/F1
   и HTTP, политику сегментации/лимиты, затем provider/model/условия и бюджет
   реальных вызовов. На следующих срезах — точные R/V/H-контракты, разрешение
   существенных вопросов и определения аналитики. Сейчас их не нужно решать
   для O1 или технического И2б.

Новых продуктовых правил/AI-контрактов этим предложением не утверждается.
Дальнейшая реализация зависит от конкретного согласуемого среза, а не от
общего согласия на все будущие подсистемы. До него новый API/DDL/worker не создаётся.
