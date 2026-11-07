"""Deterministic, explicitly synthetic controls. Never a production trust adapter."""

import json
from copy import deepcopy
from pathlib import Path

from .model import Verification, fingerprint
from .validation import prepare


def boolean(value):
    return {"kind": "boolean", "allowed": [value]}


def base(texts=None):
    texts = texts or ["Между сеансами сохраняйте фильтры.", "Между сеансами сбрасывайте фильтры."]
    findings, fragments = [], []
    for index, text in enumerate(texts, 1):
        key = f"f{index}"
        findings.append(
            {
                "key": key,
                "ref": {"kind": "finding", "id": key, "state_id": key + "-v1"},
                "text": text,
                "types": ["request"],
                "mode": "direct",
                "evidence": [{"kind": "available", "fragment_key": f"e{index}"}],
                "uncertainty_notes": [],
                "open_questions": [],
                "authorship": "ai",
            }
        )
        source = {"kind": "feedback_source", "id": f"source{index}", "state_id": "source-v1"}
        fragments.append(
            {
                "key": f"e{index}",
                "ref": {"kind": "fragment", "id": f"e{index}", "state_id": "fragment-v1"},
                "source_ref": source,
                "text_ref": deepcopy(source),
                "quote": text,
                "locator": {"start": 0, "end": len(text)},
                "reliability": "usable",
            }
        )
    request = {
        "contract_version": "1.0",
        "operation": "group_findings",
        "project_id": "synthetic-project",
        "request_id": "synthetic-request-v1",
        "input": {"findings": findings, "fragments": fragments, "documents": []},
    }
    response = {
        "coverage": [
            {"input_key": f["key"], "reviewed": True, "disposition": "completed"} for f in findings
        ],
        "uncertainties": [],
        "questions": [],
        "result": {
            "groups": [
                {
                    "local_id": "g1",
                    "title": "Фильтры",
                    "summary": "Кандидат противоположных позиций",
                    "finding_keys": [f["key"] for f in findings],
                    "considered_keys": [f["key"] for f in findings],
                    "context_keys": [],
                    "conflicts": [
                        {
                            "local_id": "c1",
                            "description": "Кандидат конфликта, не доказанный K",
                            "positions": [
                                {"description": "Сохранять", "finding_keys": ["f1"]},
                                {"description": "Сбрасывать", "finding_keys": ["f2"]},
                            ],
                        }
                    ],
                }
            ],
            "ungrouped_finding_keys": [],
        },
    }
    origin = {"kind": "human", "actor": "synthetic-curator", "method": "explicit_manual_fixture"}
    proposal = {
        "version": "formalization-v1",
        "origin": origin,
        "decomposition_rationale": "Два явно подготовленных атомарных ожидания о сохранении.",
        "model": {
            "id": "filter-retention",
            "version": "model-v1",
            "method": "explicit_atomic_partition",
            "rationale": "Один исследуемый случай: переход между сеансами.",
            "formal_model": {
                "object_id": "filters",
                "parameter_id": "retain",
                "situations": ["session"],
                "domain": {"kind": "boolean", "allowed": [False, True]},
            },
            "contexts": [{"id": "between_sessions", "situations": ["session"]}],
            "relations": [],
        },
        "atoms": [],
        "pair": {
            "left_atom_id": "a1",
            "right_atom_id": "a2",
            "rationale": "Сравнить эти два ожидания, не всю группу.",
        },
        "omissions": [],
        "omega": None,
    }
    data = {
        "bridge_version": "1",
        "grouping_request": request,
        "grouping_response": response,
        "selection": {
            "left_finding_keys": ["f1"],
            "right_finding_keys": ["f2"],
            "rationale": "Явно выбраны обе полные позиции кандидата конфликта.",
            "conflict": {
                "group_local_id": "g1",
                "conflict_local_id": "c1",
                "left_position": 0,
                "right_position": 1,
            },
        },
        "proposal": proposal,
    }
    for i, value in ((1, True), (2, False)):
        proposal["atoms"].append(
            {
                "id": f"a{i}",
                "object_id": "filters",
                "parameter_id": "retain",
                "context_id": "between_sessions",
                "values": boolean(value),
                "missing_fields": [],
                "sources": [
                    {
                        "finding_key": f"f{i}",
                        "finding_ref": deepcopy(findings[i - 1]["ref"]),
                        "evidence_keys": [f"e{i}"],
                    }
                ],
            }
        )
    return data


