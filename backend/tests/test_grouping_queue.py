"""F3: real PG queue, actual worker child processes and existing HTTP reads."""

import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select

from feedback2req.errors import AppError
from feedback2req.grouping import queue
from feedback2req.grouping.provider import UnconfiguredGrouping
from feedback2req.grouping.service import enqueue_grouping
from feedback2req.persistence.grouping import FindingGroup
from feedback2req.persistence.models import DocumentState, ProjectAccess
from feedback2req.persistence.processing import Attempt, Run, Unit
from feedback2req.processing import service

from .conftest import signin, signup
from .test_grouping import accept, prepare, run, synthetic_response
from .test_grouping import group_case as group_case
from .test_grouping_execution import ScriptedReplay, change_source, execute
from .test_grouping_previous_annotations import advance_group


def enqueue(app, client, case, *, sessions=None, key=None, **kwargs):
    return enqueue_grouping(
        sessions or app.state.sessions,
        app.state.identity,
        client.cookies.get(app.state.settings.session_cookie),
        case["project_id"],
        key or uuid4(),
        kwargs.pop("finding_refs", case["refs"]),
        **kwargs,
    )


def worker_env(database_url, scenario):
    env = dict(os.environ, F2R_DATABASE_URL=database_url, F2R_LOCAL_HTTP="true")
    env.pop("F2R_GROUPING_SYNTHETIC_SCENARIO", None)
    if scenario is not None:
        env["F2R_GROUPING_SYNTHETIC_SCENARIO"] = scenario
    return env


def worker(database_url, scenario="one"):
    result = subprocess.run(
        [sys.executable, "-B", "-m", "feedback2req.processing.worker", "--once"],
        env=worker_env(database_url, scenario),
        capture_output=True,
        text=True,
        timeout=25,
    )
    assert result.returncode == 0, result.stderr
    return result


@pytest.mark.parametrize(
    "scenario,groups,reason",
    [
        ("one", 1, None),
        ("many", 2, None),
        ("ungrouped", 0, None),
        ("invalid", 0, "invalid_response"),
        ("error", 0, "provider_error"),
        (None, 0, "provider_not_configured"),
    ],
)
def test_real_worker_roundtrip(client, app, database_url, group_case, scenario, groups, reason):
    key = uuid4()
    handle = enqueue(app, client, group_case, key=key)
    queued = run(client, group_case, handle)
    assert queued["state"] == "queued" and queued["units"][0]["attempt"] is None
    assert len(queued["units"][0]["input"]["findings"]) == 3
    assert not any(handle[k] for k in ("attempt_id", "request", "owner_token"))
    worker(database_url, scenario)
    receipt = run(client, group_case, handle)
    attempt = receipt["units"][0]["attempt"]
    assert receipt["state"] == ("failed" if reason else "completed")
    assert attempt["reason_code"] == reason
    assert attempt["synthetic"] is (scenario is not None)
    assert attempt["ai_performed"] is False
    items = client.get(group_case["path"] + "/groups").json()["items"]
    assert len(items) == groups
    if groups:
        detail = next(
            d
            for d in [client.get(group_case["path"] + "/groups/" + g["id"]).json() for g in items]
            if d["conflicts"]
        )
        assert len(detail["conflicts"][0]["positions"]) == 2
        assert detail["members"][0]["finding"]["evidence"][0]["source_ref"]["id"]
    elif not reason:
        assert len(attempt["grouping_result"]["ungrouped_findings"]) == 3
    assert enqueue(app, client, group_case, key=key)["replayed"]
    worker(database_url, scenario)  # A new process sees no queued work.
    assert run(client, group_case, handle) == receipt
    # The public command has deliberately not been expanded.
    assert (
        client.post(
            group_case["path"] + "/runs",
            headers={"Idempotency-Key": str(uuid4())},
            json={"operation": "group_findings", "inputs": []},
        ).status_code
        == 422
    )


def test_two_worker_processes_claim_only_once(client, app, database_url, group_case):
    handle = enqueue(app, client, group_case)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: worker(database_url), range(2)))
    assert len(results) == 2
    with app.state.sessions() as tx:
        assert (
            tx.scalar(
                select(func.count())
                .select_from(Attempt)
                .where(Attempt.unit_id == handle["unit_id"])
            )
            == 1
        )
        assert tx.scalar(select(func.count()).select_from(FindingGroup)) == 1
    assert run(client, group_case, handle)["state"] == "completed"


