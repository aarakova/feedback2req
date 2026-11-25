# Пакет B: сохраняемые требования, проверка и решение человека

**PROPOSED, редакция B.2 от 2026-11-25. Не утверждено.**
Подготовлено по поручению пользователя «находки → сохраняемые требования →
проверка → решение человека». Разрешена только подготовка. Новые миграции,
HTTP DTO/handlers и runtime этой работой не добавлены. A.2 и C не утверждаются.

База: согласованная integration/full-workflow-ui 6000656 с F2/F3 и автономными
generate_requirements/verify_requirement; рабочая ветка подготовки
feat/backend-requirements-contract от 41e3ab2 (6000656 + документы A.2).
Непринятые изменения других worktree не копируются.

Продуктовая baseline неизменна: FR-014–027, AC-05/08, BR-009–015,
DOMAIN §§6–9, DATA_MODEL §§2–6, DEC-003/004/005 и AI_CONTRACTS §§7.3/7.4/9.
Доступное основание, его достаточность, свежесть проверки, execution state и
человеческое решение — разные аспекты. Наличие FK или completed не доказывает
смысловую достаточность. Утрата источника не отменяет старое Approved.

## 1. Четыре последовательных результата

| Этап | Проверяемый результат после утверждения | Что ещё не включается |
|---|---|---|
| B1 | generation enqueue → существующий автономный генератор → атомарно сохранённые новые Requirement и первые immutable revisions с exact evidence; Run читает IDs/coverage/questions, включая пустой ответ | Человеческие решения, изменения Approved, автоматический verify |
| B2 | Список/точное чтение/история; Member сохраняет новую редакцию неутверждённого требования с expected-current guard и idempotency | Прямое редактирование Approved, решения Approver |
| B3 | Проверка реально сохранённой редакции; immutable assessments/issues/questions, scope/history и накопленные открытые blockers | AI не закрывает старые notes и не меняет human decision |
| B4 | Approver decisions/resolutions; отдельное предложение изменения Approved; атомарная замена действующей редакции только новым Approved | Отзыв Approved без предложения, публичный cancel/retry, глобальные KPI |

Каждый этап — отдельные миграция/коммит/PG acceptance run и handoff frontend.
Следующий этап не маскирует отсутствие предыдущего. Контракт B можно утвердить
целиком либо явно перечисленными этапами; принятие B1 не разрешает B4.

## 2. Физическая модель и совместимость

Предлагаются Alembic версии m04a_requirements → m04b_requirement_writes →
m04c_verification → m04d_human_decisions, первая после m03. Имена/head перед
реализацией сверяются с параллельными ветками; старые миграции не правятся.
Это проект DDL, не созданные файлы миграций. Каждый upgrade транзакционный,
без преобразования/удаления F1/F2 данных; destructive downgrade не предлагается.

Общие соглашения: UUID серверные; project_id NOT NULL; created_at TIMESTAMPTZ
NOT NULL DEFAULT clock_timestamp(); UNIQUE(project_id,id) для адресуемых строк.
Все внешние ссылки включают project_id; object/state пары проверяются составными
FK. TEXT без копирования исходного материала в журнал. Неперечисленные поля
NOT NULL; nullable обозначено `?`. Изменяемые projections не являются новыми
содержательными состояниями Revision. Review/result/decision refs — immutable,
state_id=id. Ordinal BIGINT >0, уникален в пределах Requirement.

### B1 / m04a: кандидаты и точные основания

