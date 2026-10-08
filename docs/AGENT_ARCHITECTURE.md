# Product-agent architecture

Status: TEMPLATE with user-stated responsibilities only; orchestration and
implementation design remain unresolved. Approval record/revision: TODO;
see [DECISIONS.md](DECISIONS.md).
These are future application roles, not the Codex development agents in
`.codex/agents/`.

## Product-agent roles

User-stated responsibilities, not an implementation design:

- Feedback Analysis Agent: identify and group problems, requests, observations,
  and user needs from feedback.
- Requirements Generation Agent: transform supported findings into structured
  requirements while retaining original evidence references.
- Requirements Verification Agent: check contradictions, unsupported conclusions,
  ambiguity, duplication, missing evidence, and questions for human clarification.

TODO: Clarify detailed responsibilities and obtain design approval.

## Inputs

TODO: Specify each role's approved input contract and evidence context.

## Outputs

TODO: Specify outputs and validation criteria without assuming schemas.

## Boundaries

Analysis, generation, and verification remain separate product responsibilities.
TODO: Define allowed actions and boundaries; logical role separation does not
select a deployment topology or framework.

## Handoffs

TODO: Design approved handoffs and orchestration; no protocol is selected.

## Failure/uncertainty handling

Mark uncertain or unsupported conclusions explicitly. Unsupported or disputed
conclusions must not silently become approved requirements.
TODO: Design failure handling and human clarification behavior.

## Traceability requirements

Preserve references to supporting source feedback or approved product documents.
Keep original material distinguishable from derived analysis; see the complete
[AI invariants](AI_VALIDATION.md#project-invariants).
TODO: Design the traceability mechanism after requirements approval.

## Open questions

TODO: Record unresolved role boundaries, contracts, and orchestration decisions.
