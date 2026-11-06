"""Use only versioned repository synthetic cases; no arbitrary input-file option."""

import sys
from copy import deepcopy
from pathlib import Path

from ai.group_findings.validation import validate_request
from evals.ai.grouping.build_cases import make_request

from .adapter import sha

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "evals/ai"))
from runner import DEFAULT_DATASET, Dataset


def load_cases():
    dataset = Dataset(DEFAULT_DATASET)
    cases, applicability = [], {}
    for case_id, case in dataset.cases.items():
        applicable = [
            e["id"]
            for e in case["examples"]
            if e["request"]["operation"] == "group_findings"
        ]
        applicability[case_id] = {
            "group_findings_examples": applicable,
            "status": "applicable" if applicable else "no_group_findings_request",
            "other_operations": sorted(
                {e["request"]["operation"] for e in case["examples"]}
                - {"group_findings"}
            ),
        }
        for example_id in applicable:
            example = dataset.examples[(case_id, example_id)]
            cases.append(
                {
                    "id": case_id + "-" + example_id,
                    "request": example["request"],
                    "annotation": case["annotation"],
                    "source": [case_id, example_id],
                    "trusted": example["trusted"],
                    "relationship": None,
                }
            )
    path = ROOT / "evals/ai/grouping/cases.json"
    import json

    controls = json.loads(path.read_text("utf-8"))
    for case in controls["cases"]:
        cases.append(
            {
                "id": "G-" + case["id"],
                "request": case["request"],
                "annotation": {
                    "status": "preliminary",
                    "review_focus": case["review_focus"],
                },
                "source": None,
                "trusted": None,
                "relationship": None,
            }
        )
    request = make_request(
        [
            "После повторного открытия списка заново выставляю фильтры.",
            "Нужно сохранять выбранные фильтры после повторного открытия списка.",
        ]
    )
    request["input"]["findings"][0].update(
        mode="inferred",
        types=["need"],
        uncertainty_notes=["Потребность выведена из описания повторной настройки."],
    )
    request["input"]["fragments"][0]["reliability"] = "uncertain"
    cases.append(
        {
            "id": "G-direct-inferred-uncertain",
            "request": request,
            "source": None,
            "trusted": None,
            "relationship": None,
            "annotation": {
                "status": "preliminary",
                "review_focus": "Сохранить inferred и uncertain; не повышать достоверность и не приписывать прямую просьбу первой находке.",
            },
        }
    )
    lost = deepcopy(request)
    lost["input"]["findings"][0]["evidence"] = [
        {"kind": "deleted_source", "source_id": "SRC1"}
    ]
    # Use the actual synthetic source ID; no deleted fragment is retained.
    lost["input"]["findings"][0]["evidence"][0]["source_id"] = lost["input"][
        "fragments"
    ][0]["source_ref"]["id"]
    lost["input"]["fragments"] = lost["input"]["fragments"][1:]
    cases.append(
        {
            "id": "G-deleted-evidence",
            "request": lost,
            "source": None,
            "trusted": None,
            "relationship": None,
            "annotation": {
                "status": "preliminary",
                "review_focus": "Удалённое основание не восстанавливать; пересказ не становится доступной цитатой.",
            },
        }
    )
    for case in list(cases):
        if len(case["request"]["input"]["findings"]) > 1:
            variant = deepcopy(case)
            variant.update(
                id=case["id"] + "-reversed",
                source=None,
                relationship={"kind": "permutation", "of": case["id"]},
            )
            for field in ("findings", "fragments", "documents"):
                variant["request"]["input"][field].reverse()
            cases.append(variant)
    base = next(c for c in cases if c["id"] == "G-compatible")
    variant = deepcopy(base)
    variant.update(
        id="G-compatible-paraphrase",
        source=None,
        relationship={"kind": "paraphrase", "of": base["id"]},
    )
    for finding, text in zip(
        variant["request"]["input"]["findings"],
        [
            "Мне нужны извещения о состоянии заявки.",
            "Хочу знать, что обработка заявки завершилась.",
        ],
        strict=True,
    ):
        finding["text"] = text
    cases.append(variant)
    for case in cases:
        validate_request(case["request"])
        case["request_sha256"] = sha(case["request"])
    return dataset, cases, applicability