| Таблица | Поля и ограничения |
|---|---|
| requirements | id, project_id, current_revision_id, approved_revision_id?; deferred FK (project,id,current_revision_id) → revision того же requirement; approved FK аналогично; до m04d CHECK approved_revision_id IS NULL |
| requirement_revisions | id, project_id, requirement_id, ordinal, previous_revision_id?, derived_from_revision_id?, title,text,rationale,authorship,author_id?,generation_attempt_id?,local_id?,created_at; UNIQUE(project,requirement,id), UNIQUE(project,requirement,ordinal), UNIQUE(generation_attempt_id,local_id); parent/base FK того же requirement |
| revision_considered_findings | project,revision_id,finding_id,finding_state_id; PK всех refs; FK → exact revision/finding, CHECK finding_state_id=finding_id (текущий immutable F1) |
| revision_evidence | id,project,revision_id,finding_id,finding_state_id,source_id; FK выбранной finding → revision_considered_findings; техническая source identity хранится отдельно от доступного содержимого |
| revision_evidence_fragments | project,evidence_id,finding_id,source_id,fragment_id,fragment_state_id; PK(project,evidence_id,fragment_id); FK → evidence того же finding/source; FK(project,finding_id,fragment_id) → F1 finding_evidence; CHECK fragment_state_id=fragment_id; FK(project,source_id,fragment_id) → exact F1 fragment |
| revision_evidence_losses | project,evidence_id,source_id,recorded_at; PK(project,evidence_id); FK → exact evidence/source lineage; только технический ID и факт утраты, без fragment ID/quote/locator; вход B не позволяет создать такой факт |
| revision_document_context | project,revision_id,document_id,state_id,start,end; PK всего excerpt; FK → точный document state, CHECK 0≤start<end; end≤len(text) проверяется при сохранении |
| revision_group_context | project,revision_id,group_id,state_id; PK exact refs; composite FK → group_states своего project/group/state |
| ai_input_bindings | project,unit_id,key,linkable,kind и типизированные nullable столбцы ссылки (ниже); PK(project,unit,key); source roles/selected/considered различаются, range сохраняется для документа |
| ai_context_keys | project,unit_id,key,parent_binding_key,source_attempt_id?,source_local_id?,annotation_id?; nested QuestionView key без ложной StateRef/evidence; FK parent binding и origin того же project |
| requirement_annotations | id,project,attempt_id,local_id,kind=question/uncertainty,text?,reason,blocking?,created_at; question требует text+blocking; uncertainty не получает выдуманный blocking; UNIQUE(attempt,local_id) |
| annotation_related | project,annotation_id,ordinal,origin,key,input_unit_id?,input_binding_key?,input_context_key?,output_revision_id?,output_annotation_id?,output_issue_id?; ровно одна typed ветвь input binding/context-key либо output; в B1 output_issue_id отсутствует до m04c |
| annotation_revision_links | project,annotation_id,requirement_id,revision_id; FK → exact revision своего Requirement, FK → annotation; связи immutable |
| requirement_annotation_scopes | project,requirement_id,annotation_id; PK всего tuple; FK Requirement/annotation того же project; annotation_revision_links ссылается на scope; deferred trigger требует хотя бы одну revision link |

Тексты title 1–200, text/rationale/reason 1–8192 Unicode code points,
whitespace-only запрещён; обрезки и скрытой Unicode-нормализации нет.
Новый AI-кандидат: authorship=ai, author_id=NULL, generation_attempt_id/local_id
обязательны. В B2 human revision имеет author_id; собственный generation_attempt_id
NULL, previous/derived_from фиксируют происхождение. При правке AI-производной
формулировки authorship=ai_and_human, при чисто human lineage — human. Нельзя
присвоить человеческой правке старую попытку как якобы новый AI-вызов.

После публикации content/evidence selection/considered/context revisions,
notes и их related links неизменяемы: запрет UPDATE/DELETE ordinary write-path
и PostgreSQL triggers; новая формулировка или evidence selection — новый UUID.
Состав scope/evidence ненулевой для каждого кандидата: deferred constraint
trigger, по аналогии F2 cardinality. Наличие хотя бы одного доступного usable
fragment необходимо, но не объявляется доказательством достаточности.

