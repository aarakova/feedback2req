# Testing

Status: application testing strategy remains a TEMPLATE with user-requested policy.
Contract-artifact validation is authorized by DEC-005. DEC-006 selects the stack
and permits this policy alignment with AGENTS.md; it does not authorize application
implementation. Proposed slice checks are in [FIRST_TEXT_SLICE.md](FIRST_TEXT_SLICE.md).
Application test tooling remains unselected. Application testing revision: TODO;
see [DECISIONS.md](DECISIONS.md).

## Testing strategy

Cover approved functionality and applicable acceptance criteria with meaningful
checks. Choose the order of test writing, implementation, and debugging within
the authorized scope; tests need not invariably precede implementation.
Separate defects from design-change proposals; follow
[AGENTS.md](../AGENTS.md) when an approved artifact is insufficient.
TODO: Define the project-specific strategy from approved requirements.

## Test levels

TODO: Define applicable unit, integration, API, workflow, and AI evaluation coverage
and boundaries. No test framework or infrastructure is selected.

## Mapping tests to requirements

TODO: Map approved requirement IDs and acceptance criteria to tests and results;
identify coverage gaps explicitly. Use [AI_VALIDATION.md](AI_VALIDATION.md) for AI
evaluation criteria.

## Execution commands once known

TODO: Record commands, prerequisites, and expected outcomes after tooling approval.
No application test commands exist yet.

## Test-change policy

Never weaken or remove a valid failing test without an approved requirement/design
change. Never change production behavior merely to make a test pass. Report
suspected incorrect tests with evidence rather than silently rewriting expectations.
Obtain approval before changing controlled requirements or design. Within an
approved change, keep documentation, tests, and implementation consistent without
a mandatory docs → tests → implementation sequence. Report failures and checks not run.

## Definition of done

Applicable approvals are recorded; documentation, tests, and code agree; relevant
checks are run and results reported. Use independent review for substantial changes
when available and disclose review limitations. Failures,
unresolved errors, uncertainty, and unavailable checks/review must be disclosed,
not represented as passing or complete validation.
TODO: Define functionality-specific completion criteria and validation commands.

## Разрешённая проверка контрактных артефактов

DEC-005 разрешает JSON Schema, демонстрационные запросы/ответы и автономные
проверки их корректности. Основная спецификация, команды и границы проверок —
[AI_CONTRACTS.md](AI_CONTRACTS.md). Python/jsonschema — инструменты этой
проверки, а не выбранный стек приложения. Тесты backend/frontend, провайдеров
и оркестрации этим этапом не создаются. Действующий набор проверяет диалект,
ссылки, позитивные/негативные примеры, закрытость объектов и выбранные свойства
локальных пар; не заявляет проверку БД, прав, живых состояний или качества AI.
