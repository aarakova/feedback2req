# Пакет B.2: поэтапная передача серверных контрактов frontend

**PROPOSED, редакция B.2 от 2026-11-25. Ни один новый endpoint ниже пока не реализован.**
[Модель, транзакции и критерии](requirements-server-slice.md) — часть той же
редакции B.2. Пакет A.2 не является обязательным условием: B1 начинает с готовых
F1 findings, сохранённые группы — необязательный контекст. Реальная модель и C
не включаются. После утверждения каждый этап передаётся с собственным PG/API
отчётом, а до этого frontend не отправляет эти команды.

## Общие типы и транспорт

Пути ниже относительно `/api/v1/projects/{project_id}`. JSON UTF-8, cookie,
Origin/X-CSRF-Token для POST, UUID Idempotency-Key. Неизвестные поля запрещены.
UUID — строки D-form; kind — точный literal. Списки `{items,next_cursor}`, UUID ASC,
не единый snapshot, прежний server page_size. Все GET доступны Member своего
проекта. Producer model/provider/synthetic/actor не передаются клиентом.

```text
FindingRef={kind:"finding",id,state_id}
FragmentRef={kind:"fragment",id,state_id}
DocumentRef={kind:"product_document",id,state_id,locator?:{start,end}}
GroupRef={kind:"finding_group",id,state_id}
RevisionRef={kind:"requirement_revision",id,state_id} // state_id=id
EvidenceWrite={finding_ref:FindingRef,fragment_refs:[FragmentRef x1+]}
EvidenceRead={finding_ref:FindingRef,links:[
  {kind:"available",fragment:FragmentDetail}|{kind:"deleted_source",source_id}]}
RevisionContext={documents:[{ref:{kind:"product_document",id,state_id},locator:{start,end}}],
                 groups:[GroupRef]}
```

FragmentDetail — точный действующий F1 detail с source_ref/text_ref, quote,
locator/reliability из [TEXT_PROCESSING_API](../TEXT_PROCESSING_API.md).
В EvidenceRead у одной finding могут быть и доступные, и утраченные source links.

Тексты title 1–200, text/rationale/human reason 1–8192 code points, не whitespace-only;
без обрезки. Суммарный HTTP body ≤16 KiB по текущей конфигурации, поэтому не все
поля одновременно помещаются на индивидуальном максимуме. Материал не режется
скрытно. Выбор ≤100 findings/≤16 documents/groups, comparisons ≤100; canonical
AI request/response ≤1 MiB. Все состояния exact; range — Unicode [start,end).

## B1 — сохраняемые кандидаты

```text
GenerateStart={operation:"generate_requirements",finding_refs:[FindingRef x1..100],
               document_refs?:[DocumentRef x0..16],group_refs?:[GroupRef x0..16]}
```

Optional массивы default=[], null запрещён. POST `/runs` →202 прежний Run DTO
с одной generation_set Unit; до claim attempt=null. Unit.input содержит findings,
documents,groups exact refs; actual ranges живут в typed snapshot. После приёма:

```text
Attempt.generation_result=null|{revision_refs:[RevisionRef],requirement_ids:[UUID],
                              input_findings:[{key,ref:FindingRef}]}
```

Остальные поля Attempt/F1/F2 не меняются. Coverage/annotations сохраняются при
0 candidates; все новые revision имеют собственное решение Draft. Генерация
не запускает verify/decision автоматически и не заменяет существующий Requirement.
GET `/runs`/`/runs/{id}` уже определяют polling/history; public retry новых kinds
в этом пакете не добавляется (409 retry_not_allowed).

## B2 — чтение и неизменяемые редакции

| Endpoint | Результат |
|---|---|
| GET /requirements | Page RequirementSummary |
| GET /requirements/{id} | RequirementSummary + current_revision_ref, approved_revision_ref?, open_proposal_ref? |
| GET /requirements/{id}/revisions | Page RevisionDetail |
| GET /requirements/{id}/revisions/{revision_id} | Exact RevisionDetail, не подмена текущей |
| POST /requirements/{id}/revisions | RevisionWrite →201 RevisionDetail; Member, только неутверждённое current |

