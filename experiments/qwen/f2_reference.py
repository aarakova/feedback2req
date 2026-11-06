"""Verify the published F2 files without copying them into application sources."""

import hashlib
import json
from pathlib import Path


def verify_reference(root):
    expected = json.loads(
        Path(__file__).with_name("f2-reference.json").read_text("utf-8")
    )
    root = Path(root).resolve()
    for name, digest in expected["sha256"].items():
        if hashlib.sha256((root / name).read_bytes()).hexdigest() != digest:
            raise ValueError("f2_reference_hash_mismatch")
    return expected["commit"]