revision_evidence_fragments — проекция доступных свидетельств, а не архив цитат.
Новый срез не реализует удаление. Будущий отдельно разрешённый FR-031 cleanup
должен атомарно убрать эти живые FK и содержимое Fragment, сохранив только
source_id + факт утраты в revision_evidence_losses. Ни quote, locator, timestamp записи
или старый source text не копируются в tombstone. Обычные API B не могут создать
deleted_source вместо доступного evidence. До такого cleanup FK препятствуют
опасному частичному удалению; B не объявляет FR-031 реализованным.
Deferred constraint запрещает одновременно live fragment links и loss fact для
одного evidence. При публикации нового кандидата loss rows запрещены, а available
evidence обязательно. Уже сохранённая история может иметь только loss fact;
содержимое revision не переписывается. Consumer-side B4 проверяется на явно
синтетическом историческом loss fixture в PG; это не тест полноценного удаления
F1/F2 источника. Producer destructive cleanup и его полномочия — отдельный срез.

### Типизированная привязка ключей

ai_input_bindings — закрытый tagged union, **не** непроверенный polymorphic UUID:
finding_id; fragment_id; document_id/state/range; group_id/state;
revision_id; verification_id; issue_id; resolution_id; human_decision_id; proposal_id.
CHECK требует ровно столбцы выбранного kind; каждая ветвь имеет свой composite
FK в соответствующую таблицу. В m04a разрешены первые четыре и revision;
m04c добавляет verification/issue, m04d — resolution/decision/proposal и их FK.
Нужные UNIQUE на существующих F1 tuples добавляются без переписывания строк.
Все keys immutable в рамках Unit; source Unit и operation проверяются сервисом.
Keyless refs prior_decision/previous_checks/base/proposal тоже имеют typed bindings:
сервер назначает внутренний key в зарезервированном @history namespace с
linkable=false. Он не добавляется в AI JSON и не становится допустимым related key.
Для настоящего canonical key linkable=true; related FK/trigger проверяет эту
границу. Благодаря этому история не хранится только как непроверенный UUID в JSON.

Nested QuestionView не получает выдуманный AI StateRef kind: ai_context_keys
указывает на parent binding и сохранённую annotation либо F1 attempt/local_id.
Для последнего existence local_id в JSONB F1 notes проверяет SQL constraint
trigger; parent/project/application binding перепроверяются при приёме.
Related на context key выдаётся как context_key + parent_ref, без превращения
в finding/evidence. Output mappings ссылаются только на созданные этой attempt
revisions/issues/notes. Kind/id/state_id не принимаются от модели.
Связи notes могут указывать на другие notes; читаются как плоские typed refs,
без рекурсивного разворачивания/бесконечного обхода. Это не новый AI reference kind.
CHECK и composite FK/constraint trigger annotation_related требуют, чтобы output
действительно принадлежал той же attempt/result, а не любому UUID проекта.

Generation annotations сохраняются и без кандидатов (принадлежат Attempt).
Input-note относится к revision, если затрагивает её considered finding;
output-note — к указанной candidate revision. Сохранённые links позволяют
показать исходный scope, а не объявлять любой вопрос вопросом всего проекта.
При новой генерации по тем же exact findings в контекст входят и неразрешённые
input-questions прежних generation attempts, в том числе с нулём кандидатов.
Новый candidate получает соответствующие links к старому note; его отсутствие
в новом ответе не стирает этот контекст. Resolution отдельного Requirement не
выдаётся за глобальное разрешение вопроса Finding или соседнего Requirement.

### B2 / m04b: человеческие сохранения

requirement_commands: id,project,actor_id,operation,idempotency_key,fingerprint,
result_revision_id?,result_proposal_id?,result_decision_id?,result_resolution_id?,
created_at; UNIQUE(project,actor,key); ровно один typed result FK. В m04b
разрешён revision_create; остальные ветви/их FK добавляет m04d.
Это receipt человеческого действия, **не** вторая AI очередь/lifecycle.
Payload/credentials/raw evidence в receipt не дублируются; хранится SHA-256
канонического body и immutable result identity.

Ordinal назначается под Requirement lock; нет MAX+1 без блокировки. B2 разрешает
изменять только текущую неутверждённую редакцию. После создания R2 её собственное
решение Draft (нет HumanDecision для R2), даже если R1 имела Rejected/проверку.
Прямую правку Approved отклоняет 409 proposal_required.
previous_revision_id — предыдущая сохранённая revision в истории Requirement;
derived_from_revision_id — содержательная база правки (у proposal — base Approved).
Обе принадлежат тому же Requirement и имеют меньший ordinal; циклы запрещены
constraint trigger. История создания не подменяет содержательную derivation.
Самостоятельная приёмка B2 проверяет реальные Draft данные; Approved/Rejected
и старые verification появляются на следующих этапах. Соответствующие guard
и отсутствие наследования решения проверяются повторно в сквозном B3/B4
прогоне, без фиктивных записей ещё не созданных таблиц.

