"""Read one bounded JSON request and print one safe JSON result."""

import argparse
import json
import sys
from dataclasses import fields
from pathlib import Path

from . import Limits, analyze
from .diagnostics import ErrorCode
from .model import Analysis, Diagnostic


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="JSON file, or - for stdin")
    for field in fields(Limits):
        parser.add_argument(f"--{field.name.replace('_', '-')}", type=int, default=field.default)
    args = parser.parse_args(argv)
    try:
        limits = Limits(**{field.name: getattr(args, field.name) for field in fields(Limits)})
    except ValueError as error:
        parser.error(str(error))
    try:
        if args.input == "-":
            raw = sys.stdin.buffer.read(limits.max_input_bytes + 1)
        else:
            with Path(args.input).open("rb") as stream:
                raw = stream.read(limits.max_input_bytes + 1)
        result = analyze(raw, limits=limits)
    except OSError:
        result = Analysis(
            "failed",
            None,
            False,
            0,
            None,
            (),
            (),
            "Input could not be read.",
            Diagnostic(ErrorCode.INVALID_INPUT, "input_io"),
        )
    print(json.dumps(result.to_dict(), ensure_ascii=True, sort_keys=True))
    return 0 if result.status == "classified" else 2


if __name__ == "__main__":
    raise SystemExit(main())