```text
RevisionWrite={expected_current_revision_id,title,text,rationale,
               evidence:[EvidenceWrite x1+],document_refs?:[DocumentRef x0..16],
               group_refs?:[GroupRef x0..16]}
RequirementSummary={id,current_revision_id,approved_revision_id:null|UUID,
  decision:"Draft"|"Approved"|"Rejected",freshness:"current"|"requires_update",
  evidence_availability:"available"|"partial"|"lost",open_blocker_count,
  open_proposal_id:null|UUID,review_hash:Hex64}
RevisionDetail={id,state_id,requirement_id,ordinal,previous_revision_id:null|UUID,
  derived_from_revision_id:null|UUID,title,text,rationale,evidence:[EvidenceRead],
  considered_refs:[FindingRef],context:RevisionContext,authorship,author_id:null|UUID,
  generation_attempt_id:null|UUID,created_at,decision:"Draft"|"Approved"|"Rejected",
  notes:{questions:[ReviewQuestion],uncertainties:[UncertaintyView]},verification_refs:[StateRef]}
```

Значения decision/evidence/freshness/notes — read projections, не изменяемые
поля содержимого Revision. До B3 verification_refs пуст; до B4 decisions только
Draft, proposals отсутствуют. Evidence читает только доступные текущие записи
точного Fragment; deleted_source — ID источника и факт утраты, без цитаты/locator.
Время human decision и author не наследуются новым revision. Нет PATCH body.

## B3 — проверка, scope и открытые обнаружения

```text
VerifyStart={operation:"verify_requirement",revision_ref:RevisionRef,
  comparison_scope?:{extent:"selected",revision_refs:[RevisionRef x0..100],selection_reason},
  followup?:{previous_result_id,issue_ids?:[UUID],question_ids?:[UUID]}}
```

Без comparison_scope — серверный project_snapshot. Selected всегда с причиной,
не выдаётся за весь проект. Followup требует хотя бы один issue/question;
все принадлежат previous_result и Requirement цели; поле HTTP не переносится
в AI JSON буквально (question-only context разрешает trusted adapter).
Собственная точная цель не может быть comparison; одинаковые revision refs
не дублируются, сервер объединяет требуемые роли. History/required_context
определяет сервер, не непроверенный клиентский previous_checks.

POST `/runs` →202 Run с revision_target Unit и точной revision/scope snapshot.
После приёма Attempt.verification_result={verification_ref:{kind:"verification_result",id,state_id}}
либо null до приёма/при техническом отказе. Дополнительно:

| Endpoint | Результат |
|---|---|
| GET /requirements/{id}/verifications | Page VerificationDetail |
| GET /requirements/{id}/verifications/{verification_id} | Exact VerificationDetail |
| GET /requirements/{id}/review-notes | `{items:[ReviewNote],next_cursor,review_hash}`; отдельная пагинация обнаружений всех проверок |

```text
VerificationDetail={id,state_id,requirement_id,target_revision_ref,attempt_id,
  comparison_scope,required_refs:[StateRef],history_refs:[StateRef],
  input_bindings:[{key,ref:StateRef,roles:[current|pending_change|new_candidate|history]}],
  context_bindings:[{key,parent_ref:StateRef,source:{attempt_id,local_id}|{annotation_id}}],
  coverage,checks:[CheckAssessment x4],
  issues:[ReviewIssue],questions:[ReviewQuestion],uncertainties,
  freshness:"current"|"requires_update",manifest_hash,provider,model,synthetic,
  material_hash,ai_performed,adapter_version,prompt_version,schema_version,created_at}
ReviewIssue={id,kind:"verification_issue",verification_id,target_revision_ref,
  category,text,reason,severity,blocking,blocking_reason,related,question_ids,
  resolution:null|ResolutionView}
ReviewQuestion={id,kind:"requirement_question",source_attempt_id,
  verification_id:null|UUID,original_revision_refs,text,reason,blocking,related,
  resolution:null|ResolutionView}
UncertaintyView={id,kind:"requirement_uncertainty",reason,related,
  source_attempt_id,verification_id:null|UUID}
```

Публичные kind=requirement_question/requirement_uncertainty — **HTTP**, не новые
AI StateRef kinds. Для related typed note ref имеет id/state_id=id; обычные
entity refs сохраняют shape origin/key/kind/id/state_id как в F2. Context branch
имеет origin=input,key,context_key,parent_ref, без выдуманного finding.
ReviewNote — закрытая union issue/question; uncertainty читается отдельно в
Revision/Verification/Run и не получает blocking по догадке. Related input
разрешён через сохранённый key binding; output — собственные созданные объекты.
StateRef related сохраняет kind/id/state_id; nested QuestionView context key
имеет context_key/parent_ref и не становится evidence.

