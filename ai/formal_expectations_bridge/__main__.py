"""Offline preparation or explicitly synthetic, exact-snapshot-verified demos."""

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from .compatibility import audit_saved_inputs
from .service import check_pair
from .synthetic import catalog, synthetic_verifier
from .validation import prepare


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("prepare").add_argument("input")
    audit = commands.add_parser(
        "audit", help="Mechanical supplied saved DTO comparison; no trust receipt"
    )
    audit.add_argument("input")
    audit.add_argument("--saved", required=True)
    commands.add_parser("demo").add_argument("case", choices=[c["id"] for c in catalog()])
    args = parser.parse_args(argv)
    if args.command in ("prepare", "audit"):
        try:
            with Path(args.input).open("rb") as stream:
                data = stream.read(1_048_577)
            if args.command == "audit":
                with Path(args.saved).open("rb") as stream:
                    saved = stream.read(1_048_577)
        except OSError:
            print(json.dumps({"status": "rejected", "diagnostic": {"code": "input_io"}}))
            return 2
        result = audit_saved_inputs(data, saved) if args.command == "audit" else prepare(data)
        print(json.dumps(asdict(result), ensure_ascii=True, sort_keys=True))
        return 0 if result.status in ("prepared", "matched") else 2
    case = next(c for c in catalog() if c["id"] == args.case)
    verification = (
        synthetic_verifier(case["id"]) if prepare(case["input"]).status == "prepared" else None
    )
    result = check_pair(case["input"], verify=verification)
    print(
        json.dumps(
            {"synthetic": True, "case_id": case["id"], "result": result.to_dict()},
            ensure_ascii=True,
            sort_keys=True,
        )
    )
    return 0 if result.status == "checked" else 2


if __name__ == "__main__":
    raise SystemExit(main())
