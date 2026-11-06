"""Real standalone AI operation + synthetic transport + real PG/F2 publication."""

import json
import threading
from contextlib import contextmanager
from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from ai.group_findings.provider import Replay
from ai.group_findings.validation import GroupingError
from sqlalchemy import func, select

from feedback2req.errors import AppError
from feedback2req.grouping import execution
from feedback2req.persistence.grouping import FindingGroup
from feedback2req.persistence.models import FeedbackSource, SourceTextState
from feedback2req.persistence.processing import Attempt, Run, Unit
from feedback2req.processing import service

from .test_grouping import group_case as group_case
from .test_grouping import synthetic_response


class ScriptedReplay(Replay):
    def __init__(self, factory=None):
        super().__init__("")
        self.factory = factory or (lambda req: synthetic_response({"request": req}))
        self.calls = 0

    def group(self, value):
        self.calls += 1
        response = self.factory(value)
        self.response = (
            response if isinstance(response, str) else json.dumps(response, ensure_ascii=False)
        )
        return super().group(value)


def execute(app, client, case, provider, *, sessions=None, key=None, **kwargs):
    return execution.execute_grouping(
        sessions or app.state.sessions,
        app.state.identity,
        client.cookies.get(app.state.settings.session_cookie),
        case["project_id"],
        key or uuid4(),
        case["refs"],
        provider=provider,
        **kwargs,
    )


def change_source(app, case):
    with app.state.sessions.begin() as tx:
        header = tx.get(FeedbackSource, UUID(case["sources"][0]["id"]))
        state = SourceTextState(
            id=uuid4(),
            project_id=header.project_id,
            source_id=header.id,
            text="Изменённый источник",
            author_id=UUID(case["owner"]["id"]),
            origin="human",
        )
        tx.add(state)
        tx.flush()
        header.current_state_id = state.id


def test_component_f2_and_exact_http_read_roundtrip(client, app, group_case):
    provider = ScriptedReplay()
    receipt = execute(app, client, group_case, provider)
    assert receipt["result"]["state"] == "completed" and provider.calls == 1
    assert len(receipt["result"]["group_ids"]) == 2
    assert "owner_token" not in receipt and "request" not in receipt
    run = client.get(group_case["path"] + "/runs/" + str(receipt["run_id"])).json()
    attempt = run["units"][0]["attempt"]
    assert attempt["synthetic"] and attempt["ai_performed"] is False
    assert len(attempt["grouping_result"]["ungrouped_findings"]) == 1
    for identity in receipt["result"]["group_ids"]:
        detail = client.get(group_case["path"] + "/groups/" + str(identity)).json()
        assert detail["members"][0]["finding"]["evidence"][0]["source_ref"]["id"]


def test_component_ungrouped_without_extra_reason_is_published(client, app, group_case):
    def empty(req):
        keys = [f["key"] for f in req["input"]["findings"]]
        return {
            "coverage": [
                {"input_key": k, "reviewed": True, "disposition": "completed"} for k in keys
            ],
            "questions": [],
            "uncertainties": [],
            "result": {"groups": [], "ungrouped_finding_keys": keys},
        }

    receipt = execute(app, client, group_case, ScriptedReplay(empty))
    assert receipt["result"]["state"] == "completed"
    assert receipt["result"]["group_ids"] == []
    assert len(receipt["result"]["ungrouped_findings"]) == 3
    assert client.get(group_case["path"] + "/groups").json()["items"] == []


def test_context_change_before_compute_prevents_provider_call(client, app, group_case, monkeypatch):
    prepare = execution.prepare_grouping

    def changed_prepare(*args, **kwargs):
        handle = prepare(*args, **kwargs)
        change_source(app, group_case)
        return handle

    monkeypatch.setattr(execution, "prepare_grouping", changed_prepare)
    provider = ScriptedReplay()
    result = execute(app, client, group_case, provider)["result"]
    assert provider.calls == 0
    assert result["state"] == "cancelled" and result["reason_code"] == "input_changed"


