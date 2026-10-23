# CI proposal — NOT APPLIED; requires user approval

Frozen baseline: main 6c01d811; evals 800d9fb; Access 9084a58; I2b 766ac01.
No workflow, common Compose file, or shared test infrastructure was changed.

## What runs now

| Exact SHA | Run | Actual relevant jobs |
|---|---|---|
| main 6c01d811 | 39958839314 | i1 + deployment; successful |
| evals 800d9fb | 39995098523 | i1 only; NO evals tests/generator/Ruff/CLI |
| Access 9084a58 | 39994169920 | i1 + deployment, including both browser modes; successful |
| I2b 766ac01 | 40000547178 | i1 + deployment for existing application; NO future queue tests |

The evals branch uses the pre-DEC-011 workflow inherited from merge-base 3ab6af0.
Its green result is not evidence for its 47 harness tests. Access uses ordinary
Playwright test discovery, so its committed 22 new scenarios join the 18 prior
scenarios. The independent six tests have local evidence; they were committed
after the review on test/frontend-access-review. No Actions outcome for the new
review commits is claimed in this proposal.

## Minimum per-PR addition after approval

In the approved integration state containing evals, reuse the existing i1 Python
environment: requirements-test.lock already pins jsonschema 4.26.0,
referencing 0.37.0, attrs 26.1.0, rpds-py 2026.9.1 and Ruff 0.17.1, matching
the harness requirements. No model, provider key, database or new paid service
is needed for these steps:

```yaml
- run: python -B -W error -m unittest discover -s evals/ai/tests -v
- run: python -B evals/ai/build_dataset.py
- run: python -m ruff check evals/ai
- run: python -m ruff format --check evals/ai
```

The unittest suite already exercises CLI exit 0/1/2, controls, every expected
fault code, compare compatibility and no overwrite. A fault replay must return
1. Never add `|| true` to hide arbitrary failures; compare its actual code with
the expected 1 and assert the 24 expected codes. Input/tool failures returning
2 must fail the check. Deterministic generation runs WITHOUT --write.

Keep known-defect regressions outside mandatory discovery until their fix order
is agreed. This review added no skip/xfail and changed no existing assertions.

## Worker gate: AUD-02 remains

Deployment currently runs `up -d`, then waits only for backend/frontend. Add an
explicit wait for the finite worker and require its container State.ExitCode=0.
Do not interpret a successful detached startup or healthy web services as that
result. A private executable demonstration is [worker-exit-gate.ps1](worker-exit-gate.ps1).
It uses a unique Compose project, immutable existing image, no network, no host
ports or volumes, and checks/removes only its own labelled container:

```powershell
powershell -NoProfile -File docs/qa/2026-10-23-independent-review/worker-exit-gate.ps1 -InjectedExitCode 0
powershell -NoProfile -File docs/qa/2026-10-23-independent-review/worker-exit-gate.ps1 -InjectedExitCode 17
```

The first must return 0; the negative injection must return 1, although detached
Compose startup itself returns 0 in both. This demonstrates the proposed gate;
it does not claim that the unchanged workflow already contains it. Applying the
gate to the actual worker service and an automated negative job needs approval.
Both cases were actually verified. This Windows host blocks .ps1 via -File;
the reviewed script body was invoked inline with ScriptBlock.Create instead,
without changing ExecutionPolicy or any global setting.

## Heavier and manual checks

- Keep real PostgreSQL, migrations, restart, proxy spoofing, Nginx and Vite
  browser regressions in deployment/integration jobs with isolated resources.
- Add future I2b PG/process/watchdog tests only after specification approval AND
  separate implementation permission; use the provisional matrix.
- Native Windows, Firefox/Safari, TLS/LAN and a dedicated-Engine restart remain
  explicit manual/target-environment checks. Never restart the shared Engine.
- Human review of PRELIMINARY annotations, S03/S12 claims, conflicting meanings,
  severity/scope and semantic robustness remains manual. No final score or
  precision/recall follows from the automated replay.
