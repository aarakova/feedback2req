# Testing

Status: TEMPLATE with user-requested testing policy. Application tests and tooling
are not yet designed or approved. Approval record/revision: TODO;
see [DECISIONS.md](DECISIONS.md).

## Testing strategy

Write tests covering approved designed functionality after requirements and
architecture approval, before implementation. Separate defects from design-change
proposals; follow [AGENTS.md](../AGENTS.md) when an approved artifact is insufficient.
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
After explicit approval of a controlled change, update documentation/design first,
then tests, then implementation. Report failures and checks not run.

## Definition of done

Applicable approvals are recorded; documentation, tests, and code agree; relevant
checks are run and results reported; independent review is completed. Failures,
unresolved errors, uncertainty, and unavailable checks/review must be disclosed,
not represented as passing or complete validation.
TODO: Define functionality-specific completion criteria and validation commands.
