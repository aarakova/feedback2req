# Independent QA additions

Reviewed SHA: 800d9fb157a5e7109f1a0af2cdc0041f65ea6177, merge-base with main:
3ab6af02cb634fb3f8fae49ff4571ab61eff713c. This branch has no DEC-011 infrastructure.
No application, contracts, dataset, annotations, existing tests or CI were edited.
Publication of these review additions was explicitly authorized after the audit.

[tests/test_independent_review.py](tests/test_independent_review.py) adds eight
ordinary tests: nested unknown-field privacy and immutability; key/ID collisions
across object types; non-BMP code-point offsets; symlink escape; boolean numeric
metadata; external-response-byte binding of expert forms; schema compatibility
and comparison output preservation. All eight passed independently, after the
original 47 tests passed. The final combined suite also passed: 55 tests,
23.499 seconds, -W error. Ruff check and format --check passed after formatting
only the two new Python files.

[regressions/test_known_defects.py](regressions/test_known_defects.py) contains
four deliberately strict regressions for two confirmed checker defects:

1. previous_fragments bypass trusted quote/locator/reliability checks.
2. verify_requirement accepts substantive issues with not_processed coverage
   when all CheckAssessment.considered_keys arrays are empty.

The four tests fail on the reviewed implementation. They are OUTSIDE tests/
and therefore outside ordinary unittest discovery and the proposed mandatory
job. There is no skip/xfail and no change to expected behavior to make them green.

```text
python -B -W error -m unittest discover -s evals/ai/tests -v
python -B -W error -m unittest discover -s evals/ai/regressions -v
```

CLI validation/reproducibility: 14 scenarios, 46 examples, 22 generated artifacts;
controls replay exit 0, all 24 fault records replay exit 1, compare exit 0,
attempted overwrite exit 2. Original contract validator passed. Every review
remains PRELIMINARY; no semantic labels were approved by this work.