def test_context_change_during_compute_prevents_publication(client, app, group_case):
    def changed(req):
        # A separate PG transaction succeeds: compute holds no project lock.
        change_source(app, group_case)
        return synthetic_response({"request": req})

    receipt = execute(app, client, group_case, ScriptedReplay(changed))
    assert receipt["result"]["reason_code"] == "input_changed"
    assert client.get(group_case["path"] + "/groups").json()["items"] == []


@pytest.mark.parametrize(
    "damage,expected",
    [
        ("json", "invalid_response"),
        ("coverage", "invalid_response"),
        ("duplicate_json", "invalid_response"),
        ("timeout", "provider_error"),
        ("not_configured", "provider_not_configured"),
        ("unsafe_exception", "provider_error"),
    ],
)
def test_component_failures_are_safe_attempt_outcomes(client, app, group_case, damage, expected):
    def broken(req):
        if damage == "json":
            return "{broken"
        if damage == "duplicate_json":
            return '{"coverage":[],"coverage":[]}'
        if damage == "timeout":
            raise TimeoutError("source text must never be persisted")
        if damage == "not_configured":
            raise GroupingError("provider_error", "provider_not_configured")
        if damage == "unsafe_exception":
            raise RuntimeError("source text must never be persisted")
        value = synthetic_response({"request": req})
        value["coverage"].pop()
        return value

    receipt = execute(app, client, group_case, ScriptedReplay(broken))
    assert receipt["result"]["state"] == "failed"
    assert receipt["result"]["reason_code"] == expected
    attempt = client.get(group_case["path"] + "/runs/" + str(receipt["run_id"])).json()["units"][0][
        "attempt"
    ]
    assert attempt["coverage"] is None and attempt["grouping_result"] is None
    assert "source text must never" not in str(attempt)
    with app.state.sessions() as tx:
        assert tx.scalar(select(func.count()).select_from(FindingGroup)) == 0


def test_unknown_publication_commit_never_reinvokes_provider(client, app, group_case):
    class Uncertain:
        @contextmanager
        def begin(self):
            with app.state.sessions.begin() as tx:
                yield tx
                completed = tx.scalar(
                    select(Attempt.id)
                    .join(Unit, Unit.id == Attempt.unit_id)
                    .join(Run, Run.id == Unit.run_id)
                    .where(Run.operation == "group_findings", Attempt.state == "completed")
                )
            if completed:
                raise ConnectionError("Lost final COMMIT acknowledgement")

    key, provider = uuid4(), ScriptedReplay()
    with pytest.raises(ConnectionError):
        execute(app, client, group_case, provider, sessions=Uncertain(), key=key)
    replay = execute(app, client, group_case, provider, key=key)
    assert replay["replayed"] and replay["result"]["state"] == "completed"
    assert provider.calls == 1


def test_unknown_prepare_commit_never_invokes_provider(client, app, group_case):
    class Uncertain:
        @contextmanager
        def begin(self):
            with app.state.sessions.begin() as tx:
                yield tx
            raise ConnectionError("Lost prepare COMMIT acknowledgement")

    key, provider = uuid4(), ScriptedReplay()
    with pytest.raises(ConnectionError):
        execute(app, client, group_case, provider, sessions=Uncertain(), key=key)
    replay = execute(app, client, group_case, provider, key=key)
    assert replay["replayed"] and replay["result"]["state"] == "running"
    assert provider.calls == 0


def test_heartbeat_renews_during_component_compute(client, app, group_case, monkeypatch):
    renewed = threading.Event()
    renew = execution.renew_grouping
    monkeypatch.setattr(execution, "HEARTBEAT_SECONDS", 0.02)

    def recording_renew(*args):
        value = renew(*args)
        if value:
            renewed.set()
        return value

    monkeypatch.setattr(execution, "renew_grouping", recording_renew)

    def slow(req):
        with app.state.sessions.begin() as tx:
            attempt = tx.scalar(
                select(Attempt).where(Attempt.request_id == UUID(req["request_id"]))
            )
            attempt.lease_expires_at = service.now(tx) + timedelta(seconds=0.5)
        renewed.clear()
        assert renewed.wait(timeout=3)
        with app.state.sessions() as tx:
            attempt = tx.scalar(
                select(Attempt).where(Attempt.request_id == UUID(req["request_id"]))
            )
            assert attempt.lease_expires_at > service.now(tx) + timedelta(seconds=1)
            assert attempt.lease_expires_at <= attempt.deadline_at
        return synthetic_response({"request": req})

    assert execute(app, client, group_case, ScriptedReplay(slow))["result"]["state"] == "completed"


