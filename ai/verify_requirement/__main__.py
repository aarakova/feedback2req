"""Explicit synthetic verification replay. No real model or automatic fallback."""

import argparse
import json
import sys
from pathlib import Path

from .provider import Replay, read_json_bytes
from .service import verify_requirement
from .validation import ReviewPlan, VerificationError, decode


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", required=True)
    parser.add_argument("--synthetic-response", required=True)
    parser.add_argument("--output", required=True, help="New canonical JSON file")
    parser.add_argument(
        "--synthetic-plan",
        help="Optional synthetic executor metadata, never model output",
    )
    args = parser.parse_args(argv)
    try:
        request = decode(read_json_bytes(args.request, side="request"), side="request")
        plan = None
        if args.synthetic_plan:
            raw = decode(
                read_json_bytes(args.synthetic_plan, side="request"), side="request"
            )
            if (
                not isinstance(raw, dict)
                or set(raw) != {"checked_assessments", "comparison_keys"}
                or any(
                    not isinstance(v, list)
                    or any(not isinstance(k, str) for k in v)
                    or len(v) != len(set(v))
                    for v in raw.values()
                )
            ):
                raise VerificationError("invalid_request", "synthetic_plan")
            plan = ReviewPlan(
                frozenset(raw["checked_assessments"]), frozenset(raw["comparison_keys"])
            )
        candidate = verify_requirement(
            request,
            Replay(read_json_bytes(args.synthetic_response)),
            verify_context=lambda _: None,
            review_plan=plan,
        )
        with Path(args.output).open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(candidate, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        print(
            "PASS synthetic_fixture_replay; model=none; semantic_quality=not_evaluated"
        )
        return 0
    except VerificationError as error:
        print(str(error), file=sys.stderr)
        return 2
    except Exception:  # noqa: BLE001 -- CLI diagnostics must exclude source/response text.
        print("tool_error:output_or_configuration", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
