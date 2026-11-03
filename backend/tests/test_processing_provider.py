"""No real network: assert transmission gates, wire schema and strict JSON parsing."""

import json
from uuid import uuid4

import pytest
from jsonschema import Draft202012Validator

from feedback2req.config import Settings
from feedback2req.processing import provider, validation


def test_provider_requires_transmission_permission(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("No transport may be constructed without permission")

    monkeypatch.setattr(provider, "build_opener", forbidden)
    settings = Settings(database_url="postgresql+psycopg://synthetic.invalid/test", local_http=True)
    with pytest.raises(provider.ProviderError) as error:
        provider.Ollama(settings).extract({})
    assert error.value.code == "provider_not_configured"


def test_provider_uses_canonical_schema_without_network(monkeypatch):
    req = validation.request(uuid4(), uuid4(), uuid4(), uuid4(), "synthetic feedback")
    canonical = {
        "coverage": [{
            "input_key": "s1", "reviewed": True, "disposition": "completed",
            "reason": "No findings in synthetic response",
        }],
        "uncertainties": [], "questions": [],
        "result": {"fragments": [], "findings": []},
    }
    captured = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self, limit):
            assert limit == 262145
            envelope = {"done": True, "message": {"content": json.dumps(canonical)}}
            return json.dumps(envelope).encode()

    class Transport:
        def open(self, request, timeout):
            captured.update(json.loads(request.data))
            assert timeout <= 60
            return Response()

    monkeypatch.setattr(provider, "build_opener", lambda *args: Transport())
    settings = Settings(
        database_url="postgresql+psycopg://synthetic.invalid/test",
        local_http=True,
        ai_transfer_enabled=True,
        ai_provider_url="http://synthetic.invalid/api/chat",
        ai_model="synthetic-only",
        processing_test_mode=True,
    )
    assert provider.Ollama(settings).extract(req) == canonical
    assert captured["stream"] is False
    assert json.loads(captured["messages"][-1]["content"]) == req
    Draft202012Validator.check_schema(captured["format"])
    Draft202012Validator(captured["format"]).validate(canonical)
    assert "https://feedback2req.invalid/contracts/ai/v1/common.schema.json#" not in json.dumps(
        captured["format"]
    )


@pytest.mark.parametrize("raw", ['{"same":1,"same":2}', '{"value":NaN}', 'invalid'])
def test_duplicate_and_non_json_provider_payload_is_rejected(raw):
    with pytest.raises(validation.InvalidResponse):
        validation.decode(raw)