Новый пустой VerificationDetail.issues не заменяет review-notes и не закрывает
старое обнаружение. Показывать source revision/result и точный resolution.
Severity high не равна blocking; question блокирует независимо от issue severity.
Review hash серверный, зависит от IDs открытой истории/решений/manifest и доступности;
клиент не вычисляет его из числа замечаний.
original_revision_refs фильтруются по Requirement текущего endpoint. Cache key
статуса note включает project/requirement/kind/id, потому что один generation
question может иметь разные resolutions у разных Requirement. Resolution —
внешняя read projection; immutable содержание исходного результата не меняется.
Resolution меняет review hash, но не делает material freshness устаревшей без
изменения target/evidence/comparisons. Freshness=current сама по себе не даёт
права на Approved и не подтверждает достаточность основания.

required_refs — exact comparisons из comparison_scope.required_keys; history_refs —
точные prior decision/base/previous-check refs. roles у comparison binding —
литералы AI 1.0, у остальных input bindings []. В input_bindings выдаются только
linkable canonical keys; внутренние @history keys не выдаются как AI inputs.

## B4 — Approver и отдельные предложения Approved

```text
ProposalWrite={expected_approved_revision_id,title,text,rationale,
  evidence:[EvidenceWrite x1+],document_refs?:[DocumentRef x0..16],
  group_refs?:[GroupRef x0..16],change_reason}
ApprovedWrite={decision:"Approved",expected_current_revision_id,
  expected_review_hash:Hex64,proposal_id:null|UUID,verification_id:UUID,
  rationale,evidence_confirmation:{sufficient:true,reason}}
RejectedWrite={decision:"Rejected",expected_current_revision_id,
  expected_review_hash:Hex64,proposal_id:null|UUID,verification_id?:UUID|null,rationale}
ResolutionWrite={expected_target_revision_id,expected_review_hash:Hex64,
  note:{kind:"verification_issue"|"requirement_question",id},
  kind:"corrected"|"not_applicable",reason,followup_verification_id?:UUID}
```

| Endpoint | Право / ответ |
|---|---|
| POST /requirements/{id}/proposals | Member; ProposalWrite →201 ProposalDetail |
| GET /requirements/{id}/proposals | Member; page ProposalDetail |
| GET /requirements/{id}/proposals/{proposal_id} | Member; exact ProposalDetail |
| POST /revisions/{revision_id}/decisions | Approver; ApprovedWrite/RejectedWrite →201 HumanDecisionView |
| GET /requirements/{id}/decisions | Member; page HumanDecisionView, exact revision refs |
| GET /requirements/{id}/decisions/{decision_id} | Member; exact HumanDecisionView |
| POST /requirements/{id}/resolutions | Approver; ResolutionWrite →201 ResolutionView |
| GET /requirements/{id}/resolutions | Member; page ResolutionView |
| GET /requirements/{id}/resolutions/{resolution_id} | Member; exact ResolutionView |

ProposalDetail={id,requirement_id,base_revision_ref,proposed_revision_ref,
created_by,change_reason,status:"open"|"accepted"|"rejected",created_at,
closing_decision_id:null|UUID}. Proposed revision имеет Draft до собственного
решения, а Requirement по-прежнему показывает действующее Approved.
При reject base неизменна; при approve атомарно закрыть proposal, переключить
current/approved refs. Открытое предложение нельзя молча заменить вторым.
Corrected требует followup; not_applicable — человеческую причину. Ни то ни
другое не закрывает новое обнаружение с другим UUID. Resolution scope ограничен
Requirement: общий generation question в соседнем Requirement остаётся открытым.

HumanDecisionView={id,revision_ref,proposal_id:null|UUID,verification_ref:null|StateRef,
decision,rationale,actor_id,evidence_confirmation:null|object,created_at}.
ResolutionView={id,requirement_id,note,kind,reason,actor_id,followup_verification_ref:null|StateRef,created_at}.
Оба immutable. Replay возвращает ту же result identity и актуальное read
представление, не обещает byte-for-byte старый ответ. Backend заново проверяет
текущее членство/право команды, но не выполняет решение повторно.

## Ошибки и неизвестный исход

| HTTP / code | Смысл / действие frontend |
|---|---|
| 401 unauthenticated; 403 origin_rejected/csrf_rejected | Прежнее восстановление сессии/security; не менять pending key |
| 403 forbidden | Нет Approver; не рисовать успешное решение; прежний unknown commit всё ещё мог сохраниться |
| 404 not_found | Проект/ref/state/объект неизвестен либо недоступен; одинаковый ответ |
| 409 input_changed | Source/target/comparison context изменён; свежий явный выбор, не тихая подмена states |
| 409 revision_conflict/review_conflict | Expected current/review hash устарел; обновить exact данные |
| 409 proposal_required/proposal_already_open | Approved не редактируется напрямую / уже есть open proposal |
| 409 approval_blocked | Есть открытые blockers/material questions; показать серверные IDs причин |
| 409 verification_required/verification_stale/evidence_unavailable | Нет подходящей проверки/контекст устарел/нет usable available evidence |
| 409 resolution_invalid/decision_not_allowed | Followup/note/target не подходят для этой команды |
| 409 idempotency_conflict | Тот же key, другой path/body/operation; не создавать key автоматически |
| 413 body_too_large; 422 invalid_request/invalid_input | Envelope/DTO или selection/context bounds; данные не обрезать |
| 500 internal_error; network/proxy/непригодный response | Исход неизвестен: GET known IDs или same actor/project/path/body/key replay |

