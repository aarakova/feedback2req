"""Malformed observation records never authorize even a process lookup or signal."""

import json

import pytest

from feedback2req.processing import worker


@pytest.mark.parametrize("record", [
    {"pid": 999999, "start": "1", "deadline": 1},
    {"pid": 999999, "start": "1", "deadline": 1, "ready": "true"},
    {"pid": 999999, "start": 1, "deadline": 1, "ready": True},
    {"pid": 999999, "start": "bad", "deadline": 1, "ready": True},
    {"pid": 999999, "start": "1", "deadline": 1, "ready": True, "extra": 1},
    [],
])
def test_corrupt_observation_cannot_authorize_signal(tmp_path, monkeypatch, record):
    state = tmp_path / "worker.json"
    state.write_text(json.dumps(record))
    monkeypatch.setattr(worker, "STATE", state)
    monkeypatch.setattr(worker, "LOCK", tmp_path / "worker.lock")
    lookups = []

    def forbidden(pid):
        lookups.append(pid)
        raise AssertionError("Corrupt metadata must be rejected before process lookup")

    monkeypatch.setattr(worker, "identity", forbidden)
    assert worker.probe() == 1
    assert lookups == []
