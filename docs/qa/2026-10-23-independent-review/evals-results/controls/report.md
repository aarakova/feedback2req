# Диагностический replay AI

**Разметка предварительная; окончательной оценки качества модели нет.**

Режим: `synthetic_fixture_replay`. Записей: 46.
Получены ответы: 46; технических сбоев: 0.
Не назначено примеров: 0; экспертных листов pending: 46.

| Категория автоматических проверок | Записей с нарушениями / всего |
|---|---:|
| technical | 0 / 46 |
| structure | 0 / 46 |
| provenance | 0 / 46 |
| coverage | 0 / 46 |
| consistency | 0 / 46 |

## Отдельные экспертные критерии (предварительно)

Значения met/not_met/uncertain/not_applicable задаёт эксперт; pending означает отсутствие оценки.

| Критерий | Распределение вердиктов |
|---|---|
| semantic_support | pending: 46 |
| semantic_completeness | pending: 46 |
| absence_of_false_positives | pending: 46 |
| direct_vs_inferred | pending: 46 |
| uncertainty_and_conflicts | pending: 46 |
| severity_and_blocking | pending: 46 |
| robustness | pending: 46 |

## Сценарии

| Сценарий / пример / попытка | Операция | Диагностика | Эксперт |
|---|---|---|---|
| S01 / extract / 1 | extract_feedback | Нарушений в реализованных проверках нет | pending |
| S01 / generate / 1 | generate_requirements | Нарушений в реализованных проверках нет | pending |
| S01 / verify-control / 1 | verify_requirement | Нарушений в реализованных проверках нет | pending |
| S01 / paraphrase / 1 | extract_feedback | Нарушений в реализованных проверках нет | pending |
| S02 / extract / 1 | extract_feedback | Нарушений в реализованных проверках нет | pending |
| S02 / generate / 1 | generate_requirements | Нарушений в реализованных проверках нет | pending |
| S03 / extract / 1 | extract_feedback | Нарушений в реализованных проверках нет | pending |
| S03 / generate / 1 | generate_requirements | Нарушений в реализованных проверках нет | pending |
| S03 / generate-combined / 1 | generate_requirements | Нарушений в реализованных проверках нет | pending |
| S04 / observation / 1 | extract_feedback | Нарушений в реализованных проверках нет | pending |
| S04 / no-requirements / 1 | generate_requirements | Нарушений в реализованных проверках нет | pending |
| S04 / no-findings / 1 | extract_feedback | Нарушений в реализованных проверках нет | pending |
| S05 / group / 1 | group_findings | Нарушений в реализованных проверках нет | pending |
| S05 / generate / 1 | generate_requirements | Нарушений в реализованных проверках нет | pending |
| S05 / reordered / 1 | group_findings | Нарушений в реализованных проверках нет | pending |
| S06 / group / 1 | group_findings | Нарушений в реализованных проверках нет | pending |
| S06 / question / 1 | generate_requirements | Нарушений в реализованных проверках нет | pending |
| S06 / verify / 1 | verify_requirement | Нарушений в реализованных проверках нет | pending |
| S07 / extract / 1 | extract_feedback | Нарушений в реализованных проверках нет | pending |
| S07 / question / 1 | generate_requirements | Нарушений в реализованных проверках нет | pending |
| S07 / verify / 1 | verify_requirement | Нарушений в реализованных проверках нет | pending |
| S08 / extract / 1 | extract_feedback | Нарушений в реализованных проверках нет | pending |
| S08 / question / 1 | generate_requirements | Нарушений в реализованных проверках нет | pending |
| S08 / verify / 1 | verify_requirement | Нарушений в реализованных проверках нет | pending |
| S09 / unsupported / 1 | verify_requirement | Нарушений в реализованных проверках нет | pending |
| S09 / contradiction / 1 | verify_requirement | Нарушений в реализованных проверках нет | pending |
| S09 / control / 1 | verify_requirement | Нарушений в реализованных проверках нет | pending |
| S09 / missed-unsupported / 1 | verify_requirement | Нарушений в реализованных проверках нет | pending |
| S09 / false-positive / 1 | verify_requirement | Нарушений в реализованных проверках нет | pending |
| S10 / speech-usable / 1 | extract_feedback | Нарушений в реализованных проверках нет | pending |
| S10 / speech-uncertain / 1 | extract_feedback | Нарушений в реализованных проверках нет | pending |
| S10 / independent-pdf / 1 | extract_feedback | Нарушений в реализованных проверках нет | pending |
| S10 / partial-comparison / 1 | verify_requirement | Нарушений в реализованных проверках нет | pending |
| S10 / partial-found / 1 | verify_requirement | Нарушений в реализованных проверках нет | pending |
| S11 / unicode-repeated / 1 | extract_feedback | Нарушений в реализованных проверках нет | pending |
| S11 / evidence-control / 1 | generate_requirements | Нарушений в реализованных проверках нет | pending |
| S11 / irrelevant-evidence / 1 | generate_requirements | Нарушений в реализованных проверках нет | pending |
| S12 / partial-sufficient / 1 | verify_requirement | Нарушений в реализованных проверках нет | pending |
| S12 / partial-insufficient / 1 | verify_requirement | Нарушений в реализованных проверках нет | pending |
| S12 / all-deleted / 1 | verify_requirement | Нарушений в реализованных проверках нет | pending |
| S13 / own-revision / 1 | verify_requirement | Нарушений в реализованных проверках нет | pending |
| S13 / other-proposal / 1 | verify_requirement | Нарушений в реализованных проверках нет | pending |
| S13 / selected / 1 | verify_requirement | Нарушений в реализованных проверках нет | pending |
| S13 / previous-blocker / 1 | verify_requirement | Нарушений в реализованных проверках нет | pending |
| S14 / feedback-injection / 1 | extract_feedback | Нарушений в реализованных проверках нет | pending |
| S14 / document-injection / 1 | extract_feedback | Нарушений в реализованных проверках нет | pending |

## Ограничения

- PRELIMINARY annotations; no final semantic quality score or model ranking.
- Coverage is declared, not proof of semantic reading.
- Trusted states are synthetic fixture facts, not database/permission/race checks.
- No ASR, application lifecycle, provider calls, or deletion implementation tested.
- Semantic support, completeness, false positives, uncertainty/conflicts and robustness require expert review.
- Engineering reference fixtures, including intentional_semantic_error, are not positive semantic gold.
- S06 has only conflicting positions: independent continuation during a semantic conflict is not covered; S10 covers a technical failure.
