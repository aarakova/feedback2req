# Пакет решений для полного пользовательского цикла

**PROPOSED, ревизия 1, 2026-11-06. Не является разрешением реализации.**
Основание — текущее интеграционное поручение; DOMAIN/REQUIREMENTS/AI 1.0
сохраняются. Три независимых решения ниже можно принять раздельно.

## A. Публичный запуск группировки

Предлагается утвердить целиком ревизию 1
[grouping-run-api-proposed](../plans/grouping-run-api-proposed.md), перенесённую
без изменения из be328080cbeb484b3e2b77866709775627884d98.
POST `/api/v1/projects/{id}/runs` получает отдельную закрытую ветку
`operation=group_findings`, `finding_refs`, `document_refs`, `previous_group_refs`.
F1 inputs сохраняются. Member + Origin/CSRF + UUID Idempotency-Key;
1–100 findings, до 16 excerpts/16 прежних групп, общий HTTP limit 16 KiB,
canonical request/response ≤1 MiB. Весь selected finding рассматривается целиком.
Один Run/Unit finding_set, queued Attempt=null; тот же ключ/тело возвращает
прежний Run без повторного inference. Исторические refs не заменяются текущими.
Ошибки, bounds, fingerprints и поведение unknown COMMIT — в указанной ревизии.
Нет публичного grouping retry/cancel или TTL. Без настроенного провайдера
команда принимается, затем failed/provider_not_configured. Synthetic — только тест.

После согласования: discriminated HTTP DTO → существующий enqueue → worker;
frontend exact selection/context/start/same-key recovery/polling; контрактные
PG/API/CSRF/isolation/unknown COMMIT тесты. Новая миграция не нужна.
Выбор реальной модели/разрешение передачи — отдельное решение.

## B. Требования, редакции и проверки: минимальный серверный срез

Предлагается новый M04 после M03; M01/M02a/M02b/M03 неизменны.
Это проект физической реализации ДМ-1–ДМ-6, не изменение доменных правил.

### Данные и целостность

Все UUID назначает сервер. Все связи между объектами — typed composite FK
с project_id. HumanDecision/IssueResolution всегда имеют действительного User.
Immutable результаты не обновляются задним числом.

| Таблица | Основные данные и ограничения |
|---|---|
| requirements | id, project_id, current_revision_id, approved_revision_id nullable, created_at; deferred FK редакций того же requirement/project |
| requirement_revisions | id, project_id, requirement_id, ordinal, title, text, rationale, author_id nullable, authorship, attempt_id nullable, created_at; UNIQUE(project,requirement,ordinal); immutable |
| revision_findings / revision_fragments | revision_id + exact finding/fragment state; непустое пригодное evidence для нового кандидата; документация не evidence |
| revision_context | revision_id + typed exact group/document ref, locator для excerpt; рассмотренная область отдельно от evidence |
| requirement_proposals | id, project_id, requirement_id, base_revision_id, proposed_revision_id, status=open/accepted/rejected, created_by, created_at; partial UNIQUE requirement WHERE open |
| verification_results | id, project_id, revision_id, attempt_id, comparison scope/required refs/executed plan, coverage, four CheckAssessment, provenance, created_at; immutable, UNIQUE attempt |
| verification_issues / verification_questions | id, verification_id, exact target revision, canonical type/text/severity/blocking/blocking_reason/related refs; вопросы отдельно от issues; immutable обнаружения |
| issue_resolutions | id, project_id, issue_id или question_id (ровно одно), kind=corrected/not_applicable, reason, author_id, followup_verification_id nullable, created_at; append-only |
| human_decisions | id, project_id, revision_id, verification_id, value=Approved/Rejected, rationale, actor_id, created_at; append-only |

Существующие Run/Unit/Attempt расширяются отдельными typed входами generation/
verification, без изменения F1/F2 shape. Для них предлагаются отдельные таблицы
входов, аналогично GroupingInput; новые operation CHECK добавляются M04.
В БД хранится immutable снимок **состава и states**, scope, local→persistent mapping,
версии prompt/adapter и метаданные provider/model/revision/synthetic/ai_performed.
Не вводится бессрочный raw request/response архив исходных текстов.
M04 создаёт эти таблицы и расширяет только operation/input CHECK очереди;
данные старых таблиц не переписывает. Миграция должна иметь транзакционный
upgrade и тест переноса существующего полного графа F1/F2. Downgrade с потерей
новых результатов не используется в пользовательском запуске.