@pytest.mark.parametrize("when", ["before", "during"])
def test_access_revocation(client, app, group_case, when):
    member = signup(client, "f3-member")
    client.put(group_case["path"] + "/access/" + member["id"], json={"can_approve": False})
    signin(client, "f3-member")
    handle = enqueue(app, client, group_case)

    def revoke():
        with app.state.sessions.begin() as tx:
            tx.delete(tx.get(ProjectAccess, (group_case["project_id"], UUID(member["id"]))))

    def candidate(req):
        revoke()  # Separate PG transaction proves no project lock is held during inference.
        return synthetic_response({"request": req})

    provider = ScriptedReplay(candidate)
    if when == "before":
        revoke()
    queue.execute_queued_grouping(app.state.sessions, provider)
    assert provider.calls == (0 if when == "before" else 1)
    assert client.get(group_case["path"] + "/runs/" + str(handle["run_id"])).status_code == 404
    signin(client, "f2-owner")
    receipt = run(client, group_case, handle)
    assert receipt["state"] == "cancelled"
    assert receipt["units"][0]["attempt"]["reason_code"] == "access_revoked"
    assert client.get(group_case["path"] + "/groups").json()["items"] == []


@pytest.mark.parametrize("when", ["before", "during"])
def test_stale_source(client, app, group_case, when):
    handle = enqueue(app, client, group_case)

    def candidate(req):
        change_source(app, group_case)
        return synthetic_response({"request": req})

    provider = ScriptedReplay(candidate)
    if when == "before":
        change_source(app, group_case)
    queue.execute_queued_grouping(app.state.sessions, provider)
    assert provider.calls == (0 if when == "before" else 1)
    receipt = run(client, group_case, handle)
    assert receipt["state"] == "cancelled"
    assert receipt["units"][0]["attempt"]["reason_code"] == "input_changed"


def test_context_snapshot_and_stale_previous_group(client, app, group_case):
    first = prepare(app, client, group_case)
    accept(app, first, synthetic_response(first))
    group = client.get(group_case["path"] + "/groups").json()["items"][0]
    detail = client.get(group_case["path"] + "/groups/" + group["id"]).json()
    doc = client.post(
        group_case["path"] + "/documents", json={"title": "Context", "text": "Exact context"}
    ).json()
    handle = enqueue(
        app,
        client,
        group_case,
        document_refs=[{"id": doc["id"], "state_id": doc["state_id"]}],
        previous_group_refs=[{"id": group["id"], "state_id": group["state_id"]}],
    )
    selected = run(client, group_case, handle)["units"][0]["input"]
    assert selected["documents"][0]["state_id"] == doc["state_id"]
    assert selected["previous_groups"][0]["state_id"] == group["state_id"]
    advance_group(app, group_case, detail)
    provider = ScriptedReplay()
    assert queue.execute_queued_grouping(app.state.sessions, provider) is False
    assert provider.calls == 0
    assert run(client, group_case, handle)["units"][0]["attempt"]["reason_code"] == "input_changed"


