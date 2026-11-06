"""Exercise verification on S01–S14 and additional synthetic controls."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "evals/ai"))

from checks import InputError, check_request
from runner import (
    DEFAULT_DATASET,
    MANUAL_CRITERIA,
    Dataset,
    digest,
    evaluate,
    write_report,
)

from ai.verify_requirement import ReviewPlan, verify_requirement
from ai.verify_requirement.prompt import PROMPT_VERSION
from ai.verify_requirement.provider import Replay
from evals.ai.verification.build_cases import cases, plan_for, semantic_counterexamples


def execution_plan(value):
    return (
        None
        if value is None
        else ReviewPlan(
            frozenset(value["checked_assessments"]), frozenset(value["comparison_keys"])
        )
    )


def replay(output):
    dataset = Dataset(DEFAULT_DATASET)
    records = []
    for (case_id, example_id), example in dataset.examples.items():
        if example["request"]["operation"] != "verify_requirement":
            continue

        def verify(request, trusted=example["trusted"]):
            if check_request(dataset.contracts, request, trusted):
                raise InputError("TRUSTED-CONTEXT")

        candidate = verify_requirement(
            example["request"],
            Replay(json.dumps(example["fixture_response"], ensure_ascii=False)),
            verify_context=verify,
            review_plan=execution_plan(plan_for(case_id, example_id)),
        )
        records.append(
            {
                "case_id": case_id,
                "example_id": example_id,
                "outcome": "returned",
                "request_sha256": digest(example["request"]),
                "response": candidate,
            }
        )
    metadata = {
        "format_version": "1.0",
        "dataset_version": dataset.manifest["dataset_version"],
        "annotation_version": dataset.manifest["annotation_version"],
        "dataset_sha256": dataset.sha256,
        "mode": "synthetic_fixture_replay",
        "model": {"name": "none", "revision": "not_applicable"},
        "configuration": {
            "prompt_version": PROMPT_VERSION,
            "adapter_version": "verify-replay-1.0.0",
            "generation_settings": {},
            "seed": None,
        },
        "records": records,
    }
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    replay_path = output / "replay.json"
    replay_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    report, template = evaluate(dataset, replay_path)
    write_report(report, template, output / "evaluation")
    controls, counterexamples = cases(), semantic_counterexamples()
    reviews = []
    for row in controls + counterexamples:
        candidate = verify_requirement(
            row["request"],
            Replay(json.dumps(row["response"], ensure_ascii=False)),
            verify_context=lambda _: None,
            review_plan=execution_plan(row["review_plan"]),
        )
        reviews.append(
            {
                "case_id": row["id"],
                "fixture_role": row["fixture_role"],
                "request_sha256": digest(row["request"]),
                "response_sha256": digest(candidate),
                "review_plan": row["review_plan"],
                "annotation_status": "preliminary",
                "expert_status": "pending",
                "criteria": {name: {"status": "pending"} for name in MANUAL_CRITERIA},
            }
        )
    (output / "additional-review.json").write_text(
        json.dumps(reviews, indent=2) + "\n", encoding="utf-8"
    )
    summary = {
        "mode": "synthetic_fixture_replay",
        "model": "none",
        "existing_verification_records": len(records),
        "additional_controls": len(controls),
        "semantic_counterexamples": len(counterexamples),
        "technical_diagnostics": sum(
            len(r["automatic"]["diagnostics"]) for r in report["records"]
        ),
        "semantic_quality": "not_evaluated",
        "annotation_status": "preliminary",
    }
    (output / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary))
    return int(summary["technical_diagnostics"] > 0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        raise SystemExit(replay(args.output))
    except Exception:  # noqa: BLE001 -- diagnostics must not expose model or source text.
        print("verification_replay_error", file=sys.stderr)
        raise SystemExit(2) from None
