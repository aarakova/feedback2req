"""Real PG/API tests; deterministic provider output is explicitly synthetic."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from feedback2req.persistence.models import FeedbackSource, ProjectAccess, SourceTextState
from feedback2req.persistence.processing import Attempt, Finding, Fragment, Run
from feedback2req.processing import service, validation
from feedback2req.processing.provider import ProviderError

from .conftest import ORIGIN, project, signin, signup


class Synthetic:
    name, model, synthetic = "test-only", "deterministic", True

    def __init__(self, change=None):
        self.calls = 0
        self.change = change

    def extract(self, request):
        self.calls += 1
        response = {
            "coverage": [{"input_key": "s1", "reviewed": True, "disposition": "completed"}],
            "questions": [],
            "uncertainties": [],
            "result": {
                "fragments": [
                    {
                        "local_id": "f1",
                        "segment_key": "s1",
                        "quote": request["input"]["segments"][0]["text"],
                        "occurrence": 0,
                    }
                ],
                "findings": [
                    {
                        "local_id": "n1",
                        "text": "Синтетическая находка для теста",
                        "types": ["request"],
                        "mode": "direct",
                        "fragment_ids": ["f1"],
                        "considered_keys": ["s1"],
                        "context_keys": [],
                    }
                ],
            },
        }
        if self.change:
            self.change(request, response)
        return response


@pytest.fixture
def setup_run(client):
    owner = signup(client, "extract-owner")
    signin(client, "extract-owner")
    p = project(client)
    path = f"/api/v1/projects/{p['id']}"
    source = client.post(
        path + "/sources", json={"kind": "text", "text": " ё🙂\r\n фильтры "}
    ).json()
    return owner, path, source


def start(client, path, source, key=None, operation="extract_feedback"):
    return client.post(
        path + "/runs",
        headers={"Idempotency-Key": str(key or uuid4())},
        json={
            "operation": operation,
            "inputs": [{"kind": "source", "id": source["id"], "state_id": source["state_id"]}],
        },
    )


def get_run(client, path, run):
    return client.get(path + "/runs/" + run["id"]).json()


def test_extract_end_to_end(client, app, setup_run):
    _, path, source = setup_run
    assert client.get(path + "/findings").json()["items"] == []
    response = start(client, path, source)
    assert response.status_code == 202
    run = response.json()
    assert run["state"] == "queued"
    assert run["units"][0]["attempt"] is None
    provider = Synthetic()
    assert service.execute_one(app.state.sessions, app.state.settings, provider)
    completed = get_run(client, path, run)
    assert completed["state"] == "completed"
    attempt = completed["units"][0]["attempt"]
    assert attempt["synthetic"] is True and attempt["ai_performed"] is False
    assert "owner_token" not in attempt
    found = client.get(path + "/findings").json()["items"]
    assert len(found) == 1
    item = client.get(path + "/findings/" + found[0]["id"]).json()
    fragment = item["evidence"][0]
    assert fragment["quote"] == source["text"]
    assert fragment["source_ref"]["state_id"] == source["state_id"]
    assert fragment["locator"] == {"start": 0, "end": len(source["text"])}
    assert (
        client.get(path + f"/fragments/{fragment['id']}/states/{fragment['state_id']}").json()
        == fragment
    )
    assert not service.execute_one(app.state.sessions, app.state.settings, provider)
    assert provider.calls == 1
    overview = client.get(path + "/overview").json()
    assert overview["material_counts"] == {"text_sources": 1, "product_documents": 0}
    assert overview["processing"]["latest_run_id"] == run["id"]
    assert client.get(path + "/runs").json()["items"] == [completed]
    assert source["text"] not in str(overview)


def test_invalid_response_and_manual_retry(client, app, setup_run):
    _, path, source = setup_run
    run = start(client, path, source).json()
    broken = Synthetic(lambda req, out: out["result"]["fragments"][0].update(quote="not in source"))
    service.execute_one(app.state.sessions, app.state.settings, broken)
    failed = get_run(client, path, run)
    assert failed["state"] == "failed"
    attempt = failed["units"][0]["attempt"]
    assert attempt["reason_code"] == "invalid_response"
    assert attempt["finding_ids"] == attempt["fragment_ids"] == []
    assert not service.execute_one(app.state.sessions, app.state.settings, broken)
    key = str(uuid4())
    target = path + f"/units/{failed['units'][0]['id']}/retries"
    body = {"expected_attempt_id": attempt["id"]}
    retried = client.post(target, headers={"Idempotency-Key": key}, json=body)
    assert retried.status_code == 202
    assert client.post(target, headers={"Idempotency-Key": key}, json=body).json() == retried.json()
    assert (
        client.post(target, headers={"Idempotency-Key": str(uuid4())}, json=body).status_code == 409
    )
    service.execute_one(app.state.sessions, app.state.settings, Synthetic())
    assert get_run(client, path, retried.json())["state"] == "completed"
    assert get_run(client, path, run)["state"] == "failed"


def test_input_and_idempotency(client, app, setup_run):
    _, path, source = setup_run
    key = uuid4()
    first = start(client, path, source, key)
    assert start(client, path, source, key).json() == first.json()
    assert start(client, path, source, key, "inspect_text").status_code == 409
    assert (
        client.post(
            path + "/runs", json={"operation": "extract_feedback", "inputs": []}
        ).status_code
        == 422
    )
    doc = client.post(path + "/documents", json={"title": "Контекст", "text": "x"}).json()
    assert start(client, path, source | {"state_id": doc["state_id"]}).status_code == 422
    assert start(client, path, source | {"state_id": str(uuid4())}).status_code == 404
    other = project(client)
    other_path = f"/api/v1/projects/{other['id']}"
    assert start(client, other_path, source).status_code == 404
    denied = start(client, path, source)
    assert denied.status_code == 202
    assert (
        client.post(
            path + "/runs", json=first.json(), headers={"X-CSRF-Token": "wrong"}
        ).status_code
        == 403
    )
    with TestClient(app, base_url=ORIGIN, headers={"Origin": ORIGIN}) as outsider:
        signup(outsider, "outsider")
        signin(outsider, "outsider")
        for suffix in ["/runs", "/findings", "/overview", "/runs/" + first.json()["id"]]:
            assert outsider.get(path + suffix).status_code == 404
        assert start(outsider, path, source).status_code == 404


@pytest.mark.parametrize("mutate", ["revoke", "input", "expire"])
def test_publication_rechecks_permissions_input_and_lease(client, app, setup_run, mutate):
    _, path, source = setup_run
    member = signup(client, "extract-member")
    client.put(path + "/access/" + member["id"], json={"can_approve": True})
    signin(client, "extract-member")
    run = start(client, path, source).json()

    def change(req, out):
        with app.state.sessions.begin() as tx:
            if mutate == "revoke":
                tx.delete(tx.get(ProjectAccess, (UUID(req["project_id"]), UUID(member["id"]))))
            elif mutate == "input":
                header = tx.get(FeedbackSource, UUID(source["id"]))
                replacement = SourceTextState(
                    id=uuid4(),
                    project_id=header.project_id,
                    source_id=header.id,
                    text="Changed",
                    author_id=UUID(member["id"]),
                    origin="human",
                )
                tx.add(replacement)
                tx.flush()
                header.current_state_id = replacement.id
            else:
                attempt = tx.scalar(
                    select(Attempt).where(Attempt.request_id == UUID(req["request_id"]))
                )
                attempt.lease_expires_at = service.now(tx) - timedelta(seconds=1)

    service.execute_one(app.state.sessions, app.state.settings, Synthetic(change))
    with app.state.sessions() as tx:
        assert tx.scalar(select(func.count()).select_from(Finding)) == 0
        attempt = tx.scalar(select(Attempt))
        assert attempt.state == ("running" if mutate == "expire" else "cancelled")
    if mutate == "expire":
        service.recover_one(app.state.sessions)
        assert get_run(client, path, run)["state"] == "failed"


@pytest.mark.parametrize("stage", ["claim", "completion"])
def test_unknown_commit_never_replays_provider_or_publication(client, app, setup_run, stage):
    _, path, source = setup_run
    run = start(client, path, source).json()
    provider = Synthetic()

    class Uncertain:
        count = 0

        @contextmanager
        def begin(self):
            self.count += 1
            turn = self.count
            with app.state.sessions.begin() as tx:
                yield tx
            if turn == (2 if stage == "claim" else 4):
                raise ConnectionError("simulated lost COMMIT acknowledgement")

    with pytest.raises(ConnectionError):
        service.execute_one(Uncertain(), app.state.settings, provider)
    result = get_run(client, path, run)
    assert result["state"] == ("running" if stage == "claim" else "completed")
    assert provider.calls == (0 if stage == "claim" else 1)
    assert not service.execute_one(app.state.sessions, app.state.settings, provider)
    assert provider.calls == (0 if stage == "claim" else 1)


def test_disabled_provider_and_technical_result(client, app, setup_run):
    _, path, source = setup_run
    run = start(client, path, source).json()
    service.execute_one(app.state.sessions, app.state.settings)
    failed = get_run(client, path, run)
    assert failed["units"][0]["attempt"]["reason_code"] == "provider_not_configured"
    technical = start(client, path, source, operation="inspect_text").json()
    service.execute_one(app.state.sessions, app.state.settings)
    attempt = get_run(client, path, technical)["units"][0]["attempt"]
    assert attempt["technical_result"] == {
        "character_count": len(source["text"]),
        "utf8_byte_count": len(source["text"].encode()),
    }
    assert attempt["ai_performed"] is False


@pytest.mark.parametrize("damage", ["duplicate", "coverage", "context", "question", "partial"])
def test_programmatic_contract_rejection(damage):
    req = validation.request(uuid4(), uuid4(), uuid4(), uuid4(), "aaa")
    response = Synthetic().extract(req)
    if damage == "duplicate":
        response["result"]["findings"][0]["local_id"] = "f1"
    elif damage == "coverage":
        response["coverage"][0]["input_key"] = "not-s1"
    elif damage == "context":
        response["result"]["findings"][0]["context_keys"] = ["foreign-document"]
    elif damage == "question":
        response["questions"] = [
            {
                "local_id": "q",
                "text": "?",
                "reason": "unclear",
                "blocking": True,
                "related": [{"origin": "output", "key": "f1"}],
            }
        ]
    else:
        response["coverage"][0]["disposition"] = "partially_processed"
    with pytest.raises(validation.InvalidResponse):
        validation.accept(req, response)


def test_empty_success_and_overlapping_occurrence(client, app, setup_run):
    _, path, source = setup_run
    run = start(client, path, source).json()

    def empty(req, out):
        out["result"] = {"fragments": [], "findings": []}
        out["coverage"][0]["reason"] = "No actionable feedback in synthetic test"

    service.execute_one(app.state.sessions, app.state.settings, Synthetic(empty))
    result = get_run(client, path, run)
    assert result["state"] == "completed"
    assert result["units"][0]["attempt"]["coverage"][0]["reason"]
    req = validation.request(uuid4(), uuid4(), uuid4(), uuid4(), "aaa")
    out = Synthetic().extract(req)
    out["result"]["fragments"][0].update(quote="aa", occurrence=1)
    assert validation.accept(req, out) == {"f1": (1, 3)}


def test_concurrent_idempotency_and_claim(client, app, setup_run):
    owner, path, source = setup_run
    project_id = UUID(path.rsplit("/", 1)[1])
    key = uuid4()
    inputs = [{"kind": "source", "id": UUID(source["id"]), "state_id": UUID(source["state_id"])}]

    def issue(_):
        with app.state.sessions.begin() as tx:
            return service.command(
                tx, project_id, UUID(owner["id"]), key, "extract_feedback", inputs
            ).id

    with ThreadPoolExecutor(max_workers=2) as pool:
        ids = list(pool.map(issue, range(2)))
    assert ids[0] == ids[1]
    with ThreadPoolExecutor(max_workers=2) as pool:
        claimed = list(pool.map(lambda _: service.claim(app.state.sessions), range(2)))
    assert sum(item is not None for item in claimed) == 1
    with app.state.sessions() as tx:
        assert tx.scalar(select(func.count()).select_from(Attempt)) == 1


def test_independent_success_survives_partial_failure(client, app, setup_run):
    _, path, source = setup_run
    second = client.post(path + "/sources", json={"kind": "text", "text": "second"}).json()
    response = client.post(
        path + "/runs",
        headers={"Idempotency-Key": str(uuid4())},
        json={
            "operation": "extract_feedback",
            "inputs": [
                {"kind": "source", "id": item["id"], "state_id": item["state_id"]}
                for item in [source, second]
            ],
        },
    )
    assert response.status_code == 202
    provider = Synthetic()
    service.execute_one(app.state.sessions, app.state.settings, provider)

    class Broken(Synthetic):
        def extract(self, request):
            raise ProviderError()

    service.execute_one(app.state.sessions, app.state.settings, Broken())
    result = get_run(client, path, response.json())
    assert result["state"] == "partial"
    assert {unit["state"] for unit in result["units"]} == {"completed", "failed"}
    assert len(client.get(path + "/findings").json()["items"]) == 1


def test_new_tables_reject_cross_project_evidence(client, app, setup_run):
    from sqlalchemy.exc import IntegrityError

    _, path, source = setup_run
    start(client, path, source)
    service.execute_one(app.state.sessions, app.state.settings, Synthetic())
    other = project(client)
    with app.state.sessions() as tx:
        fragment = tx.scalar(select(Fragment))
        values = dict(
            id=uuid4(),
            project_id=UUID(other["id"]),
            attempt_id=fragment.attempt_id,
            local_id="foreign",
            source_id=fragment.source_id,
            source_state_id=fragment.source_state_id,
            quote=fragment.quote,
            start=fragment.start,
            end=fragment.end,
            reliability="usable",
        )
    with pytest.raises(IntegrityError), app.state.sessions.begin() as tx:
        tx.add(Fragment(**values))


def test_worker_sql_timeouts_and_connection_recovery(database_url):
    from sqlalchemy import text
    from sqlalchemy.exc import OperationalError

    engine, sessions = service.worker_database(database_url)
    try:
        with sessions.begin() as tx:
            assert tx.scalar(text("SHOW statement_timeout")) == "5s"
            assert tx.scalar(text("SHOW lock_timeout")) == "2s"
            assert tx.scalar(text("SHOW transaction_timeout")) == "8s"
        with pytest.raises(OperationalError), sessions.begin() as tx:
            tx.execute(text("SELECT pg_sleep(6)"))
        with sessions.begin() as tx:
            assert tx.scalar(select(func.count()).select_from(Run)) == 0
    finally:
        engine.dispose()