Error envelope прежний: `{error:{code,message,details,request_id}}`, без raw SQL/
source/provider exception. Для approval_blocked details={issue_ids,question_ids},
для conflict details={current_revision_id,review_hash}; все IDs только доступного
проекта. При прочих ошибках details={}. Технический worker reason_code остаётся
provider_not_configured/provider_error/invalid_response/execution_error/
lease_expired/deadline_exceeded; отмены input_changed/access_revoked.

## Сценарии приёмки и передача по этапам

| ID | Этап | Проверяемый исход |
|---|---|---|
| B01 | B1 | Новый saved candidate: точные permanent IDs, Draft, M:N evidence |
| B02 | B1 | Один пригодный отзыв достаточен для кандидата, document-only отклонён |
| B03 | B1 | 0 candidates не ошибка; Run хранит coverage и questions |
| B04 | B1 | Partial overall coverage виден, без выдуманной полноты проекта |
| B05 | B1 | Unknown enqueue/claim/accept COMMIT в обоих исходах, модель ≤1 раза |
| B06 | B1 | Invalid/local-id/foreign-state ответ rollback всего aggregate |
| B07 | B1 | Revoke/stale/lease/restart не публикуют поздние результаты |
| B08 | B2 | История/точный GET не подменяют выбранную revision текущей |
| B09 | B2 | Human write создаёт новый UUID, без прежнего решения/verification |
| B10 | B2 | Два edit с одним expected current: один успех, один conflict |
| B11 | B2 | Same-key write после timeout даёт прежнюю identity, не дубль |
| B12 | B2+B4 | После включения решений: direct edit Approved →proposal_required |
| B13 | B3 | Ровно четыре assessments; kind/related/project FK проверяются в PG |
| B14 | B3 | Default snapshot/selected/history roles не смешаны; stale membership отменяет accept |
| B15 | B3 | Блокер V1 + пустая V2: review-notes по-прежнему показывает блокер |
| B16 | B3 | Blocking question остаётся независимо от severity issue |
| B17 | B3 | Not-processed/insufficient/inconclusive не выдаются за чистый общий результат |
| B18 | B3 | Target saved revision и обязательная prior/change/followup история из DB |
| B19 | B4 | Member не делает Approved; Approver может решать по собственному предложению |
| B20 | B4 | Любой старый/новый open blocker запрещает новый Approved |
| B21 | B4 | Новая proposal revision Draft, base Approved остаётся действующей |
| B22 | B4 | Два concurrent proposal →ровно одна open запись |
| B23 | B4 | Reject proposal сохраняет base/current/approved и историю |
| B24 | B4 | Approve exact checked target атомарно переключает указатели |
| B25 | B4 | Пустая проверка не создаёт resolution; corrected требует отдельного события/followup |
| B26 | B4 | Not_applicable требует Approver/reason; «принять риск» не закрывает blocker |
| B27 | B4 | Новое issue UUID не закрыто старым resolution; общий question не закрыт в соседнем Requirement |
| B28 | B4 | Утрата evidence не отменяет прежнее Approved, но запрещает новое без пригодного основания |
| B29 | B4 | Human unknown COMMIT + replay не создаёт второй decision/переход |
| B30 | Все | Project/actor change: старый ответ не применяется, pending key не повторяется другим actor |
| B31 | Все | Upgrade с заполненной F1/F2 БД и regressions без потери старых данных |
| B32 | Все | Synthetic явно отмечен, ни AI, ни completed не назначают Approved |

**В этой подготовке B01–B32 NOT RUN**: runtime/DDL ещё не согласованы. После
принятия B1 сначала передать его фактические DTO/Run examples/PG отчёт; затем
B2 read/revisions, B3 checks/notes и B4 Approver/proposal. UI не должен считать
все четыре этапа готовыми по результатам первого. Синтетические lifecycle traces —
[примеры](requirements-lifecycle-examples.json), не backend-реализация.
