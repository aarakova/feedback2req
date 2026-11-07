"""Saved negative engineering proposals, never model observations or approvals."""

from copy import deepcopy
from pathlib import Path

from .dataset import dataset_hash, get_case
from .protocol import canonical, response_from_reference, sha
from .runner import SYNTHETIC_MODEL, write


def negative_controls():
    values = []

    def case(key):
        return response_from_reference(get_case(key))

    def add(label, value, expected):
        values.append(
            {
                "label": label,
                "case_id": value["case_id"],
                "raw": canonical(value),
                "expected": expected,
            }
        )

    value = case("B-05-parameter-aliases")
    value["formalization"]["atoms"][1]["parameter_id"] = "different_parameter"
    add("parameter-mismatch", value, "formalization_error")
    value = case("B-02-different-conditions")
    value["formalization"]["atoms"][1]["context_id"] = value["formalization"]["atoms"][0][
        "context_id"
    ]
    add("lost-condition", value, "review_required")
    value = case("B-05-parameter-aliases")
    value["formalization"]["atoms"][0]["values"]["lower"] = "2"
    add("invented-value", value, "review_required")
    value = case("B-11-false-D")
    bad = deepcopy(get_case("B-11-false-D")["input"]["proposal"])
    bad.pop("origin")
    value["formalization"] = bad
    add("wrong-disjoint-partition", value, "review_required")
    value = case("B-04-incomplete-information")
    value["formalization"]["omega"]["variants"] = value["formalization"]["omega"]["variants"][:1]
    add("incomplete-omega-claimed-complete", value, "review_required")
    value = case("B-15-multiple-position-findings")
    value["selection"]["left_finding_keys"] = ["f1"]
    add("first-position-member-only", value, "provenance_error")
    value = case("B-01-direct-conflict")
    value["formalization_confirmed"] = True
    add("self-approval", value, "structure_error")
    value = case("B-01-direct-conflict")
    value["formalization"]["atoms"][0]["sources"][0]["finding_ref"]["state_id"] = (
        "unselected-latest"
    )
    add("state-substitution", value, "provenance_error")
    values.append(
        {
            "label": "broken-json",
            "case_id": "B-01-direct-conflict",
            "raw": b'{"broken"',
            "expected": "syntax_error",
        }
    )
    return values


def generate(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    records, expectations = [], []
    for index, control in enumerate(negative_controls()):
        name = f"{index:03}.bin"
        (output / name).write_bytes(control["raw"])
        records.append(
            {
                "case_id": control["case_id"],
                "attempt": index + 2,
                "response_file": name,
                "response_sha256": sha(control["raw"]),
            }
        )
        expectations.append(
            {
                "case_id": control["case_id"],
                "attempt": index + 2,
                "label": control["label"],
                "expected_status": control["expected"],
            }
        )
    write(
        output / "manifest.json",
        {
            "experiment_version": "1",
            "mode": "synthetic_proposals",
            "dataset_sha256": dataset_hash(),
            "model": deepcopy(SYNTHETIC_MODEL),
            "records": records,
        },
    )
    write(
        output / "expectations.json",
        {"synthetic": True, "semantic_gold": False, "records": expectations},
    )
