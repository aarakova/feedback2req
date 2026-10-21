import importlib.util
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "url,project",
    [
        ("postgresql+psycopg://f2r_test@127.0.0.1:55433/feedback2req", "feedback2req-i1-test"),
        (
            "postgresql+psycopg://f2r_test@foreign.example:55433/feedback2req_i1_test",
            "feedback2req-i1-test",
        ),
        (
            "postgresql+psycopg://f2r_test@127.0.0.1:5432/feedback2req_i1_test",
            "feedback2req-i1-test",
        ),
        (
            "postgresql+psycopg://production@127.0.0.1:55433/feedback2req_i1_test",
            "feedback2req-i1-test",
        ),
        ("postgresql+psycopg://f2r_test@127.0.0.1:55433/feedback2req_i1_test", "feedback2req"),
        (
            "postgresql+psycopg://f2r_test@127.0.0.1:55433/feedback2req_i1_test",
            "feedback2req-ci-bad",
        ),
    ],
)
def test_restart_rejects_unsafe_target(monkeypatch, url, project):
    path = Path(__file__).parents[2] / "scripts" / "check_i1_restart.py"
    spec = importlib.util.spec_from_file_location("restart_safety", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setenv("F2R_TEST_DATABASE_URL", url)
    monkeypatch.setenv("F2R_TEST_COMPOSE_PROJECT", project)
    monkeypatch.setattr(sys, "argv", [str(path)])

    def forbidden(*args, **kwargs):
        pytest.fail("Unsafe targets must be rejected before any database/process access")

    monkeypatch.setattr(module, "create_engine", forbidden)
    monkeypatch.setattr(module, "run", forbidden)
    with pytest.raises(RuntimeError):
        module.main()
