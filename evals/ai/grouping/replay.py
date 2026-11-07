"""Exercise the new component, then feed its S05/S06 results to the existing runner."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "evals/ai"))

from checks import InputError, check_request, strict_load
from runner import DEFAULT_DATASET, Dataset, digest, evaluate, write_report

from ai.group_findings import group_findings
from ai.group_findings.prompt import PROMPT_VERSION
from ai.group_findings.provider import Replay


def replay(output):
    dataset = Dataset(DEFAULT_DATASET)
    records = []
    for (case_id, example_id), example in dataset.examples.items():
        if example["request"]["operation"] != "group_findings":
            continue

        def verify(request, trusted=example["trusted"]):
            if check_request(dataset.contracts, request, trusted):
                raise InputError("TRUSTED-CONTEXT")

        candidate = group_findings(
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
            "adapter_version": "synthetic-replay-1.0.0",
            "generation_settings": {},
            "seed": None,
        },
        "records": records,
    }
    # Existing reports must never be overwritten.
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    replay_path = output / "replay.json"
    replay_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    report, template = evaluate(dataset, replay_path)
    write_report(report, template, output / "evaluation")
    controls = strict_load(Path(__file__).with_name("cases.json"))
    for case in controls["cases"]:
        group_findings(
            case["request"],
            Replay(json.dumps(case["response"], ensure_ascii=False)),
            verify_context=lambda _: None,
        )
    summary = {
        "mode": "synthetic_fixture_replay",
        "model": "none",
        "additional_controls": len(controls["cases"]),
        "existing_grouping_records": len(records),
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
    except Exception:  # noqa: BLE001 -- never print fixture/model contents on failure.
        print("grouping_replay_error", file=sys.stderr)
        raise SystemExit(2) from None