### B3 / m04c: проверки и обнаружения

| Таблица | Поля и ограничения |
|---|---|
| verification_targets | project,unit_id,requirement_id,revision_id,scope_kind,selection_reason?,manifest JSONB,manifest_hash CHAR(64),material_hash CHAR(64); UNIQUE(unit_id); exact revision FK; manifest содержит refs/roles/IDs истории, не raw texts |
| verification_results | id,project,requirement_id,target_revision_id,attempt_id,coverage JSONB,comparison_scope JSONB,manifest_hash,material_hash,created_at; UNIQUE(attempt_id), composite target FK; accepted result отделён от Attempt failure |
| verification_assessments | project,result_id,kind,conclusion,rationale,considered_keys JSONB; PK(project,result,kind), enum четырёх kinds и трёх conclusions из AI 1.0; deferred trigger требует ровно 4 |
| verification_issues | id,project,result_id,requirement_id,target_revision_id,local_id,category,text,reason,severity,blocking,blocking_reason,created_at; UNIQUE(result,local_id), composite FK на exact result/target |
| verification_issue_questions | project,result_id,issue_id,annotation_id; FK обеих сторон того же result; только question kind, не uncertainty |
| verification_followup | project,unit_id,previous_result_id,issue_id? или question_id?; exact project/Requirement принадлежность; вопрос не выдаётся за AI VerificationIssue |

requirement_annotations получают nullable verification_result_id, FK и связь с
точной target revision; все issues/questions/uncertainties сохраняются атомарно.
Публичные notes имеют UUID, source verification_ref и target_revision_ref.
Серьёзность low/medium/high и blocking независимы. Для blocking=true нужен
blocking_reason; Question.blocking не выводится из severity связанного issue.
Новый текст, похожий на старое issue, получает новый ID, не auto-dedup.
Точные assessment kinds: support, contradictions, ambiguity, duplicates.
Conclusions: no_issue_found, issues_found, inconclusive — без общего passed.

**Открытые обязательства:** для решения по Requirement берётся объединение
неразрешённых issues и blocking questions, привязанных к его сохранённым revisions,
включая старые проверки и незавершённое предложение. Пустой новый issues[] и
переключение current revision не удаляют старые обнаружения/links.
Исторический target каждого note виден. Применимость старого замечания к
изменённой формулировке разбирает человек; backend не объявляет его исчезнувшим.
Generation question может затронуть несколько Requirement: разрешение имеет
обязательный requirement_id scope и не закрывает вопрос соседнего Requirement.
Uncertainty показывается, но без выдуманного флага блокировки.

### B4 / m04d: решение и предложение

| Таблица | Поля и ограничения |
|---|---|
| requirement_proposals | id,project,requirement_id,base_revision_id,proposed_revision_id,created_by,reason,status=open/accepted/rejected,created_at,closed_at?,closing_decision_id?; exact same-requirement FK; partial UNIQUE(project,requirement) WHERE status='open' |
| human_decisions | id,project,requirement_id,revision_id,proposal_id?,verification_id?,decision=Approved/Rejected,rationale,actor_id,evidence_confirmation JSONB?,created_at; exact revision/result FK; Approved требует verification и подтверждение достаточности |
| issue_resolutions | id,project,requirement_id,issue_id? или question_id?,kind=corrected/not_applicable,reason,actor_id,followup_verification_id?,created_at; ровно один note; две partial UNIQUE(project,requirement,issue_id)/(project,requirement,question_id) для выбранной ветви, typed FK; corrected требует followup result |

