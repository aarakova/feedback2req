"""Run synthetic generation through the component and the existing S01–S14 runner."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "evals/ai"))

from checks import InputError, check_request, strict_load
from runner import (
    DEFAULT_DATASET,
    MANUAL_CRITERIA,
    Dataset,
    digest,
    evaluate,
    write_report,
)

from ai.generate_requirements import generate_requirements
from ai.generate_requirements.prompt import PROMPT_VERSION
from ai.generate_requirements.provider import Replay


def replay(output):
    dataset = Dataset(DEFAULT_DATASET)
    records = []
    for (case_id, example_id), example in dataset.examples.items():
        if example["request"]["operation"] != "generate_requirements":
            continue

        def verify(request, trusted=example["trusted"]):
            if check_request(dataset.contracts, request, trusted):
                raise InputError("TRUSTED-CONTEXT")

        candidate = generate_requirements(
            example["request"],
            Replay(json.dumps(example["fixture_response"], ensure_ascii=False)),
            verify_context=verify,
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
            "adapter_version": "generate-replay-1.0.0",
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
    additional = strict_load(Path(__file__).with_name("cases.json"))
    reviews = []
    for case in additional["controls"] + additional["semantic_counterexamples"]:
        candidate = generate_requirements(
            case["request"],
            Replay(json.dumps(case["response"], ensure_ascii=False)),
            verify_context=lambda _: None,
        )
        reviews.append(
            {
                "case_id": case["id"],
                "fixture_role": case["fixture_role"],
                "request_sha256": digest(case["request"]),
                "response_sha256": digest(candidate),
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
        "existing_generation_records": len(records),
        "additional_controls": len(additional["controls"]),
        "semantic_counterexamples": len(additional["semantic_counterexamples"]),
        "technical_diagnostics": sum(
            len(row["automatic"]["diagnostics"]) for row in report["records"]
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
    except Exception:  # noqa: BLE001 -- do not expose model/fixture content on failure.
        print("generation_replay_error", file=sys.stderr)
        raise SystemExit(2) from None