Предлагаемые типы: UUID для id/ref, TIMESTAMPTZ NOT NULL DEFAULT now() для created_at,
TEXT для title/text/rationale/reason, BIGINT ordinal > 0, BOOLEAN для blocking,
JSONB для закрытых canonical assessments/coverage/scope и mapping. Title 1–200,
text/rationale 1–8192 code points, human reason 1–8192. Nullable поля указаны
в таблице; author_id nullable только для AI, attempt_id nullable только для human.
Authorship=ai/human/ai_and_human. Composite FK revision/requirement/project и
UNIQUE(project,id) применяются ко всем дочерним таблицам. Связь автора/attempt
проверяется CHECK и сервисом; ссылка на чужой проект не может пройти FK.

### Закрытые DTO предлагаемой ревизии

Все refs — обязательные kind/id/state_id с UUID. Revision immutable:
state_id=id; новый текст/evidence создаёт новый UUID. Request тексты не принимают
provider/model/synthetic/authorship/actor или permanent output IDs.

```text
GenerateStart = {operation:"generate_requirements", finding_refs:[FindingRef],
                 document_refs:[], group_refs:[]}  // последние два default=[]
VerifyStart = {operation:"verify_requirement", revision_ref:RevisionRef,
               comparison_scope?:{extent:"selected",revision_refs:[],selection_reason}}
// Отсутствующий comparison_scope означает доверенный project_snapshot.
RevisionWrite = {expected_revision_id,title,text,rationale,
                 evidence:[{finding_ref,fragment_refs:[FragmentRef]}]}
ProposalWrite = {expected_approved_revision_id,title,text,rationale,evidence}
DecisionWrite = {expected_revision_id,verification_id,decision:"Approved"|"Rejected",rationale}
ResolutionWrite = {expected_revision_id,kind:"corrected"|"not_applicable",reason,
                   followup_verification_id?}
RequirementSummary = {id,current_revision_id,approved_revision_id,
                      decision:"Draft"|"Approved"|"Rejected",freshness,
                      evidence_availability:"available"|"partial"|"lost",
                      open_blocker_count,open_proposal_id}
RevisionDetail = {id,state_id,requirement_id,ordinal,title,text,rationale,
                  evidence,context,considered_refs,questions,uncertainties,
                  authorship,author_id,attempt_id,created_at}
VerificationDetail = {id,revision_ref,run_id,unit_id,attempt_id,checks:[CheckAssessment x4],
                      issues,questions,uncertainties,coverage,comparison_scope,
                      inputs:[{key,ref,roles}],provider,model,model_revision,
                      synthetic,ai_performed,created_at}
```

approved_revision_id/open_proposal_id nullable; незнакомая достаточность основания
не выводится из availability. Existing fragment refs и states проверяются по
сохранённой finding, не по клиентскому тексту. Checks/issues/questions используют
поля и enums AI 1.0; при чтении related дополняется typed persistent refs и
сохраняет origin/key. Все list ответы имеют прежние items/next_cursor и UUID ASC.
Глобальные KPI требований в этот срез не входят.

### Предлагаемый HTTP и права

Пути относительно `/api/v1/projects/{id}`, JSON закрытый, UUID, no-store,
общие Origin/CSRF/Idempotency-Key и безопасные ошибки сохраняются.

| Операция | DTO / результат | Право |
|---|---|---|
| POST /runs, generate_requirements | finding_refs[1+], document_refs[], group_refs[] →202 Run; тексты загружает сервер | Member |
| POST /runs, verify_requirement | revision_ref, comparison_scope (project_snapshot default либо selected+reason) →202 Run | Member |
| GET /requirements, /requirements/{id} | cursor page / header с exact revision refs и независимыми decision/freshness/evidence availability | Member |
| GET /requirements/{id}/revisions/{revision_id} | immutable title/text/rationale/evidence/context/questions/provenance | Member |
| POST /requirements/{id}/revisions | expected_revision_id, title,text,rationale,evidence refs →201 новая Draft; Approved требует proposal | Member |
| POST /requirements/{id}/proposals | expected_approved_revision_id, title,text,rationale,evidence refs →201 отдельное предложение | Member |
| GET /revisions/{revision_id}/verifications | cursor page точных проверок, четыре оценки, старые открытые issues/questions | Member |
| POST /revisions/{revision_id}/decisions | expected_revision_id, verification_id, decision, rationale →201 HumanDecision | Approver |
| POST /issues/{issue_id}/resolutions | expected target ref, kind, reason, followup_verification_id →201 разрешение | Approver |

