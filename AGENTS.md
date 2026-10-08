# Repository instructions

## Purpose and scope

Prepare a web system for software development teams to analyze audio, video,
and text feedback alongside product documentation and generate evidence-linked
product improvement requirements and analytical dashboards.
Current authorization is harness and document templates only. Do not start
detailed project documentation, architecture, tests, or application implementation
until the user explicitly requests the corresponding work.

## Development gates

Follow this order: (1) detailed project/domain documentation, (2) explicit user
approval, (3) architecture design, (4) explicit user approval, (5) tests covering
approved designed functionality, (6) backend/frontend implementation, and
(7) validation against those tests and independent review.
A later stage must never silently redefine an earlier approved stage.

## Source of truth and change control

- Approved documents in `docs/` govern implementation; drafts, TODOs, research,
  plans, and agent output do not constitute approval. Record approval evidence,
  scope, and the approved artifact revision in `docs/DECISIONS.md`.
- Never silently change approved requirements, domain documentation,
  architecture, data models, API contracts, technologies, product-agent
  responsibilities, or any other controlled design artifact.
- If a change is needed: stop affected work; explain the problem and why the
  approved design is insufficient; propose a concrete change; identify affected
  documents, tests, and code; wait for explicit user approval; then update the
  design/documentation, update tests, and only then resume implementation.
- Ask the user before deciding anything that materially affects those controlled
  areas. Explain significant project-structure decisions before implementation.
  Flag conflicting sources rather than choosing an interpretation silently.
- Keep documentation, tests, and code synchronized. Never implement a changed
  architecture first and document it afterward. Do not make destructive or
  irreversible changes without explicit approval.

## Documents and plans

Use `docs/REQUIREMENTS.md` and `docs/DOMAIN.md` for scope and domain;
`docs/ARCHITECTURE.md`, `docs/AGENT_ARCHITECTURE.md`, `docs/DATA_MODEL.md`, and
`docs/API.md` for design; `docs/TESTING.md` and `docs/AI_VALIDATION.md` for
validation; and `docs/DECISIONS.md` for decisions and approvals.
Use the execution-plan workflow in `PLANS.md` for complex or multi-file tasks;
trivial edits do not need a plan.

## Agents and delegation

Codex development agents in `.codex/agents/` are architect, requirements analyst,
test engineer, backend developer, frontend developer, and reviewer. They develop
and review this repository. They are distinct from the future application's
Feedback Analysis Agent, Requirements Generation Agent, and Requirements
Verification Agent; see `docs/AGENT_ARCHITECTURE.md`.

Delegate only bounded tasks within the authorized stage. Supply approved source
references, scope, allowed files, and expected validation. Avoid overlapping
writes. The coordinating agent checks integration and synchronization; delegation
does not grant approval or bypass gates. Use a separate reviewer for independent
review and report when independent review was unavailable. Architect and reviewer
propose/report changes without editing files. No agent can approve design changes.

## Testing and research

- Derive tests from approved requirements and architecture before implementation.
  Never weaken or remove a valid failing test without an approved requirement or
  design change, or change production behavior merely to make a test pass.
- Run relevant checks and explicitly report failures, unresolved errors,
  uncertainty, and checks not run. Evaluate AI behavior using explicit criteria;
  exact wording is an assertion only when required. Preserve the six invariants
  in `docs/AI_VALIDATION.md`.
- External research may inform options and current documentation, never authorize
  a design or technology change. Cite sources and distinguish facts from proposals.
  For OpenAI APIs, Codex, Agents SDK, and platform features, use the official
  OpenAI Developer Docs MCP when available; otherwise consult official OpenAI
  documentation and disclose that fallback. If research suggests changing an
  approved decision, propose the change and wait for user approval.