def disjoint_contexts(data):
    model = data["proposal"]["model"]
    model["formal_model"]["situations"] = ["desktop", "mobile"]
    model["contexts"] = [{"id": k, "situations": [k]} for k in ("desktop", "mobile")]
    model["relations"] = [{"left": "desktop", "right": "mobile", "relation": "disjoint"}]
    data["proposal"]["atoms"][0]["context_id"] = "desktop"
    data["proposal"]["atoms"][1]["context_id"] = "mobile"
    return data


def unknown_context():
    data = disjoint_contexts(
        base(["Сохраняйте фильтры (устройство не указано).", "На ПК сбрасывайте фильтры."])
    )
    atoms = data["proposal"]["atoms"]
    atoms[0]["context_id"], atoms[0]["missing_fields"] = None, ["conditions"]
    atoms[1]["context_id"] = "desktop"
    variants = []
    for situation in ("desktop", "mobile"):
        variants.append(
            {
                "left": {"conditions": [situation], "values": boolean(True)},
                "right": {"conditions": ["desktop"], "values": boolean(False)},
            }
        )
    data["proposal"]["omega"] = {
        "origin": {
            "kind": "human",
            "actor": "synthetic-curator",
            "method": "finite_fixture_enumeration",
        },
        "method": "all_cases_of_declared_two_case_fixture_model",
        "justification": (
            "В этой синтетической модели контекст выбирает ровно desktop или mobile; "
            "не утверждение о реальном мире."
        ),
        "declared_complete": True,
        "variants": variants,
    }
    return data


