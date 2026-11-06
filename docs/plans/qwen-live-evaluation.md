# Qwen live evaluation / F2 compatibility

Authorized iteration 2026-11-06. Own branch/worktree from
`c03d34310efd5c92a29450a2d6d06dc87d64fb9c`; pinned read-only F2 reference
`4c62684e7769d2c3a71de3264aa15e954a1262d0`. Fetch and both remote HEAD checks passed.
No merges or changes to F2/production/AI contracts 1.0.

1. Inspect exact published F2 integration, validators and approval records.
2. Inspect current hardware and real availability/access conditions of free GPU
   environments. Never install runtime/download weights/transfer data without
   specific permission; never use paid resources or identity verification.
3. Extend existing harness for product/experimental prompts, controlled sampling
   matrix and explicit D/K/S/U cases. Preserve raw evidence and all provenance.
4. Validate adapter → component → unchanged F2 → PG persistence/GET, using an
   explicitly synthetic transport in an isolated disposable test database.
   Real provider path must separately fit F2's 120s deadline, retain diagnostics
   and mark ai_performed accurately; no production worker/API connection.
5. Deliver a portable synthetic-only bundle and gated free-GPU instructions if
   no authorized usable runtime is available. Report actual blockers/unknowns.
6. Run experimental/grouping/schema tests, targeted PG tests and independent
   review; commit and publish own branch as authorized continuation.

Known observations: RAM free ~0.68 GiB / 6.94 GiB, Docker ~3.30 GiB; no confirmed
compute VRAM. Colab page is signed out; actual GPU allocation/quota unknown.
User input requested asynchronously for authorized environment/access. Continue
independent tests/package work while awaiting the answer.

Important F2 limits: 30s lease / 120s deadline; old 180s experiment timeout must
not be passed directly. F2 additionally checks string sizes, duplicate conflict
positions and narrower annotation targets. Structural PASS is not semantic PASS.

Completed preparation/verification: 34 harness tests, 37 standalone tests,
8 own PG tests and 38 pinned F2 regression tests PASS; 1 actual-model test
explicitly SKIPPED. Contract validator and Ruff PASS. Added both unchanged prompt
profiles, matched/recommended sampler matrices, 34-case inventory, pinned F2
hash checks, 90s provider boundary, gated notebook/bootstrap and portable bundler.
Independent read-only review completed; both P2 findings fixed/re-read.

Concrete outstanding blocker: no sufficient local resources and no authorized,
allocated external GPU runtime. No real inference, runtime/weight installation,
external data transfer, semantic assessment or real F2 model path occurred.
Deliver committed source and sealed bundle; minimum user actions and all limits
are documented in experiments/qwen/LIVE_EVALUATION.md. No production/contract/F2
source changes or merge. Model use remains opt-in after explicit permissions.
