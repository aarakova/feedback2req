# Independent Access QA

Reviewed SHA: 9084a58aefb5c5efd9668bf5df36c12872aeb574; base main 6c01d811.
Scope: DEC-012 and unchanged I1/I2a contracts. No application, existing tests,
models, migrations, approved documents or workflow changes.
Publication of these review additions was explicitly authorized after the audit.

New [access-independent.spec.ts](../../frontend/tests/access-independent.spec.ts)
protects six previously missing combinations: canonical UUID input; failed middle
page and deduplication; removal AFTER successful preflight; concurrent add AFTER
absence preflight; failed reconciliation retaining uncertainty; committed late
mutation after navigation. Both races explicitly accept the documented PUT/upsert
limitation and require one write, disclosed consequences and correct server state.

Actual results so far: original 40 browser tests passed through Vite; independent
six passed through Vite; 11 real PostgreSQL backend authorization/security tests
passed with -W error; TypeScript and Vite production build passed.

Known defects are opt-in only, outside normal test directories:

- [test_audit_input.py](../../backend/regressions/test_audit_input.py): four AUD-01
  cases (NUL POST/PATCH and surrogate register/login), all fail with 500 vs 422;
  privacy and rollback assertions pass before the final status assertion.
- [password-unicode.spec.ts](../../frontend/regressions/password-unicode.spec.ts):
  AUD-03, real API accepts an 800-code-point password, browser insertion truncates
  it. The regression fails without changing any limit. Its separate config is
  [playwright.regressions.config.ts](../../frontend/playwright.regressions.config.ts).

Commands (requires isolated test API/database as in the repository instructions):

```text
python -B -m pytest -p no:cacheprovider backend/regressions/test_audit_input.py -q -W error
npx playwright test tests/access-independent.spec.ts
npx playwright test --config=playwright.regressions.config.ts
```

Final Nginx verification: all 46 browser tests passed (2.1 minutes), using the
new build and actual API/PostgreSQL in a private namespace-local proxy topology.
The opt-in AUD-03 regression also fails there, at 762 vs 800 code points.
This is not a rerun of Compose DNS/spoofing/restart; those have exact-SHA CI evidence.
All owned containers were removed; original working container IDs remain healthy.
The working stack/shared tags are untouched.
