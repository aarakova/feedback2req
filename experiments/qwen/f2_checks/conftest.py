"""Load unchanged test fixtures from an explicitly pinned external F2 snapshot."""

from pathlib import Path

import backend.tests
from experiments.qwen.f2_reference import verify_reference

verify_reference(Path(backend.tests.__file__).resolve().parents[2])

pytest_plugins = ["backend.tests.conftest"]
