# Диагностический replay AI

**Разметка предварительная; окончательной оценки качества модели нет.**

Режим: `synthetic_fixture_replay`. Записей: 24.
Получены ответы: 20; технических сбоев: 4.
Не назначено примеров: 36; экспертных листов pending: 24.

| Категория автоматических проверок | Записей с нарушениями / всего |
|---|---:|
| technical | 4 / 24 |
| structure | 5 / 24 |
| provenance | 10 / 24 |
| coverage | 4 / 24 |
| consistency | 2 / 24 |

## Отдельные экспертные критерии (предварительно)

Значения met/not_met/uncertain/not_applicable задаёт эксперт; pending означает отсутствие оценки.

| Критерий | Распределение вердиктов |
|---|---|
| semantic_support | pending: 24 |
| semantic_completeness | pending: 24 |
| absence_of_false_positives | pending: 24 |
| direct_vs_inferred | pending: 24 |
| uncertainty_and_conflicts | pending: 24 |
| severity_and_blocking | pending: 24 |
| robustness | pending: 24 |

## Сценарии

| Сценарий / пример / попытка | Операция | Диагностика | Эксперт |
|---|---|---|---|
| S01 / extract / 1 | extract_feedback | SCHEMA-ADDITIONALPROPERTIES | pending |
| S01 / extract / 2 | extract_feedback | SCHEMA-ENUM, SCHEMA-ONEOF | pending |
| S11 / unicode-repeated / 1 | extract_feedback | QUOTE-OCCURRENCE | pending |
| S11 / unicode-repeated / 2 | extract_feedback | QUOTE-OCCURRENCE | pending |
| S01 / extract / 3 | extract_feedback | FINDING-FRAGMENT-MISSING | pending |
| S01 / extract / 4 | extract_feedback | LOCAL-IDS-NOT-UNIQUE | pending |
| S01 / extract / 5 | extract_feedback | LINK-WRONG-ROLE | pending |
| S01 / extract / 6 | extract_feedback | COVERAGE-KEYS, RESULT-FROM-UNREVIEWED | pending |
| S11 / evidence-control / 1 | generate_requirements | REQUIREMENT-EVIDENCE-MISMATCH | pending |
| S05 / group / 1 | group_findings | GROUP-COVERAGE, GROUP-MEMBER-MISSING, GROUP-MEMBER-NOT-CONSIDERED, RESULT-FROM-UNREVIEWED | pending |
| S06 / group / 1 | group_findings | CONFLICT-MEMBER-OUTSIDE-GROUP | pending |
| S06 / question / 1 | generate_requirements | QUESTION-SCOPE | pending |
| S10 / partial-comparison / 1 | verify_requirement | DUPLICATES-INCOMPLETE-CLEAN | pending |
| S10 / partial-comparison / 2 | verify_requirement | COMPARISON-PARTIAL-COVERAGE | pending |
| S09 / unsupported / 1 | verify_requirement | ISSUE-CHECK-CONTRADICTION | pending |
| S09 / unsupported / 2 | verify_requirement | ISSUE-QUESTION-MISSING | pending |
| S13 / own-revision / 1 | verify_requirement | DUPLICATE-SAME-REQUIREMENT | pending |
| S10 / independent-pdf / 1 | extract_feedback | TECH-TIMEOUT | pending |
| S10 / independent-pdf / 2 | extract_feedback | TECH-PROVIDER_ERROR | pending |
| S10 / independent-pdf / 3 | extract_feedback | TECH-INVALID_RESPONSE | pending |
| S10 / independent-pdf / 4 | extract_feedback | TECH-CANCELLED | pending |
| S11 / unicode-repeated / 3 | extract_feedback | RESPONSE-JSON-DUPLICATE-PROPERTY | pending |
| S11 / unicode-repeated / 4 | extract_feedback | RESPONSE-JSON-NONFINITE-NUMBER | pending |
| S11 / unicode-repeated / 5 | extract_feedback | RESPONSE-JSON-UNREADABLE | pending |

## Ограничения

- PRELIMINARY annotations; no final semantic quality score or model ranking.
- Coverage is declared, not proof of semantic reading.
- Trusted states are synthetic fixture facts, not database/permission/race checks.
- No ASR, application lifecycle, provider calls, or deletion implementation tested.
- Semantic support, completeness, false positives, uncertainty/conflicts and robustness require expert review.
- Engineering reference fixtures, including intentional_semantic_error, are not positive semantic gold.
- S06 has only conflicting positions: independent continuation during a semantic conflict is not covered; S10 covers a technical failure.