Убирается временный CHECK approved_revision_id IS NULL; deferred FK/trigger
требует соответствующий HumanDecision Approved той же revision/Requirement.
CHECK approved_revision_id IS NULL OR approved_revision_id=current_revision_id.
Нельзя выставить указатель на произвольную revision без решения. Role/membership
перепроверяются транзакционно, исторический actor остаётся различим после отзыва прав.
Иммутабельные decisions/resolutions не переписываются. Статус proposal закрывается
ровно один раз в той же транзакции, что decision и (при Approved) header switch.

Не является частью B прямой перевод уже Approved в Rejected без change proposal.
Это ограничение предложенного API-среза, не запрет будущего отдельного доменного
сценария. Approved base остаётся действующей при open/rejected proposal; target
proposal revision до своего решения Draft. Proposal accepted делает именно её
current+approved; предыдущие текст, decision, actor/time сохраняются.

Для межтабличных guard добавляются UNIQUE(project,requirement,target_revision,id)
на verification_results и UNIQUE(project,requirement,proposed_revision,id) на
proposals. HumanDecision имеет composite FK именно на эти tuples, а не только
на UUID result/proposal. Resolution question FK идёт в requirement_annotation_scopes;
constraint trigger проверяет kind=question. Для issue используется composite FK
(project,requirement,issue_id). Чужой note того же проекта тоже не разрешается.

## 3. Очередь, автономные AI и транзакции

Новых очередей нет. m04a расширяет Run.operation generate_requirements и Unit
input_kind=generation_set; m04c добавляет verify_requirement / revision_target.
Source/document поля Unit для обоих NULL. Старый F1 claim заменяет исключение
finding_set на явный allowlist source/document + inspect/extract, чтобы не
захватить новый тип и не вызвать F1 current_input. F3 остаётся finding_set/group.
run_view тоже диспетчеризуется явно по operation: новые input/results не должны
попасть в F1 input_ref. Deferred constraints требуют нужный typed snapshot для
generation_set/revision_target; queued Unit без обязательных входов не сохраняется.
Приоритет прежних F1/F3 сохраняется, затем generation/verification; гарантии
справедливости/TTL не добавляются и это ограничение видно оператору.

Одна generation Unit на выбранный набор; одна verification Unit на exact target.
Authenticated command сохраняет Run/queued Unit/bindings без user session token.
HTTP использует проверенные Actor/Tx без nested-session auth. Claim создаёт одну
Attempt с ownership/provenance после preflight; provider вызывается только после
подтверждённого COMMIT claim. Inference без Project lock; 5 s heartbeat, lease
30 s, deadline 120 s, прежний bounded child supervisor. После истечения/unknown
COMMIT нет requeue/model replay. Ошибка операции не откатывает чужие результаты.

```python
candidate = generate_requirements(request, generation_provider, verify_context=trusted_db_check)
# Atomically accept -> new Requirement/Revision UUIDs and exact evidence mapping.
report = verify_requirement(saved_revision_request, verification_provider,
    verify_context=trusted_db_check, required_context=trusted_history_fields,
    review_plan=None)  # single-call MVP, not an invented partial executor
```

В B1 только новые кандидаты, без автоматической замены существующего Requirement.
previous_candidates/change_reason генератора пока не публично подключены.
B4 создаёт human proposal; AI не назначает ему принятие. Verify — отдельная
команда после сохранения, а не второй вызов генератора и не auto Approved.

Каждый AI aggregate принимается целиком: structure + AP-01–14 + live access,
owner/lease/deadline, exact inputs/evidence/target, complete comparison manifest,
prior decisions/questions/issues. Invalid output → failed/invalid_response без
частичных revisions/results/notes. Валидные 0 candidates сохраняют coverage и
notes в Run. Partial overall generation coverage допустим по отдельным findings;
partially_processed одного finding без доверенного плана отклоняется.

Verification MVP не реализует aggregator: partially_processed без независимо
доверенного ReviewPlan отклоняется, план не строится из model JSON. Сохраняются
completed/insufficient_information/not_processed и все четыре оценки; not_processed
не является no_issue_found. Selected scope не объявляется project-wide.

