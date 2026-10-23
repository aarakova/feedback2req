# Independent branch QA

Authorized scope: inspect frozen branches, add independent tests, run isolated
checks, and produce an integration assessment. The original review excluded
production, workflow and contract changes, commits, pushes and branch integration.
After the review, the user explicitly authorized saving, committing and pushing
the results. This publication does not authorize implementation or integration.

Frozen inputs:

| Branch | SHA | merge-base with main |
|---|---|---|
| main | 6c01d8113a40eb514e180453ec8e4ae1d8679b6e | same |
| agents/ai-feedback2req-testing-preparation | 800d9fb157a5e7109f1a0af2cdc0041f65ea6177 | 3ab6af02cb634fb3f8fae49ff4571ab61eff713c |
| agents/pasted-text-processing-adf660ee | 9084a58aefb5c5efd9668bf5df36c12872aeb574 | 6c01d8113a40eb514e180453ec8e4ae1d8679b6e |
| agents/pasted-text-processing | 766ac01174ac44fda92f68d948f57e22c2666d5c | 6c01d8113a40eb514e180453ec8e4ae1d8679b6e |

All source worktrees initially clean. Review worktrees are under
the local QA worktree directory; test/ai-evals-review and test/frontend-access-review are new
branches; i2b-spec-review is a detached, read-only review checkout.

1. Inventory diffs, approvals, existing tests, and exact-SHA CI: complete.
2. AI harness review and independent tests: complete; 55 normal tests pass,
   four opt-in tests expose two MEDIUM defects without production changes.
3. Access review: complete; original 40 plus independent six pass through Vite;
   all 46 pass through Nginx, real API/PostgreSQL; tsc/Vite build and 11 backend
   security/authorization tests pass.
4. AUD-01–03: complete; four API and one browser opt-in regressions fail for
   the known defects; proposed worker gate passes 0 and rejects injected 17.
5. PROVISIONAL I2b matrix (44 scenarios) and CI proposal: delivered, NOT APPLIED.
6. Checks/resource cleanup: complete. All owned containers removed; original
   three working containers retain their IDs and remain healthy. All original
   worktrees and detached spec checkout remain clean; tracked diffs are empty.
7. REPORT.md, I2B_TEST_MATRIX.md, CI_PROPOSAL.md and keyed 24-fault evidence
   delivered. Review additions are now committed on the two test branches;
   reports are preserved on test/independent-qa-results based on frozen main.

Isolation: immutable existing image IDs, no changes to shared tags, unique
containers, network namespaces and temporary PostgreSQL data, no working DB.
Native Python remains unavailable; use existing Linux tool images.

Final evidence: all four exact SHAs have successful GitHub Actions runs. Evals
CI has only i1 and contains no AI-evals test/generator steps. Access CI has i1
and deployment; the new independent tests have LOCAL evidence only. I2b remains
documentation-only and PROPOSED. No contracts, production, old tests, CI, tags,
shared services or user data changed during the review. Only the subsequent
publication adds commits and pushes; no branches are merged.
