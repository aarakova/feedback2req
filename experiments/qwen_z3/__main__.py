"""Offline experimental CLI. No option calls a model or changes production data."""

import argparse
import json
from pathlib import Path

from .dataset import applicability, dataset_hash, export, load_cases
from .protocol import ExperimentError
from .runner import collect, generate_synthetic, replay


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("inventory")
    commands.add_parser("export").add_argument("--output", required=True)
    commands.add_parser("synthetic").add_argument("--output", required=True)
    commands.add_parser("negative-controls").add_argument("--output", required=True)
    pack = commands.add_parser("collect")
    pack.add_argument("--responses", required=True)
    pack.add_argument("--model", required=True)
    pack.add_argument("--output", required=True)
    pack.add_argument("--case", action="append", required=True)
    pack.add_argument("--attempt", type=int, default=1)
    run = commands.add_parser("replay")
    run.add_argument("--manifest", required=True)
    run.add_argument("--output", required=True)
    run.add_argument(
        "--reviews", help="Separately selected human review registry, never model output"
    )
    args = parser.parse_args(argv)
    try:
        if args.command == "inventory":
            print(
                json.dumps(
                    {
                        "cases": len(load_cases()),
                        "dataset_sha256": dataset_hash(),
                        "applicability": applicability(),
                    },
                    ensure_ascii=False,
                )
            )
        elif args.command == "export":
            export(Path(args.output))
        elif args.command == "synthetic":
            generate_synthetic(args.output)
        elif args.command == "negative-controls":
            from .controls import generate

            generate(args.output)
        elif args.command == "collect":
            collect(
                args.responses, args.model, args.output, case_ids=args.case, attempt=args.attempt
            )
        else:
            report = replay(args.manifest, args.output, reviews_path=args.reviews)
            print(json.dumps(report["summary"], ensure_ascii=False))
            return (
                0
                if all(
                    r["status"] in ("formal_conclusion", "model_abstained")
                    for r in report["records"]
                )
                else 1
            )
        return 0
    except ExperimentError as error:
        print(json.dumps({"category": error.category, "rule": error.rule}))
    except (OSError, ValueError):
        print(json.dumps({"category": "input_error", "rule": "file_or_configuration"}))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