Default project_snapshot собирается сервером: текущие неотклонённые revisions
получают AI role current, open proposals — pending_change, новые сохранённые
кандидаты — new_candidate. History имеет role history. Это точные литералы AI 1.0,
а не новые statuses; pending_change несёт proposal_ref. Exact target исключён, одинаковые RevisionRef
объединены с union roles, history не заменяет required set. Своя base revision
может быть history/change context, не possible_duplicate другого Requirement.
До публикации под Project lock заново сравнивается manifest refs/roles/states/
open-history IDs. Новый кандидат/proposal/decision или потеря источника могут
сделать результат устаревшим → cancelled/input_changed, не тихое обновление scope.

Для прежнего решения/изменения/issue followup backend сам выставляет
required_context prior_decision/change_context/followup. Question-only followup
не притворяется issue_ref: note остаётся в target.open_questions со стабильным
QuestionView key, previous_checks и trusted verification_followup. AI 1.0 не
получает нового поля question_refs; наличие этого контекста проверяет callback.

Сохраняются provider/model/synthetic/ai_performed, adapter/prompt/schema versions
и hash версии конфигурации в attempt metadata (новые nullable столбцы; прежние
F1/F2 строки не переписываются). Ни provider, ни доверенный review plan клиент
не задаёт. Production не импортирует experiments/qwen/evaluator/Z3. Реальная
модель не включается; тесты — Replay/injected synthetic, без fallback при ошибке.

### Актуальность материала и события review

При приёме сравнивается полный manifest_hash: в том числе история, прочитанная
AI, не должна меняться незаметно во время compute. После сохранения material_hash
определяет свежесть target/evidence/comparison refs/roles и доступности. Новый
resolution сам по себе не меняет material_hash и не требует ещё одного AI-вызова.
Review hash отдельно меняется при notes/resolutions/decisions; новая блокировка
всегда учитывается решением, даже если material freshness=current.

Для нового Approved дополнительно требуется, чтобы проверка несла относящийся
последний prior_decision: для proposal это решение base Approved, для обычной
target — её прежнее решение, если есть. Его смена до нового решения требует
актуальной проверки соответствующего контекста. Само создаваемое Approved не
объявляет использованный результат задним числом устаревшим. Freshness не равна
ни eligibility на все команды, ни человеческой оценке достаточности.

## 4. Человеческая транзакция Approved

Порядок locks: Project → Requirement → Proposal (если есть) → нужные immutable
result/note rows; общий порядок UUID для множества заметок. Никаких model calls
в транзакции решения. После текущей auth/membership/Approver проверки:

1. Найти receipt: при совпадении fingerprint вернуть прежний объект без нового
   действия. Иначе проверить expected_current_revision_id/expected_review_hash.
2. Проверить exact target: current неутверждённая revision либо revision этого
   open proposal с тем же base Approved. Нельзя решить по произвольной history.
3. Approved требует принятую актуальную проверку этой revision, reviewed=true,
   а также доступное usable evidence и человеческое evidence_confirmation.
   Чистые checks сами по себе не подтверждают достаточность. Inconclusive/
   insufficient_information видны отдельно; не превращаются в автоматический
   запрет только по названию enum или в автоматическое разрешение. Непросмотренная
   target (not_processed) не является выполненной проверкой.
4. Перечитать все старые/новые открытые blocking notes этого Requirement.
   Любой открытый blocker или blocking question запрещает новое Approved.
   Никакого решения «принять риск». Rejected не требует вызова AI/чистых checks.
5. Записать immutable HumanDecision + receipt; при proposal атомарно закрыть его.
   Только Approved target меняет current/approved указатели.

Corrected resolution требует отдельного принятого свежего followup verification,
связанного с точным note и рассматриваемой revision того же Requirement,
фактического рассмотрения затронутого вывода и человеческой причины. Один пустой
issues[] не закрывает ничего: Approver создаёт отдельный resolution. Новое note
другого результата не закрывается старым resolution. Not_applicable требует
Approver и явной причины, не последующей пустой проверки.

## 5. HTTP, errors и staged handoff

