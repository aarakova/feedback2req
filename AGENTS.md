# Repository instructions

feedback2req is a web system that analyzes text feedback and speech in audio/video
alongside product documentation to produce evidence-linked improvement requirements
and dashboards. People make the final decisions on requirements.

## Approved sources and scope

- Use approved documents in `docs/` and approval records in `docs/DECISIONS.md`
  as the source of truth. Drafts, TODOs, plans, research, and agent output are not
  approvals. Respect the scope and revision of each approved decision.
- Consult `docs/REQUIREMENTS.md` and `docs/DOMAIN.md` for product rules;
  `docs/ARCHITECTURE.md`, `docs/AGENT_ARCHITECTURE.md`, `docs/DATA_MODEL.md`, and
  `docs/API.md` for approved design; `docs/TESTING.md` and `docs/AI_VALIDATION.md`
  for applicable validation criteria and AI invariants.
- Work within the current user-authorized task and approved project decisions.
  Do not treat unfinished design areas as permission to invent their contracts.

## Autonomy and clarification

- Assess whether a substantive task is sufficiently specified before starting.
  If material ambiguity, conflicting sources, missing requirements, or fundamentally
  different behavior or architecture options remain, ask focused questions and
  wait for answers before doing the affected work. Explain why the answers matter.
- Continue clarification while material uncertainty remains. Do not invent missing
  requirements, decide substantial architecture questions for the user, or present
  assumptions as approved facts. Use answers already in approved docs and context.
- When the task is clear, independently choose implementation, refactoring, testing,
  and debugging techniques within approved behavior, architecture, and contracts.
  Ordinary technical details and operations within the authorized task need no
  repeated approval or full design process.
- Keep planning proportional to the task; consult `PLANS.md` when a written plan
  is needed. Trivial changes need no additional plans, reports, or decision records.

## Project changes and consistency

- Obtain explicit user approval before changing agreed requirements, domain rules,
  substantial architecture or technology decisions, data models, API contracts,
  product-agent responsibilities, or other agreed project contracts.
- If approved design is insufficient, pause the affected work, explain the problem,
  and propose a concrete change with its consequences and affected artifacts.
  Approval covers only the agreed scope; newly discovered changes outside it need
  separate approval. Record project approvals, scope, and artifact revisions in
  `docs/DECISIONS.md`.
- For approved architecture or contract changes, check related components and update
  documentation, tests, and implementation within scope. Keep them consistent;
  do not leave architecture or contract changes undocumented. Avoid unrelated edits.

## Implementation and validation

- Follow existing project conventions and explicit user preferences. Write
  maintainable, testable code and run checks relevant to the change.
- Base tests on approved behavior. Do not weaken valid tests or rewrite expected
  results solely to conceal implementation defects.
- Report failed checks, unresolved errors, unfinished work, material uncertainty,
  and validation not performed. Use independent review for substantial changes
  when available and disclose review limitations.
- Do not perform destructive or irreversible actions without explicit permission.

Codex development agents in `.codex/agents/` work on this repository; they are
separate from the application's AI roles in `docs/AGENT_ARCHITECTURE.md`.
Delegation stays within the authorized scope and does not grant design approval.
