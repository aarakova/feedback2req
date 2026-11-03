"""Explicit synthetic replay CLI; real adapters are configured by application code."""

import argparse
import json
import sys
from pathlib import Path

from .provider import Replay, read_json_bytes
from .service import group_findings
from .validation import GroupingError, decode


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", required=True)
    parser.add_argument("--synthetic-response", required=True)
    parser.add_argument("--output", required=True, help="New canonical JSON file")
    args = parser.parse_args(argv)
    try:
        request = decode(read_json_bytes(args.request, side="request"), side="request")
        response = read_json_bytes(args.synthetic_response)
        # Only the explicitly synthetic command bypasses a real state repository.
        candidate = group_findings(
            request, Replay(response), verify_context=lambda _: None
        )
        with Path(args.output).open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(candidate, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        print(
            "PASS synthetic_fixture_replay; model=none; semantic_quality=not_evaluated"
        )
        return 0
    except GroupingError as error:
        print(str(error), file=sys.stderr)
        return 2
    except Exception:  # noqa: BLE001 -- CLI diagnostics must exclude source text/paths.
        print("tool_error:output_or_configuration", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