def catalog():
    cases = []

    def add(key, data, status, formal, explanation, *, structure=None, **flags):
        cases.append(
            {
                "id": key,
                "input": deepcopy(data),
                "expected_status": status,
                "expected_formal_class": formal,
                "expected_structural_class": structure or formal,
                "explanation": explanation,
                "synthetic_confirmations": flags,
                "interpretation_limit": (
                    "Класс относится только к явно подготовленной структуре; "
                    "смысловые метки предварительны."
                ),
            }
        )

    add(
        "01-direct-conflict",
        base(),
        "checked",
        "K",
        "Общие условия и непересекающиеся bool значения.",
    )
    add(
        "02-different-conditions",
        disjoint_contexts(base(["На ПК сохраняйте фильтры.", "На телефоне сбрасывайте фильтры."])),
        "checked",
        "D",
        "Явное разбиение desktop/mobile делает C непересекающимися.",
    )
    value = base(["Между сеансами сохраняйте фильтры.", "Мне также нужно сохранение фильтров."])
    value["proposal"]["atoms"][1]["values"] = boolean(True)
    add("03-compatible", value, "checked", "S", "Одинаковые условия и допустимое значение true.")
    add(
        "04-incomplete-information",
        unknown_context(),
        "checked",
        "U",
        "Полное Ω выбранной модели содержит D и K.",
    )
    value = base(
        ["Отклик должен занимать от 1 до 3 секунд.", "Время ответа должно быть от 5 до 10 секунд."]
    )
    model = value["proposal"]["model"]["formal_model"]
    model["parameter_id"] = "latency"
    model["domain"] = {
        "kind": "interval",
        "lower": "0",
        "upper": "20",
        "unit": "s",
        "dimension": "time",
    }
    for atom, bounds in zip(value["proposal"]["atoms"], ((1, 3), (5, 10)), strict=True):
        atom["parameter_id"] = "latency"
        atom["values"] = {
            "kind": "interval",
            "lower": str(bounds[0]),
            "upper": str(bounds[1]),
            "unit": "s",
        }
    value["proposal"]["decomposition_rationale"] = (
        "Куратор явно сопоставил «отклик» и «время ответа» одному параметру latency этой модели."
    )
    add(
        "05-parameter-aliases",
        value,
        "checked",
        "K",
        "Синонимия подготовлена явно и требует доверенного подтверждения.",
    )
    value = base()
    value["proposal"]["atoms"][1]["parameter_id"] = "autosubmit"
    add(
        "06-different-parameters",
        value,
        "rejected",
        None,
        "Разные параметры нельзя сравнивать в модели одного параметра.",
    )
    value = disjoint_contexts(
        base(
            [
                "На ПК сохраняйте фильтры, на телефоне сбрасывайте их.",
                "На ПК всегда сбрасывайте фильтры.",
            ]
        )
    )
    atoms = value["proposal"]["atoms"]
    atoms[1]["context_id"] = "desktop"
    extra = deepcopy(atoms[0])
    extra.update(id="a3", context_id="mobile", values=boolean(False))
    atoms.append(extra)
    value["proposal"]["decomposition_rationale"] = (
        "f1 явно разложена на два атома a1/a3; выбранная пара a1/a2 не проверяет a3."
    )
    add(
        "07-multiple-wishes",
        value,
        "checked",
        "K",
        "Одна находка даёт два атома с сохранённым exact основанием; "
        "проверяется только выбранная пара.",
    )
    value = base(["Фильтры каждый раз пропадают.", "Между сеансами сбрасывайте фильтры."])
    value["grouping_request"]["input"]["findings"][0]["mode"] = "inferred"
    value["proposal"]["origin"] = {
        "kind": "ai",
        "actor": "synthetic-proposer",
        "method": "saved_proposal_no_live_model",
    }
    add(
        "08-inferred-not-direct",
        value,
        "blocked",
        None,
        "AI-интерпретация потребности пока не подтверждена доверенным reviewer.",
        structure="K",
        formalization_confirmed=False,
    )
    value = disjoint_contexts(base())
    value["proposal"]["model"]["relations"][0]["relation"] = "overlap"
    add(
        "09-context-contradiction",
        value,
        "rejected",
        None,
        "Заявленные пересекающиеся контексты нельзя отобразить в непересекающиеся C.",
    )
    value = base(["Сохраняйте фильтры.", "Сохраняйте фильтры и у меня."])
    value["proposal"]["origin"]["kind"] = "ai"
    add(
        "10-false-K",
        value,
        "blocked",
        None,
        "Неверное false вместо true породило бы K; trusted review блокирует формализацию.",
        structure="K",
        formalization_confirmed=False,
    )
    value = disjoint_contexts(
        base(["На ПК сохраняйте фильтры.", "На настольном компьютере сбрасывайте фильтры."])
    )
    value["proposal"]["origin"]["kind"] = "ai"
    add(
        "11-false-D",
        value,
        "blocked",
        None,
        "PC и desktop ошибочно объявлены разными непересекающимися условиями; "
        "разбиение не подтверждено.",
        structure="D",
        contexts_confirmed=False,
    )
    value = unknown_context()
    value["proposal"]["omega"] = None
    add(
        "12-no-complete-omega",
        value,
        "needs_refinements",
        None,
        "Неизвестное C без полного явно заданного Ω не даёт U или другого класса.",
    )
    value = unknown_context()
    value["proposal"]["omega"]["variants"] = value["proposal"]["omega"]["variants"][:1]
    value["proposal"]["omega"]["origin"]["kind"] = "ai"
    add(
        "12b-AI-false-completeness",
        value,
        "blocked",
        None,
        "AI объявил единственный K-вариант полным; доверенный контур не подтверждает полноту.",
        structure="K",
        omega_complete_confirmed=False,
    )
    for pair in ((0, 1), (0, 2), (1, 2)):
        value = base(["Нужен режим a или b.", "Нужен режим b или c.", "Нужен режим a или c."])
        all_values = [["a", "b"], ["b", "c"], ["a", "c"]]
        value["grouping_response"]["result"]["groups"][0]["conflicts"] = []
        value["proposal"]["model"]["formal_model"]["domain"] = {
            "kind": "enum",
            "allowed": ["a", "b", "c"],
        }
        value["selection"].update(
            conflict=None,
            left_finding_keys=[f"f{pair[0] + 1}"],
            right_finding_keys=[f"f{pair[1] + 1}"],
        )
        for atom, index in zip(value["proposal"]["atoms"], pair, strict=True):
            atom["values"] = {"kind": "enum", "allowed": all_values[index]}
            atom["sources"] = [
                {
                    "finding_key": f"f{index + 1}",
                    "finding_ref": deepcopy(
                        value["grouping_request"]["input"]["findings"][index]["ref"]
                    ),
                    "evidence_keys": [f"e{index + 1}"],
                }
            ]
        add(
            "13-pair-" + "".join(str(i + 1) for i in pair),
            value,
            "checked",
            "S",
            "Попарный S не даёт совместимости тройки {a,b}, {b,c}, {a,c}.",
        )
    value = base()
    value["proposal"] = None
    add(
        "14-no-formalization",
        value,
        "needs_formalization",
        None,
        "Свободный текст не извлекается автоматически в переменные Z3.",
    )
    value = base(["Сохраняйте фильтры.", "Сбрасывайте фильтры.", "Мне тоже нужно сохранение."])
    value["grouping_response"]["result"]["groups"][0]["conflicts"][0]["positions"][0][
        "finding_keys"
    ].append("f3")
    value["selection"]["left_finding_keys"].append("f3")
    value["proposal"]["atoms"][0]["sources"].append(
        {
            "finding_key": "f3",
            "finding_ref": deepcopy(value["grouping_request"]["input"]["findings"][2]["ref"]),
            "evidence_keys": ["e3"],
        }
    )
    add(
        "15-multiple-position-findings",
        value,
        "checked",
        "K",
        "Ожидание левой позиции связано с обеими явно выбранными подтверждающими находками.",
    )
    value = base(
        [
            "В приватном режиме фильтры нельзя сохранять; в обычном режиме сохраняйте их.",
            "В приватном режиме сохраняйте фильтры.",
        ]
    )
    value["proposal"]["atoms"][0]["values"] = {"kind": "conditional", "depends_on": "context"}
    add(
        "16-dependent-constraint",
        value,
        "rejected",
        None,
        "Противоречие условий приватного режима и сохранения требует разбиения A(C) "
        "на атомарные случаи; условная SMT-формула этой версией не принимается.",
    )
    return cases


