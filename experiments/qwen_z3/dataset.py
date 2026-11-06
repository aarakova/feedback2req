"""Independent engineering reference structures and source applicability.

No saved model response is used to build these preliminary references.
"""

import json
from copy import deepcopy
from pathlib import Path

from ai.formal_expectations_bridge.synthetic import base, unknown_context
from ai.formal_expectations_bridge.synthetic import catalog as bridge_catalog

from .protocol import fingerprint, input_hash, input_view

ROOT = Path(__file__).resolve().parents[2]
DATA = Path(__file__).with_name("data")
QUESTIONS = [
    "Все ли пожелания разложены на атомы без потери условий?",
    "Совпадают ли объект и параметр по смыслу, а не только по названию?",
    "Есть ли для каждого известного C/A точное доступное основание?",
    "Не выдуманы ли значения и не скрыты ли неизвестные сведения?",
    "Сохранены ли все находки выбранных позиций либо явные причины исключения?",
    "Обоснованы ли атомарное разбиение и полнота Ω относительно выбранной модели?",
]


def load_cases():
    cases = []
    for item in bridge_catalog():
        source, reference = deepcopy(item["input"]), deepcopy(item["input"])
        expected = item["expected_structural_class"]
        key = item["id"]
        if key == "10-false-K":
            reference["proposal"]["atoms"][1]["values"]["allowed"] = [True]
            expected = "S"
        elif key == "11-false-D":
            reference["proposal"]["model"] = deepcopy(base()["proposal"]["model"])
            for atom in reference["proposal"]["atoms"]:
                atom["context_id"] = "between_sessions"
            expected = "K"
        elif key == "09-context-contradiction":
            reference["proposal"]["model"] = deepcopy(base()["proposal"]["model"])
            for atom in reference["proposal"]["atoms"]:
                atom["context_id"] = "between_sessions"
            expected = "K"
        elif key == "12b-AI-false-completeness":
            reference["proposal"]["omega"] = deepcopy(unknown_context()["proposal"]["omega"])
            expected = "U"
        elif key == "14-no-formalization":
            reference["proposal"] = deepcopy(base()["proposal"])
            expected = "K"
        elif key in ("06-different-parameters", "16-dependent-constraint"):
            reference, expected = None, None
        elif key == "12-no-complete-omega":
            expected = None
        # These are research reference drafts, not retrospective claims of approval.
        cases.append(
            {
                "id": "B-" + key,
                "source": {"kind": "bridge_catalog", "id": key},
                "input": source,
                "reference": reference,
                "expected_formal_class": expected,
                "reference_status": "PRELIMINARY_ENGINEERING_CONTROL",
                "abstention_reason": (
                    "Без доверенного подтверждения структуры/оснований/Ω заключение запрещено. "
                    + item["explanation"]
                ),
                "expert_questions": deepcopy(QUESTIONS),
            }
        )
    for case_id in ("S05", "S06"):
        source_file = ROOT / f"evals/ai/datasets/synthetic-ru-v1/cases/{case_id}.json"
        source = json.loads(source_file.read_text("utf-8"))
        for example in source["examples"]:
            if example["request"]["operation"] != "group_findings":
                continue
            data = base()
            data["grouping_request"] = deepcopy(example["request"])
            data["grouping_response"] = deepcopy(example["fixture_response"])
            data["selection"]["conflict"] = None
            context_id = "list_reopened" if case_id == "S05" else "default_settings"
            model = data["proposal"]["model"]
            model["formal_model"]["situations"] = [context_id]
            model["contexts"] = [{"id": context_id, "situations": [context_id]}]
            model["rationale"] = "Явная исследовательская модель исходного условия " + context_id
            findings = data["grouping_request"]["input"]["findings"]
            for index, atom in enumerate(data["proposal"]["atoms"]):
                atom["context_id"] = context_id
                atom["sources"] = [
                    {
                        "finding_key": findings[index]["key"],
                        "finding_ref": deepcopy(findings[index]["ref"]),
                        "evidence_keys": [
                            v["fragment_key"]
                            for v in findings[index]["evidence"]
                            if v["kind"] == "available"
                        ],
                    }
                ]
                atom["values"]["allowed"] = [True if case_id == "S05" else index == 0]
            if case_id == "S06":
                formal = data["proposal"]["model"]["formal_model"]
                formal.update(object_id="status_notifications", parameter_id="sound_by_default")
                for atom in data["proposal"]["atoms"]:
                    atom.update(object_id=formal["object_id"], parameter_id=formal["parameter_id"])
            cases.append(
                {
                    "id": case_id + "-" + example["id"],
                    "source": {
                        "kind": "synthetic-ru-v1",
                        "case": case_id,
                        "example": example["id"],
                        "source_sha256": fingerprint(source),
                    },
                    "input": deepcopy(data),
                    "reference": deepcopy(data),
                    "expected_formal_class": "S" if case_id == "S05" else "K",
                    "reference_status": "PRELIMINARY_ENGINEERING_CONTROL",
                    "abstention_reason": (
                        "Предварительная разметка S01–S14 не заменяет доверенный смысловой review."
                    ),
                    "expert_questions": deepcopy(QUESTIONS)
                    + source["annotation"].get("expert_questions", []),
                }
            )
    return cases


def applicability():
    result = []
    for file in sorted((ROOT / "evals/ai/datasets/synthetic-ru-v1/cases").glob("S*.json")):
        source = json.loads(file.read_text("utf-8"))
        examples = [
            e["id"] for e in source["examples"] if e["request"]["operation"] == "group_findings"
        ]
        result.append(
            {
                "case_id": source["id"],
                "source_sha256": fingerprint(source),
                "applicable_examples": examples,
                "status": "included" if examples else "no_canonical_grouping_pair",
                "reason": (
                    "Прочие операции не преобразуются в группу "
                    "и не создают вымышленные Finding states."
                ),
            }
        )
    return result


def dataset_hash():
    return fingerprint({"cases": load_cases(), "applicability": applicability()})


def get_case(case_id):
    matches = [c for c in load_cases() if c["id"] == case_id]
    if not matches:
        raise ValueError("Unknown registered case")
    return deepcopy(matches[0])


def export(path):
    """New directory only. Export source inputs and references separately."""
    path.mkdir(parents=True, exist_ok=False)
    from .prompt import task

    (path / "tasks").mkdir()
    files = {
        "inputs.json": {
            "dataset_sha256": dataset_hash(),
            "cases": [input_view(c) | {"input_sha256": input_hash(c)} for c in load_cases()],
        },
        "references.json": {
            "dataset_sha256": dataset_hash(),
            "semantic_gold": False,
            "cases": load_cases(),
        },
        "applicability.json": applicability(),
    }
    for name, value in files.items():
        with (path / name).open("x", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
    for case in load_cases():
        with (path / "tasks" / (case["id"] + ".json")).open("x", encoding="utf-8") as stream:
            json.dump(task(case), stream, ensure_ascii=False, indent=2)
            stream.write("\n")