@pytest.mark.parametrize("expiry", ["lease", "deadline"])
def test_crashed_worker_is_not_reexecuted(client, app, database_url, group_case, expiry):
    handle = enqueue(app, client, group_case)
    # Run the actual worker pass with an injected, blocking synthetic transport.
    code = (
        "import sys,time\n"
        "from feedback2req.grouping import provider\n"
        "from feedback2req.processing import worker\n"
        "class Blocking(provider.SyntheticGrouping):\n"
        " def group(self,request):\n"
        "  print('synthetic_compute_started',flush=True)\n"
        "  time.sleep(60)\n"
        "  return super().group(request)\n"
        "provider.grouping_provider=lambda settings: Blocking('one')\n"
        "sys.argv=['worker','--once']\n"
        "raise SystemExit(worker.main())\n"
    )
    process = subprocess.Popen(
        [sys.executable, "-B", "-c", code],
        env=worker_env(database_url, None),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            with app.state.sessions() as tx:
                claimed = tx.scalar(select(Attempt.id).where(Attempt.unit_id == handle["unit_id"]))
            if claimed or process.poll() is not None:
                break
            time.sleep(0.05)
        assert claimed
    finally:
        if process.poll() is None:
            process.kill()
        stdout, stderr = process.communicate(timeout=5)
    # Claim is durable before the transport starts; either kill boundary is safe.
    assert not stderr
    with app.state.sessions.begin() as tx:
        attempt = tx.scalar(select(Attempt).where(Attempt.unit_id == handle["unit_id"]))
        if expiry == "deadline":
            attempt.started_at -= timedelta(seconds=200)
            attempt.deadline_at = service.now(tx) - timedelta(seconds=1)
        attempt.lease_expires_at = service.now(tx) - timedelta(seconds=2)
    worker(database_url)
    receipt = run(client, group_case, handle)
    assert receipt["state"] == "failed"
    assert receipt["units"][0]["attempt"]["reason_code"] == (
        "lease_expired" if expiry == "lease" else "deadline_exceeded"
    )
    assert client.get(group_case["path"] + "/groups").json()["items"] == []


class Uncertain:
    def __init__(self, sessions, phase, committed=True):
        self.sessions, self.phase, self.committed = sessions, phase, committed

    def __call__(self):
        return self.sessions()

    @contextmanager
    def begin(self):
        with self.sessions.begin() as tx:
            yield tx
            hit = bool(
                tx.scalar(
                    select(Unit.id)
                    .join(Run)
                    .where(
                        Run.operation == "group_findings",
                        Unit.state == self.phase,
                    )
                )
            )
            if hit and not self.committed:
                raise ConnectionError("Unknown commit result with rollback")
        if hit:
            raise ConnectionError("Unknown commit result")


@pytest.mark.parametrize("phase", ["queued", "running", "completed"])
def test_unknown_commit_does_not_repeat_model(client, app, group_case, phase):
    key, provider = uuid4(), ScriptedReplay()
    sessions = Uncertain(app.state.sessions, phase)
    if phase == "queued":
        with pytest.raises(ConnectionError):
            enqueue(app, client, group_case, sessions=sessions, key=key)
        handle = enqueue(app, client, group_case, key=key)
        assert handle["replayed"]
        assert provider.calls == 0
        assert queue.execute_queued_grouping(app.state.sessions, provider)
    else:
        handle = enqueue(app, client, group_case, key=key)
        with pytest.raises(ConnectionError):
            queue.execute_queued_grouping(sessions, provider)
        assert not queue.execute_queued_grouping(app.state.sessions, provider)
    assert provider.calls == (0 if phase == "running" else 1)
    assert enqueue(app, client, group_case, key=key)["replayed"]
    # Synchronous F2 replay also must not dispatch a queued/previously claimed Unit.
    assert execute(app, client, group_case, provider, key=key)["replayed"]
    assert provider.calls == (0 if phase == "running" else 1)


def test_queue_idempotency_and_limits(client, app, group_case):
    key = uuid4()
    handle = enqueue(app, client, group_case, key=key)
    assert (
        enqueue(app, client, group_case, key=key, finding_refs=list(reversed(group_case["refs"])))[
            "run_id"
        ]
        == handle["run_id"]
    )
    with pytest.raises(AppError) as caught:
        enqueue(app, client, group_case, key=key, finding_refs=group_case["refs"][:1])
    assert caught.value.code == "idempotency_conflict"
    with pytest.raises(AppError):
        enqueue(app, client, group_case, finding_refs=group_case["refs"] * 34)
    provider = ScriptedReplay()
    assert execute(app, client, group_case, provider, key=key)["result"] is None
    assert provider.calls == 0


def test_f1_claim_does_not_consume_grouping(client, app, group_case):
    handle = enqueue(app, client, group_case)
    assert service.claim(app.state.sessions) is None
    assert run(client, group_case, handle)["state"] == "queued"
    assert queue.execute_queued_grouping(app.state.sessions, UnconfiguredGrouping())


def test_queued_context_and_previous_annotations_roundtrip(client, app, group_case):
    first = prepare(app, client, group_case)
    accept(app, first, synthetic_response(first))
    group = client.get(group_case["path"] + "/groups").json()["items"][0]
    original = client.get(group_case["path"] + "/groups/" + group["id"]).json()
    doc = client.post(
        group_case["path"] + "/documents", json={"title": "Context", "text": "Context"}
    ).json()
    handle = enqueue(
        app,
        client,
        group_case,
        document_refs=[{"id": doc["id"], "state_id": doc["state_id"]}],
        previous_group_refs=[{"id": group["id"], "state_id": group["state_id"]}],
    )

    def response(req):
        value = synthetic_response({"request": req})
        value["result"]["groups"][0]["context_keys"] = ["d1"]
        for kind in ("questions", "uncertainties"):
            value[kind][0]["related"] = [{"origin": "input", "key": "g1"}]
        return value

    provider = ScriptedReplay(response)
    assert queue.execute_queued_grouping(app.state.sessions, provider)
    receipt = run(client, group_case, handle)["units"][0]["attempt"]
    for kind in ("questions", "uncertainties"):
        assert receipt["annotations"][kind][0]["related"][0] == {
            "origin": "input",
            "key": "g1",
            "kind": "finding_group",
            "id": group["id"],
            "state_id": group["state_id"],
        }
    details = [
        client.get(group_case["path"] + "/groups/" + identity).json()
        for identity in receipt["grouping_result"]["group_ids"]
    ]
    assert any(
        d["context"] and d["context"][0]["ref"]["state_id"] == doc["state_id"] for d in details
    )
    assert provider.calls == 1
    assert client.get(group_case["path"] + "/groups/" + group["id"]).json() == original


@pytest.mark.parametrize("damage", ["duplicate_range", "oversized_context"])
def test_queue_rejects_context_before_commit(client, app, group_case, damage):
    doc = client.post(
        group_case["path"] + "/documents", json={"title": "Context", "text": "ABC"}
    ).json()
    refs = [{"id": doc["id"], "state_id": doc["state_id"]}]
    if damage == "duplicate_range":
        refs.append(refs[0] | {"locator": {"start": 0, "end": 3}})
    else:
        with app.state.sessions.begin() as tx:
            tx.get(DocumentState, UUID(doc["state_id"])).text = "A" * 1048577
    with app.state.sessions() as tx:
        before = tx.scalar(select(func.count()).select_from(Run))
    with pytest.raises(AppError) as caught:
        enqueue(app, client, group_case, document_refs=refs)
    assert caught.value.code == "invalid_input"
    with app.state.sessions() as tx:
        assert tx.scalar(select(func.count()).select_from(Run)) == before


def test_concurrent_enqueue_deduplicates(client, app, group_case):
    key = uuid4()
    with ThreadPoolExecutor(max_workers=2) as pool:
        handles = list(pool.map(lambda _: enqueue(app, client, group_case, key=key), range(2)))
    assert handles[0]["unit_id"] == handles[1]["unit_id"]
    assert {h["replayed"] for h in handles} == {False, True}


@pytest.mark.parametrize("phase", ["running", "completed"])
def test_unknown_commit_with_rollback(client, app, group_case, phase):
    handle = enqueue(app, client, group_case)
    provider = ScriptedReplay()
    with pytest.raises(ConnectionError):
        queue.execute_queued_grouping(
            Uncertain(app.state.sessions, phase, committed=False), provider
        )
    assert provider.calls == (0 if phase == "running" else 1)
    if phase == "running":
        assert run(client, group_case, handle)["state"] == "queued"
        assert queue.execute_queued_grouping(app.state.sessions, provider)
    else:
        assert run(client, group_case, handle)["state"] == "running"
        assert not queue.execute_queued_grouping(app.state.sessions, provider)
    assert provider.calls == 1


def test_provider_failure_has_no_synthetic_fallback(client, app, group_case):
    handle = enqueue(app, client, group_case)

    def failed(req):
        raise RuntimeError("Private source text must not appear in stored errors")

    provider = ScriptedReplay(failed)
    provider.synthetic = False
    provider.name, provider.model = "injected-real-contract", "no-external-call"
    assert queue.execute_queued_grouping(app.state.sessions, provider)
    attempt = run(client, group_case, handle)["units"][0]["attempt"]
    assert attempt["state"] == "failed" and attempt["reason_code"] == "provider_error"
    assert attempt["synthetic"] is False
    assert attempt["grouping_result"] is None
    assert "Private source text" not in str(attempt)
    assert provider.calls == 1
    assert not queue.execute_queued_grouping(app.state.sessions, provider)
    assert provider.calls == 1
