# Repository instructions

## Purpose and scope

Prepare a web system for software development teams to analyze audio, video,
and text feedback alongside product documentation and generate evidence-linked
product improvement requirements and analytical dashboards.
Current authorization is harness and document templates only. Do not start
detailed project documentation, architecture, tests, or application implementation
until the user explicitly requests the corresponding work.

## Communication language

- Communicate with the user in Russian unless the user explicitly asks for another language.
- All user-visible explanations, plans, progress updates, questions, review findings,
  implementation summaries, and justifications must be written in Russian.
- Do not expose hidden chain-of-thought. When reasoning needs to be explained,
  provide a concise Russian rationale, the relevant evidence, alternatives, and conclusion.
- Source-code identifiers, API names, library names, commands, and other technical
  tokens may remain in their conventional language. Project documentation may use
  the language explicitly approved for that artifact.

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

## Architecture change propagation

An architecture change requires explicit user approval under the existing
clarification, approval, and change-control workflow. Approval is limited to the
exact change and scope authorized; it does not authorize unrelated controlled changes.

After approval, before implementation:

1. Identify the exact approved architecture change, scope, and approval evidence.
2. Identify every controlled artifact potentially affected by the change.
3. Inspect affected documentation for inconsistencies with the approved architecture.
4. Update all documentation actually affected, within the approved scope. Do not
   modify unaffected documents merely for consistency of wording.
5. Identify existing tests whose assumptions, contracts, fixtures, or expected
   behavior are affected. Update or replace tests only when the approved change
   legitimately changes what they must verify; record why each change is needed.
   Never weaken an unaffected valid test merely to make implementation pass.
6. Only after documentation is synchronized and test implications are resolved,
   including necessary test updates, update implementation.
7. Run relevant validation and obtain independent review of documentation, tests,
   and implementation together. Report when independent review is unavailable.

At minimum, every approved architecture change must trigger an impact check of:

- `docs/REQUIREMENTS.md`;
- `docs/DOMAIN.md`;
- `docs/ARCHITECTURE.md`;
- `docs/AGENT_ARCHITECTURE.md`;
- `docs/DATA_MODEL.md`;
- `docs/API.md`;
- `docs/TESTING.md`;
- `docs/AI_VALIDATION.md`;
- `docs/DECISIONS.md`;
- active execution plans;
- affected automated tests;
- affected backend/frontend/AI implementation.

Checking an artifact does not imply it must be modified. This list is a minimum,
not a substitute for identifying other potentially affected controlled artifacts.

If the change reveals that an already approved requirement, domain rule, business
rule, actor meaning, acceptance criterion, or product-agent responsibility must
also change, STOP affected work. Architecture approval does not automatically
authorize changes to requirements or domain semantics. Report the newly discovered
conflict, propose the additional controlled change and its impact, and obtain
separate explicit user approval before proceeding. Apply the existing change-control
workflow to any other controlled change outside the approved scope as well.

Use the Architecture change impact section specified in `PLANS.md` to track
synchronization. After synchronization, record which artifacts were checked,
changed, or checked and found unaffected; which tests changed and why; validation
and independent review performed; and remaining inconsistencies or open questions.
Keep approval evidence, scope, and approved artifact revision in `docs/DECISIONS.md`.

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

## Language of project documentation

The main text of `docs/*.md` must be written in Russian so that the user can
fully review the documentation.

English is allowed and preferred for:

- identifiers;
- future class, function, and variable names;
- entity names intended for implementation;
- API field names;
- enum values;
- names of libraries, technologies, protocols, and standards.

When first introducing an important entity, prefer a Russian term followed by
its English identifier in parentheses: <Russian term> (`EnglishIdentifier`).
Use a consistent Russian translation for each identifier across all documents.
Do not translate code, commands, file names, or technical identifiers.

## Clarification gate

For any substantive task, do not immediately start editing files, designing,
implementing, or making project decisions.

Before acting, first determine whether the task is sufficiently specified.

A task is substantive if it may affect:
- requirements;
- domain model;
- architecture;
- data model;
- API contracts;
- product-agent responsibilities;
- user flows;
- testing strategy;
- AI behavior;
- security;
- persistence;
- technology choices;
- multiple project files.

If important information is missing, ambiguous, contradictory, or can reasonably
be interpreted in more than one way:

1. do not make assumptions;
2. do not choose an option silently;
3. do not modify controlled files yet;
4. ask the user clarifying questions;
5. explain briefly why each important question matters;
6. when useful, provide possible answer options without selecting one;
7. wait for the user's answers;
8. reassess whether further clarification is required;
9. ask another round of questions if material uncertainty remains;
10. only begin the task when the information is sufficient or the user explicitly
authorizes proceeding with stated assumptions.

Prefer multiple rounds of clarification over filling gaps with assumptions.

Do not treat silence, previous guesses, common practice, or implementation
convenience as user approval.

For trivial and unambiguous actions, additional clarification is not required.

## Clarify → Propose → Execute

For substantive work, follow three separate phases.

### Phase 1 — CLARIFY

Allowed:
- inspect existing files;
- analyze approved documentation;
- identify contradictions and missing information;
- ask questions;
- list alternatives.

Not allowed:
- modify controlled project artifacts;
- select architecture or technologies;
- implement code;
- convert assumptions into requirements.

Stay in CLARIFY until enough information is available.

### Phase 2 — PROPOSE

Present:
- proposed decisions;
- alternatives where relevant;
- consequences;
- affected files;
- assumptions;
- unresolved questions.

For controlled artifacts, wait for explicit user approval before execution.

### Phase 3 — EXECUTE

Only after the required clarification and approval:
- update documentation;
- update tests where applicable;
- implement approved changes;
- validate the result.

Never collapse CLARIFY, PROPOSE, and EXECUTE into one step for substantive
requirements, architecture, or design work.

## Clarification depth

For requirements, domain analysis, architecture, data modeling, AI workflow design,
security, and user-flow design, perform deep clarification.

Actively look for:
- undefined actors;
- unclear terminology;
- missing boundaries;
- hidden assumptions;
- alternative interpretations;
- exceptional cases;
- lifecycle questions;
- permissions and responsibility;
- failure cases;
- human approval points;
- data provenance;
- privacy and security implications;
- non-functional requirements;
- measurable acceptance criteria.

Ask questions in manageable batches.

For a new major area, the first clarification round should usually contain
approximately 10–20 high-value questions grouped by topic.

After receiving answers, perform another gap analysis and ask a second round if
material gaps remain.

Do not ask questions whose answers are already explicitly present in approved
documentation.

## User-review priority

Optimize for user reviewability rather than autonomous speed.

When there is a trade-off between:
- proceeding quickly using an assumption, and
- asking the user for clarification,

prefer clarification whenever the assumption could materially affect the product,
architecture, tests, or future implementation.