Предлагаемые bounds: выбранные findings 1–100, documents/groups до 16;
title 1–200, text/rationale до существующего material text limit, тело 16 KiB;
canonical AI request/response ≤1 MiB, отказ без обрезки. Сравнение project_snapshot
может превысить предел: безопасный отказ, явный selected+reason не выдаётся за
весь проект. Ошибки 404 для чужого объекта, 409 для устаревших expected states/
блокеров/open proposal, 422 для неверного выбора/DTO; unknown COMMIT сохраняет
прежний ключ. Никакой автоматической повторной генерации.

### Жизненный цикл и приём

Generation формирует только Draft. Кандидаты, exact evidence и mapping
сохраняются атомарно после schema/application validation и повторной проверки
инициатора/актуальности/доступности. Local ID не является RevisionView.ref.
Пустой валидный ответ успешен и сохраняет coverage/reason без требования.
Верификация читает **сохранённую** редакцию и доверенные previous_checks,
prior_decision/change_context; все четыре оценки и замечания сохраняются вместе.
Завершение Run не меняет Draft/Approved/Rejected.

Новое Approved требует точной проверенной редакции, пригодного доступного
основания, отсутствия открытых блокеров и существенных вопросов; право
Approver проверяется в транзакции решения. Старые блокеры не исчезают из-за
пустой новой проверки. Severity не определяет blocking. «Принять риск» не
разрешает блокер. Not_applicable требует причины. Corrected требует связанной
повторной проверки затронутого вывода; она сама не является человеческим решением.
Правка Approved создаёт proposal; до отдельного решения прежняя approved revision
действует. Утрата основания не отменяет старое решение. Реализация удаления
источников/проекта в этот срез не включается; новые снимки не обходят её правила.

Критерии приёмки: PG constraints и migration preservation; concurrent proposal/
decision/accept; чужие refs и подмена states; access revocation и stale comparisons;
lease/deadline/unknown COMMIT; no duplicate revisions/results; partial coverage;
старые блокеры; Approver vs Member; сохранение действующей Approved при отказе
proposal; UI exact evidence/history/reload и отсутствие фиктивных KPI.

## C. Доверенный обмен и формальная проверка

Предлагается согласовать [обмен F2](qwen-z3-f2-exchange.md) ревизии 0.1
как направление следующего среза, **не как готовый HTTP/SQL контракт**.
GroupDetail не восстанавливает canonical snapshot/local mapping. Нужен exporter
с exact attempt, полным принятым canonical request/response, mapping, разрешёнными
states и provenance. До его проекта и решения production Z3 не подключается.

Прикладной сценарий: выбор двух exact findings/позиций → evidence → предложенные
object/parameter/C/A и пропуски → отдельная доверенная проверка соответствия
источникам/сопоставимости/полноты Ω → Z3. AI не подтверждает собственный результат.
Показываются D/K/S/U только после gate; timeout/unknown/resource_limit/error
отдельно. Вывод относится только к модели и подтверждённым предпосылкам.
Хранение формализации/review/result требует следующего конкретного SQL/DTO
проекта; имеющееся [предложение хранения](formal-expectations-results.md)
остаётся PROPOSED. Автономные synthetic replay доступны независимо.

## Граница разрешения

Согласование A не утверждает B/C или реальную модель. Для B нужно отдельно
утвердить предложенные таблицы/DTO/права/жизненный цикл этой ревизии; никакие
из них пока не действуют в backend. C требует конкретного exporter/
доверенного review/storage контракта. Нынешняя интеграционная ветка не создаёт
новых product таблиц/POST за пределами уже утверждённого F1/F2.
