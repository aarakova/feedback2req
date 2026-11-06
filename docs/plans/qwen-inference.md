# Qwen inference preparation

User-authorized experiment, 2026-11-04. Base: `410b936e451629a53ca1eb0fb15a4908961155b6`.
Branch: `experiment/qwen-group-findings`; isolated worktree. No production, F2,
contract 1.0, worker or other feature-branch changes are authorized here.

1. Verify base/F1/grouping history, approved contracts and preliminary evaluation rules.
2. Audit both adapters; inspect hardware and official model/runtime sources.
3. Build an opt-in, loopback-only, synthetic-only inference harness with bounded
   transport, pinned runtime/weights, raw responses, validation and review sheets.
4. Run mocked adapter and existing contract/grouping/evaluation checks in the
   existing offline Docker test image; obtain independent review.
5. Document results, reproduction, resource limits, separate 9B plan and limitations;
   commit only this branch. Request installation/download/run approval last.

Model installation, weight downloads, system changes and external computation
remain approval gates. Article referred to by the user is absent from the supplied
context; request its link while continuing independent preparation.

Sources: docs/DECISIONS.md (DEC-001–006 and scoped later decisions),
docs/AI_CONTRACTS.md, docs/AI_VALIDATION.md, docs/AGENT_ARCHITECTURE.md,
ai/group_findings/, evals/ai/REVIEW.md. No new product/design approval is inferred.

Status: preparation completed 2026-11-06. Verified fetch/base and created own
branch/worktree; inspected adapters, history, approved sources and hardware;
prepared isolated serving, configs, 24-case inventory, runner, bounded transport,
resource sampler, raw/validation/review separation and reproduction/report docs.
21 new tests, 37 grouping tests, 47 eval tests passed; contract validator, Ruff,
format, PowerShell parser and Compose config passed. Independent read-only review
completed, findings fixed and re-reviewed; reviewer did not run tests/inference
or independently verify external sources. No production/F2/contracts changed.

Remaining approval-dependent work: runtime/Python setup if needed, weights,
actual model/runtime/schema compatibility, real inference, memory/latency/semantic
measurements. No installation/download/model call or external computation was
performed. Current ~0.40 GiB free RAM is insufficient; free resources or agree a
separate host before trying inference. Missing article remains an explicit input
for later study replication. Commit prepared work; no push/merge authorized.