def test_lost_lease_is_not_published(client, app, group_case, monkeypatch):
    lost = threading.Event()
    renew = execution.renew_grouping
    monkeypatch.setattr(execution, "HEARTBEAT_SECONDS", 0.02)

    def recording_renew(*args):
        value = renew(*args)
        if not value:
            lost.set()
        return value

    monkeypatch.setattr(execution, "renew_grouping", recording_renew)

    def expired(req):
        with app.state.sessions.begin() as tx:
            attempt = tx.scalar(
                select(Attempt).where(Attempt.request_id == UUID(req["request_id"]))
            )
            attempt.lease_expires_at = service.now(tx) - timedelta(seconds=1)
        assert lost.wait(timeout=3)
        return synthetic_response({"request": req})

    with pytest.raises(AppError) as caught:
        execute(app, client, group_case, ScriptedReplay(expired))
    assert caught.value.code == "attempt_not_owned"
    assert client.get(group_case["path"] + "/groups").json()["items"] == []
    service.recover_one(app.state.sessions)
    with app.state.sessions() as tx:
        result = tx.scalar(
            select(Attempt)
            .join(Unit, Unit.id == Attempt.unit_id)
            .join(Run, Run.id == Unit.run_id)
            .where(Run.operation == "group_findings")
        )
        assert result.state == "failed" and result.reason_code == "lease_expired"


@pytest.mark.parametrize("disposition", ["not_processed", "insufficient_information"])
def test_no_substantive_output_preserves_actual_coverage(client, app, group_case, disposition):
    def response(req):
        return {
            "coverage": [
                {
                    "input_key": f["key"],
                    "reviewed": disposition != "not_processed",
                    "disposition": disposition,
                    "reason": "Synthetic incomplete scope",
                }
                for f in req["input"]["findings"]
            ],
            "questions": [],
            "uncertainties": [],
            "result": {"groups": [], "ungrouped_finding_keys": []},
        }

    result = execute(app, client, group_case, ScriptedReplay(response))
    assert result["result"]["state"] == "completed"
    attempt = client.get(group_case["path"] + "/runs/" + str(result["run_id"])).json()["units"][0][
        "attempt"
    ]
    assert {v["disposition"] for v in attempt["coverage"]} == {disposition}
    assert attempt["grouping_result"]["group_ids"] == []


@pytest.mark.parametrize("previous_annotation", [None, "questions", "uncertainties"])
def test_previous_group_context_and_annotations_are_accepted(
    client, app, group_case, previous_annotation
):
    first = execute(app, client, group_case, ScriptedReplay())
    group_id = first["result"]["group_ids"][0]
    saved = client.get(group_case["path"] + "/groups/" + str(group_id)).json()

    def response(req):
        candidate = synthetic_response({"request": req})
        if previous_annotation:
            candidate[previous_annotation][0]["related"] = [
                {
                    "origin": "input",
                    "key": req["input"]["previous_groups"][0]["key"],
                }
            ]
        return candidate

    second = execute(
        app,
        client,
        group_case,
        ScriptedReplay(response),
        previous_group_refs=[
            {"id": str(group_id), "state_id": saved["state_id"]},
        ],
    )
    assert second["result"]["state"] == "completed"
    if previous_annotation:
        attempt = client.get(group_case["path"] + "/runs/" + str(second["run_id"])).json()["units"][
            0
        ]["attempt"]
        assert attempt["annotations"][previous_annotation][0]["related"] == [
            {
                "origin": "input",
                "key": "g1",
                "kind": "finding_group",
                "id": str(group_id),
                "state_id": saved["state_id"],
            }
        ]
    assert client.get(group_case["path"] + "/groups/" + str(group_id)).json() == saved