def synthetic_verifier(case_id: str):
    """Whitelist an exact curated fixture packet. No-op verifiers are not used."""
    if type(case_id) is not str:
        raise ValueError("Synthetic verifier requires a registered case id")
    case = next((c for c in catalog() if c["id"] == case_id), None)
    if case is None:
        raise ValueError("Unknown synthetic case id")
    expected = prepare(case["input"])
    if expected.status != "prepared":
        raise ValueError("Synthetic case has no prepared packet")
    saved = deepcopy(expected.packet)
    flags = dict.fromkeys(
        (
            "basis_verified",
            "formalization_confirmed",
            "comparability_confirmed",
            "contexts_confirmed",
            "omega_complete_confirmed",
        ),
        True,
    )
    flags.update(case["synthetic_confirmations"])

    def verify(packet):
        if packet != saved:
            raise ValueError("Synthetic snapshot mismatch")
        return Verification(
            fingerprint(saved),
            "synthetic-curator-registry-v1",
            "Exact curated synthetic snapshot; not a live project verification.",
            **flags,
        )

    return verify


def write_snapshots():
    root = Path(__file__).resolve().parent / "examples"
    root.mkdir(exist_ok=True)
    cases = catalog()
    (root / "cases.json").write_text(
        json.dumps(cases, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    # Preliminary review prompts, not labels computed from solver results.
    annotations = [
        {
            "case_id": c["id"],
            "status": "PRELIMINARY",
            "reviewer": None,
            "semantic_verdict": "pending",
            "review_prompt": c["explanation"],
            "not_semantic_gold": True,
        }
        for c in cases
    ]
    (root / "expert-review.json").write_text(
        json.dumps(annotations, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    write_snapshots()