Точные DTO/пути/статусы и сценарии определены в
[передаче frontend](requirements-frontend-handoff.md). Все команды закрытые,
UUID/Origin/CSRF, no-store и error envelope текущего API сохранены. Role checks
действуют и при replay. Human receipt scope project/actor/key, operation+path+body
в fingerprint; AI start ключи сохраняют прежнюю область Run start. Unknown
COMMIT → same key или чтение known IDs, не новая генерация/решение.

Для server selection предлагаются 1–100 findings, ≤16 documents/groups,
≤100 comparisons; body 16 KiB (действующий общий предел), AI request/response
≤1 MiB. До 100 candidates/attempt, отказ всего oversized aggregate без truncation.
Достижение всех отдельных char/count bounds не гарантирует fit в общий body.
project_snapshot сверх caps отклоняется, не урезается; selected требует причины.
Ресурсные bounds — профиль серверного приёма, не изменение AI Schema 1.0.
Если AI-ответ проходит общую схему, но превышает серверные bounds, весь aggregate
отклоняется как invalid_response; отдельные части не обрезаются ради сохранения.

## 6. Критерии завершения этапов

| Этап | Обязательные проверки на настоящем PostgreSQL и API |
|---|---|
| B1 | M03→m04a сохраняет полный граф F1/F2; composite FK/ownership; M:N evidence; один отзыв→кандидат; document-only отказ; 0 candidates; duplicate local IDs; invalid rollback; exact states/revoke; concurrent claim; lease/restart; unknown enqueue/claim/final COMMIT без второй модели |
| B2 | GET current/exact/history с project isolation и live evidence; immutable UPDATE/DELETE отказ; concurrent revisions/ordinal; expected state conflict; same-key write replay; новая revision Draft и без старой проверки/решения; direct Approved edit запрещён |
| B3 | Ровно четыре assessments в БД; incomplete/selected scope; stale comparison membership; required history; notes stable IDs; пустая новая проверка сохраняет старый blocker; related/question_ids exact FK; generation questions при 0 candidates; unknown COMMIT без дубликатов; потеря источника не создаёт чистый support |
| B4 | Member vs Approver и revoke в гонке; blocker/question запрет Approved; old Approved после утраты evidence сохранён, новое Approved без доступного основания отказ; одна open proposal; reject сохраняет base; approve переключает только exact target; corrected+followup/not_applicable reason; новое issue не наследует старое resolution; same-key human unknown COMMIT; решение новой revision не наследуется |

Каждый этап: отдельный SQL/API отчёт и F1/F2 regression, synthetic provenance;
непройденное/недоступное — NOT RUN, не PASS. Проверка формы JSON/SQL не доказывает
semantic support или semantic correction. SQL constraints проверяются прямыми
INSERT/UPDATE, а concurrency/COMMIT/access — транзакциями, не только mocks.

## 7. Зависимости и граница решения

Это конкретный вариант для отдельного утверждения B.2. До него — только
подготовка; никакого M04 или новых POST/моделей в runtime. Существенность правки
не определяется выдуманным численным порогом: новая revision всегда отличима,
её проверка не наследуется; влияние на основания оценивается по действующим правилам.

Независим от публичного A.2: генерация берёт готовые F1 findings, group refs
необязательны. Пакет C/формальная модель и реальный Qwen не нужны synthetic пути.
Перед реализацией нужно синхронизировать конкретную интеграционную базу и
учесть проверенное 54d2435 / integration 0a59404: historical evidence и unreviewed
coverage evaluator fixes, [AI server handoff](https://github.com/aarakova/feedback2req/blob/54d24359cf9b334a5156ec852288d1f17e9e4e50/ai/SERVER_HANDOFF.md)
в этой линии. В данной ветке исправления и новый handoff файл не импортируются;
исходный handoff читается из git show 54d2435:ai/SERVER_HANDOFF.md.

Требуется явное утверждение всех частей B.2 либо точного подмножества B1–B4.
Решения C, публичный grouping A.2, реальная модель, push и merge этим документом
не разрешены. [Отчёт подготовки](../plans/backend-requirements-readiness.md).
