# Execution-plan workflow

Use a written, living execution plan for complex or substantive multi-file tasks,
major features, multi-component work, architecture, large refactors, AI pipeline
changes, data-model changes, and API contract changes. Skip plans for trivial edits.
Store future task plans in `docs/plans/<task>.md`, creating that directory only
when needed. A plan is a work record, not approval of its proposals.

Before affected work starts, identify the current development stage and approved
sources. Inspect existing documents and record unknowns rather than filling them
with assumptions. Follow the gates and change-control sequence in `AGENTS.md`.
Record explicit user approvals with scope and artifact revision in
`docs/DECISIONS.md`; silence, delegation, and passing tests are not approval.
Update progress and validation results as work proceeds. On a blocked change,
stop affected work and record the proposal and impact before seeking approval.
Close a plan only when its authorized scope is complete; disclose unresolved work.

## Reusable plan template

- Goal and current authorized stage: TODO.
- Approved source requirements: TODO (document sections, IDs/revisions, approval
  record; use "none yet" when applicable).
- Known facts: TODO.
- Open questions: TODO.
- Assumptions: TODO.
- User decisions required: TODO.
- Clarification status: BLOCKED / READY.
- Affected components: TODO (do not invent components not yet designed).
- Files expected to change: TODO.
- Tests/validation required: TODO (trace to approved criteria; distinguish
  scaffold checks from future application tests).
- Dependencies and risks: TODO.
- Architectural or documentation changes required: TODO (what and why, or none).
- User approvals required: TODO (scope, status, evidence, and work blocked).
- Implementation progress: TODO (completed, next, blocked; documentation-only
  tasks track their own deliverables here).
- Validation results: TODO (commands/checks, outcomes, failures, not-run checks,
  independent review, and limitations).

## Harness setup execution record

- Goal/stage: create only the repository harness and structured document templates.
- Source/authorization: user's repository-setup request in this conversation;
  no detailed product requirements or architecture have been approved.
- Affected components: repository instructions, development-agent configuration,
  documentation templates only.
- Expected files: `AGENTS.md`, `PLANS.md`, six `.codex/agents/*.toml` files,
  and the nine requested `docs/*.md` files.
- Validation: inspect exact inventory, TOML syntax and documented field usage,
  local document references, stage gates, consistent change control, and absence
  of invented product design. No application tests are authorized at this stage.
- Dependencies/risks: Codex client support and repository permissions; templates
  must not be mistaken for approved design.
- Design/documentation changes: create requested templates and harness only.
- Approvals: creation authorized by the request; later stages remain unrequested.
- Progress: all 17 requested files created; harness-only scope complete.
- Validation results: exact 17-file inventory verified; all six TOML files parsed
  with Python 3.12 `tomllib` and checked for documented fields, required metadata,
  sandbox values, and architect reasoning effort; all 15 local Markdown links and
  anchors resolved; all nine document templates contain status and TODO markers.
  Instruction review found no conflicting approval gates or invented product
  design/technology decisions. No application tests were created or run.
  Codex runtime role discovery and sandbox enforcement were not exercised;
  no independent agent review was performed. No requested configuration field was
  omitted because of schema uncertainty; model selection is intentionally inherited.
  Initial Git status failed on ownership; a command-scoped safe-directory setting
  allowed inspection without changing global configuration. The Python launcher
  found no interpreter; direct invocation of the installed Python 3.12 succeeded.
  Writing the protected `.codex/agents/` directory required elevated permission
  and completed successfully. Official schema reference:
  https://learn.chatgpt.com/docs/agent-configuration/subagents (checked 2026-10-08).
  Developer Docs MCP unavailable in this session; official web documentation used.

## Clarification status

Before execution begins, every substantive plan must record:

- Known facts
- Open questions
- Assumptions
- User decisions required
- Clarification status: BLOCKED / READY

Execution must not begin while clarification status is BLOCKED.
BLOCKED means material questions remain. READY means material uncertainty has been
resolved or the user has explicitly authorized proceeding with the listed
assumptions.
