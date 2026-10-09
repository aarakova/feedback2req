# Журнал решений и утверждений

Статус: запись об утверждении предметной области и требований добавлена.
Архитектурные и технические решения приложения не утверждены.

## Recording decisions and approvals

Record proposals separately from approved decisions. Only explicit user approval
can approve a controlled artifact or change. Include the exact approved scope,
artifact revision or snapshot, and a reference to the user's approval. Preserve
decision history when a subsequent approved decision supersedes an earlier one.
Use this log also for requirements/domain and other controlled-artifact approvals.

## Decision template

- ID/title: TODO.
- Date: TODO.
- Context/problem: TODO.
- Alternatives: TODO.
- Proposed or approved decision: TODO (identify which).
- Consequences: TODO.
- Affected documentation, tests, and implementation: TODO.
- Approval status: TODO (not approved until explicit user approval is recorded).
- Approval evidence, date, and scope: TODO.
- Approved artifact references and revisions/snapshots: TODO.
- Supersedes/superseded by: TODO, if applicable.

## Entries

### DEC-001 — Утверждение предметной области и требований

- Дата: 2026-10-09.
- Контекст: после clarification interview и фазы PROPOSE пользователь проверил
  полные версии двух документов, запросил корректировки и затем явно утвердил
  последние предложенные версии как текущую baseline для дальнейшего проектирования.
- Альтернативы: отдельные продуктовые и технические варианты не утверждались;
  открытые вопросы сохранены для последующих решений.
- Решение: утвердить предметную область в [DOMAIN.md](DOMAIN.md) и требования
  в [REQUIREMENTS.md](REQUIREMENTS.md) в объёме последнего согласованного
  предложения. Оба документа являются текущей baseline для следующего этапа.
- Scope утверждения: определения, границы, бизнес-правила, инварианты и открытые
  вопросы `DOMAIN.md`; FR-001–FR-031, NFR-001–NFR-004, AC-01–AC-10, ограничения,
  правила трассируемости и AI, а также открытые вопросы `REQUIREMENTS.md`.
  Предварительные положения утверждены именно как предварительные; открытые
  вопросы не являются утверждёнными решениями.
- Последствия: зависимые формулировки `AI_VALIDATION.md` и
  `AGENT_ARCHITECTURE.md` синхронизируются с этой baseline. Любое последующее
  изменение утверждённых требований или семантики предметной области требует
  отдельного явного согласия пользователя по change-control workflow.
- Затронутые документы, тесты и реализация: `DOMAIN.md`, `REQUIREMENTS.md`,
  `AI_VALIDATION.md`, `AGENT_ARCHITECTURE.md`, этот журнал; тесты и код приложения
  не существуют и этим решением не утверждаются.
- Статус утверждения: APPROVED / утверждено.
- Основание утверждения: сообщение пользователя от 2026-10-09, начинающееся
  словами «Утверждаю предложенные версии предметной области и требований,
  представленные в последнем сообщении, как текущую утверждённую baseline».
- Утверждённые ревизии: `DOMAIN.md` — SHA-256
  `81DEBC027B2B656003030654A4C832C2D68F3355F989E99D02553F219A19595F`;
  `REQUIREMENTS.md` — SHA-256
  `A4E1414F0165DD5C0ABC54E5FE92C131281072B707168D52278F1239B8F5796B`.
  Хэши относятся к зафиксированным текстам с добавленными статусом и датой.
- Открытыми остаются: допустимость внешней AI-обработки конфиденциальных данных;
  состав сохраняемых сведений о происхождении после удаления источника и судьба
  `Approved` требования без единственного источника; условия утверждения при
  неразрешённом критичном замечании; правило уникальности участника; точная
  модель состояний, прав и глубина требования; форматы/лимиты, дополнительные
  языки, нагрузки/SLA, технологии хранения и шифрования, AI provider, технический
  способ обнаружения повторов, AI-метрики и пороги. Полные формулировки см. в
  разделах открытых вопросов двух утверждённых документов.
- Не утверждены: архитектура, технологии, AI provider, модель данных, API,
  точная модель состояний и ответы на открытые вопросы.
- Предыдущее/последующее решение: отсутствует.
