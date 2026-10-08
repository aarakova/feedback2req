# AI validation

Status: TEMPLATE with user-stated invariants. Detailed evaluation design, datasets,
metrics, and thresholds remain TODO; no implementation is authorized by this file.
Approval record/revision: TODO; see [DECISIONS.md](DECISIONS.md).

## Project invariants

1. **Traceability:** analytical conclusions and generated requirements retain
   references to supporting source feedback or approved product documentation.
2. **Explicit uncertainty:** unsupported or uncertain conclusions are marked as
   such instead of presented as facts.
3. **Role separation:** feedback analysis, requirement generation, and requirement
   verification are separate product responsibilities.
4. **Human control:** unsupported or disputed conclusions must not silently become
   approved product requirements.
5. **Source preservation:** original source material and derived analysis remain
   distinguishable.
6. **Validation:** eventually test AI behavior against explicit evaluation criteria;
   do not rely on exact natural-language matching unless wording is required.

## Evaluation goals

TODO: Translate approved requirements and these invariants into evaluation criteria,
including role separation and source preservation.

## Datasets/scenarios

TODO: Define representative scenarios, dataset provenance, and expected judgments.

## Traceability checks

TODO: Define checks that references exist and actually support the conclusion.

## Unsupported-claim checks

TODO: Define support and uncertainty judgments and how they are evaluated.

## Contradiction checks

TODO: Define contradiction scenarios and approved expected behavior.

## Ambiguity checks

TODO: Define ambiguity criteria and when clarification is required.

## Duplicate detection

TODO: Define duplication criteria and evaluation scenarios.

## Human review criteria

TODO: Define when and how human review resolves unsupported or disputed conclusions;
do not assume an approval workflow or interface.

## Metrics to be defined later

TODO: Propose metrics, thresholds, and assessment methods for explicit approval.
