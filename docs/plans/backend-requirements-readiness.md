# Подготовка серверного среза требований — 2026-11-25

**Результат: PROPOSED пакет B.2, не реализация нового backend.**
Поручение пользователя разрешает подготовку модели/контрактов и требует отдельного
утверждения перед последовательными B1–B4. Предметные правила не меняются.

## База и параллельная работа

Собственная ветка feat/backend-requirements-contract, отдельный worktree,
база 41e3ab26d240dc8b150599c264075df9417112fb: согласованная integration/full-workflow-ui
600065626be5e671223c8a8afd696a14bb4c20e5 + собственная подготовка A.2.
Preview/workspace не использован как полноценная база. A.2 остаётся PROPOSED.
Пакет B не зависит от утверждения A для synthetic generation по готовым findings.

Проверены main 410b936, integration/full-workflow-ui 6000656, готовые AI generation
866b3c6 и verification ab34793. В параллельной integration/readiness-20261121
обнаружены локальные незакоммиченные изменения; они не копировались и не правились.
Её snapshot 1bebe36 включает evaluator fix 0a59404 (исходный опубликованный
54d24359cf9b334a5156ec852288d1f17e9e4e50) и документы AI server handoff.
Они просмотрены через точные git snapshots как зависимость будущей реализации,
не выданы за уже включённые в текущую ветку.

## Подготовленные артефакты

- [Физическая модель и транзакции B.2](../proposals/requirements-server-slice.md):
  staged m04a–m04d, composite FK/immutable constraints, exact evidence и
  историческая утрата, typed key bindings, idempotency human commands,
  накопленные blockers, review/material freshness, атомарные Approver/proposal transitions.
- [Frontend handoff](../proposals/requirements-frontend-handoff.md): точные paths,
  DTO/roles/errors/recovery и 32 критерия B01–B32 с границей каждого этапа.
- [Синтетические traces](../proposals/requirements-lifecycle-examples.json):
  0 candidates с сохранённым вопросом, пустая новая проверка со старым blocker,
  новая Draft revision, reject/approve
  отдельного proposal, новый issue без старого resolution, shared question scope
  и сохранение старого Approved при потере evidence.
- [Общий пакет](../proposals/workflow-contracts.md) ссылается на B.2. A.2 и C
  сохранены отдельно без распространения разрешения между пакетами.

Существующие generate_requirements/verify_requirement вызываются раздельно,
verify получает реально сохранённую RevisionView. Provider один вызов, trusted
callback, safe errors; публикация/lease/recovery/решения — ответственность backend.
Новые four-check enums не выдуманы: support/contradictions/ambiguity/duplicates;
roles ровно current/pending_change/new_candidate/history из неизменённой AI 1.0.

## Принятые технические уточнения предложения

- Отдельные human command receipts нужны для unknown COMMIT без второй записи
  решения/редакции; это не вторая очередь AI.
- Parent/current/approved/proposed pointers связывают exact revision одного
  Requirement; новая revision не получает прежние decision/verification IDs.
- Open note union строится по stable IDs истории Requirement, не только из
  последнего результата. Resolution имеет Requirement scope, отдельного автора,
  reason/followup и не закрывает новый note с другим UUID.
- Материальная свежесть и review history разделены: human resolution не требует
  повторного AI только из-за собственного события, но новые blockers учитываются.
- Source deletion producer не входит в B. Исторический loss consumer хранит
  только ID/факт и не восстанавливает quote; B4 loss case использует явный fixture,
  не объявляет полноценное удаление F1/F2 источников реализованным.
- Порог существенности изменения не изобретён; нет автоматического Approved,
  авто-решения старых замечаний или семантического доказательства через FK/JSON.

## Проверки и ограничения

PASS, 2026-11-25, собственные синтетические документы/JSON и read-only команды:

- JSON синтаксис и UUID aliases; восемь lifecycle traces. Проверены конкретные
  ожидаемые сохранённые refs/notes/decisions, а не выполнена симуляция backend.
- 17 локальных Markdown targets, 32 строки приёмки B01–B32.
- Assessment kinds и comparison roles сверены с actual common.schema.json 1.0;
  описательные current_not_rejected/unfinished_proposal не выданы за literals.
  Проверка сначала выявила отсутствие полного списка kinds в основном документе;
  список добавлен, повторный check прошёл, проверки не ослаблялись.
- Canonical A.2 неизменен; C section сохранена относительно 41e3ab2. Editorial
  пакет A/B/C обновлён только для B.2 и ссылки на его отдельное согласование.
- git diff --check; backend/frontend/AI schemas, product rules, migrations и
  tests не менялись. Реальные source snapshots и histories прочитаны без правки.

Это проверки подготовленных артефактов, не PASS SQL/API или human lifecycle.
NOT RUN: новые SQL migrations/PG/API B01–B32 (реализация ещё не утверждена),
frontend/browser, полноценный F1/F2 regression, независимое ревью и реальная AI.
Автономный повтор generation/verification tests в этой подготовке NOT RUN:
Docker CLI найден, но Linux Engine pipe недоступен. Shared Docker/чужие
контейнеры не перезапускались, зависимости и host venv не менялись.
Наличие старых PASS в исходных ветках не считается новым проверочным результатом.

## Следующий шаг

Нужно отдельное утверждение конкретной B.2 целиком либо явно B1/B2/B3/B4.
После него пересверить интеграционный head/миграции и зависимость 54d2435,
затем реализовывать последовательно с отдельными PG/API отчётами и передачей
фронтенду. Пока runtime/backend/frontend/AI Schema 1.0 не меняются.
Push, merge и внешние AI-вызовы не выполняются.
