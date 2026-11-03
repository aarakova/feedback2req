#!/usr/bin/env python3
"""Offline AI diagnostics. Exit 0: no implemented violations; 1: diagnostics; 2: input/tool error."""

from __future__ import annotations

import argparse
import sys

from checks import InputError, strict_load
from runner import (
    DEFAULT_DATASET,
    Dataset,
    compare_reports,
    evaluate,
    write_comparison,
    write_report,
)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET))
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("validate-dataset")
    replay = commands.add_parser("replay")
    replay.add_argument(
        "--input", required=True, help="Local replay JSON; no network access"
    )
    replay.add_argument(
        "--output", required=True, help="New report directory; never overwrite"
    )
    replay.add_argument("--expert", help="Optional completed preliminary expert review")
    compare = commands.add_parser("compare")
    compare.add_argument("--left", required=True)
    compare.add_argument("--right", required=True)
    compare.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "compare":
            comparison = compare_reports(
                strict_load(args.left), strict_load(args.right)
            )
            write_comparison(comparison, args.output)
            print("COMPARED compatible diagnostic reports; NO MODEL RANKING")
            return 0
        dataset = Dataset(args.dataset)
        if args.command == "validate-dataset":
            print(
                f"PASS {len(dataset.cases)} synthetic scenarios; {len(dataset.examples)} examples; annotations PRELIMINARY"
            )
            print("Dataset SHA256 " + dataset.sha256)
            return 0
        report, template = evaluate(dataset, args.input, args.expert)
        write_report(report, template, args.output)
        print(
            f"REPLAY {report['summary']['records']} records; {report['summary']['expert_pending']} expert reviews pending; annotations PRELIMINARY"
        )
        print("NO FINAL MODEL QUALITY ASSESSMENT")
        return int(any(row["automatic"]["diagnostics"] for row in report["records"]))
    except InputError as error:
        print("INPUT ERROR: " + str(error), file=sys.stderr)
        return 2
    except Exception:  # noqa: BLE001 -- CLI boundary must not expose response contents in exceptions.
        # Exception strings can include user text, paths or response contents.
        print(
            "TOOL ERROR: unexpected failure; no successful check claimed",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
