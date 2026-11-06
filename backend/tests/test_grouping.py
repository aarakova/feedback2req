"""DEC-016: synthetic group outputs, real PostgreSQL transactions and HTTP."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from copy import deepcopy
from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select, text
from sqlalchemy.exc import IntegrityError

from feedback2req.errors import AppError
from feedback2req.grouping import service as grouping
from feedback2req.grouping import validation
from feedback2req.persistence.grouping import (
    ConflictPosition,
    FindingGroup,
    GroupConflict,
    GroupContext,
    GroupingInput,
    GroupMember,
    GroupScope,
    GroupState,
    PositionMember,
)
from feedback2req.persistence.models import (
    FeedbackSource,
    ProjectAccess,
    SourceTextState,
)
from feedback2req.persistence.processing import Attempt
from feedback2req.processing import service

from .conftest import ORIGIN, project, signin, signup
from .test_processing import Synthetic, start


@pytest.fixture
def group_case(client, app):
    owner = signup(client, "f2-owner")
    signin(client, "f2-owner")
    p = project(client)
    path = f"/api/v1/projects/{p['id']}"
    sources = []
    for value in (
        "Отправлять уведомления автоматически 🙂",
        "Только после подтверждения",
        "Другая потребность",
    ):
        source = client.post(path + "/sources", json={"kind": "text", "text": value}).json()
        sources.append(source)
        assert start(client, path, source).status_code == 202
        assert service.execute_one(app.state.sessions, app.state.settings, Synthetic())
    findings = client.get(path + "/findings").json()["items"]
    refs = [{"id": f["id"], "state_id": f["state_id"]} for f in findings]
    return {
        "owner": owner,
        "project_id": UUID(p["id"]),
        "path": path,
        "sources": sources,
        "findings": findings,
        "refs": refs,
    }


def prepare(app, client, case, **kwargs):
    return grouping.prepare_grouping(
        app.state.sessions,
        app.state.identity,
        client.cookies.get(app.state.settings.session_cookie),
        case["project_id"],
        kwargs.pop("command_key", uuid4()),
        kwargs.pop("finding_refs", case["refs"]),
        provenance=grouping.Provenance("synthetic-test", "fixture-v1", True),
        **kwargs,
    )


def synthetic_response(handle):
    """A test receipt, never a substitute provider in runtime."""
    keys = [f["key"] for f in handle["request"]["input"]["findings"]]
    return {
        "coverage": [
            {
                "input_key": k,
                "reviewed": True,
                "disposition": "completed",
                "reason": "Synthetic fixture",
            }
            for k in keys
        ],
        "questions": [
            {
                "local_id": "q1",
                "text": "Какие условия применимы?",
                "reason": "Нужно решение человека",
                "blocking": True,
                "related": [{"origin": "output", "key": "g1"}],
            }
        ],
        "uncertainties": [
            {
                "local_id": "u1",
                "reason": "Возможно, разные сценарии",
                "related": [{"origin": "input", "key": keys[0]}],
            }
        ],
        "result": {
            "groups": [
                {
                    "local_id": "g1",
                    "title": "Уведомления",
                    "summary": "Различные ожидания",
                    "finding_keys": keys[:2],
                    "considered_keys": keys,
                    "context_keys": [],
                    "conflicts": [
                        {
                            "local_id": "c1",
                            "description": "Противоположные ожидания",
                            "positions": [
                                {"description": "Автоматически", "finding_keys": [keys[0]]},
                                {"description": "С подтверждением", "finding_keys": [keys[1]]},
                            ],
                        }
                    ],
                },
                {
                    "local_id": "g2",
                    "title": "Автоматизация",
                    "summary": "Одна находка в двух группах",
                    "finding_keys": [keys[0]],
                    "considered_keys": [keys[0]],
                    "context_keys": [],
                    "conflicts": [],
                },
            ],
            "ungrouped_finding_keys": keys[2:],
        },
    }


def accept(app, h, response):
    return grouping.accept_grouping(app.state.sessions, h["unit_id"], h["owner_token"], response)


def run(client, case, h):
    response = client.get(case["path"] + "/runs/" + str(h["run_id"]))
    assert response.status_code == 200, response.text
    return response.json()


def test_groups_traceability_conflicts_many_to_many_and_runs(client, app, group_case):
    h = prepare(app, client, group_case)
    assert run(client, group_case, h)["units"][0]["attempt"]["grouping_result"] is None
    assert grouping.renew_grouping(app.state.sessions, h["unit_id"], h["owner_token"])
    assert accept(app, h, synthetic_response(h))["state"] == "completed"
    result = run(client, group_case, h)
    receipt = result["units"][0]["attempt"]
    assert receipt["synthetic"] is True and receipt["ai_performed"] is False
    assert "owner_token" not in str(result) and "grouping_owner_hash" not in str(result)
    assert len(receipt["grouping_result"]["ungrouped_findings"]) == 1
    listed = client.get(group_case["path"] + "/groups").json()
    assert len(listed["items"]) == 2
    assert all("members" not in v and "quote" not in v for v in listed["items"])
    for summary in listed["items"]:
        detail = client.get(group_case["path"] + "/groups/" + summary["id"]).json()
        exact = client.get(
            group_case["path"] + f"/groups/{detail['id']}/states/{detail['state_id']}"
        )
        assert exact.json() == detail
        assert detail["freshness"] == "current"
        for member in detail["members"]:
            assert member["ref"]["state_id"] == member["finding"]["state_id"]
            fragment = member["finding"]["evidence"][0]
            assert fragment["quote"] in [s["text"] for s in group_case["sources"]]
            assert fragment["source_ref"]["state_id"] in [
                s["state_id"] for s in group_case["sources"]
            ]
        if detail["conflicts"]:
            positions = detail["conflicts"][0]["positions"]
            assert len(positions) == 2 and positions[0]["findings"] != positions[1]["findings"]
    assert len(client.get(group_case["path"] + "/findings").json()["items"]) == 3
    assert client.get(group_case["path"] + "/overview").json()["semantic_metrics"] == {
        "availability": "not_implemented"
    }


@pytest.mark.parametrize("mixed", [False, True])
def test_all_ungrouped_empty_success_and_insufficient_information(client, app, group_case, mixed):
    h = prepare(app, client, group_case)
    out = synthetic_response(h)
    keys = [f["key"] for f in h["request"]["input"]["findings"]]
    out["result"] = {"groups": [], "ungrouped_finding_keys": keys}
    out["questions"][0]["related"] = [{"origin": "input", "key": keys[0]}]
    if mixed:
        out["coverage"][1]["disposition"] = "insufficient_information"
        out["coverage"][2].update(reviewed=False, disposition="not_processed")
        out["result"]["ungrouped_finding_keys"] = keys[:2]
    assert accept(app, h, out)["state"] == "completed"
    receipt = run(client, group_case, h)["units"][0]["attempt"]
    assert receipt["grouping_result"]["group_ids"] == []
    assert len(receipt["grouping_result"]["ungrouped_findings"]) == (2 if mixed else 3)
    assert receipt["annotations"]["questions"][0]["blocking"] is True
    assert len(receipt["coverage"]) == 3
    assert client.get(group_case["path"] + "/groups").json() == {"items": [], "next_cursor": None}


@pytest.mark.parametrize(
    "damage",
    [
        "duplicate_id",
        "duplicate_conflict_id",
        "foreign_member",
        "empty_members",
        "one_position",
        "foreign_position",
        "duplicate_position",
        "coverage_duplicate",
        "coverage_missing",
        "coverage_foreign",
        "partial_item",
        "unreviewed_member",
        "lost_finding",
        "grouped_ungrouped",
        "foreign_context",
        "foreign_considered",
        "member_not_considered",
        "question_to_conflict",
        "unknown_field",
        "nul",
    ],
)
def test_invalid_outputs_are_rejected_atomically(client, app, group_case, damage):
    h = prepare(app, client, group_case)
    out = synthetic_response(h)
    g = out["result"]["groups"][0]
    if damage == "duplicate_id":
        out["questions"][0]["local_id"] = "g1"
    elif damage == "duplicate_conflict_id":
        g["conflicts"][0]["local_id"] = "g2"
    elif damage == "foreign_member":
        g["finding_keys"] = ["not-supplied"]
    elif damage == "empty_members":
        g["finding_keys"] = []
    elif damage == "one_position":
        g["conflicts"][0]["positions"].pop()
    elif damage == "foreign_position":
        g["conflicts"][0]["positions"][0]["finding_keys"] = ["f3"]
    elif damage == "duplicate_position":
        g["conflicts"][0]["positions"][1] = deepcopy(g["conflicts"][0]["positions"][0])
    elif damage == "coverage_duplicate":
        out["coverage"].append(out["coverage"][0])
    elif damage == "coverage_missing":
        out["coverage"].pop()
    elif damage == "coverage_foreign":
        out["coverage"][0]["input_key"] = "foreign"
    elif damage == "partial_item":
        out["coverage"][0]["disposition"] = "partially_processed"
    elif damage == "unreviewed_member":
        out["coverage"][0].update(reviewed=False, disposition="not_processed")
    elif damage == "lost_finding":
        out["result"]["ungrouped_finding_keys"] = []
    elif damage == "grouped_ungrouped":
        out["result"]["ungrouped_finding_keys"].append("f1")
    elif damage == "foreign_context":
        g["context_keys"] = ["d1"]
    elif damage == "foreign_considered":
        g["considered_keys"].append("other")
    elif damage == "member_not_considered":
        g["considered_keys"] = ["f1"]
    elif damage == "question_to_conflict":
        out["questions"][0]["related"] = [{"origin": "output", "key": "c1"}]
    elif damage == "unknown_field":
        out["result"]["unexpected"] = True
    else:
        g["summary"] = "bad\x00text"
    assert accept(app, h, out)["reason_code"] == "invalid_response"
    with app.state.sessions() as tx:
        assert tx.scalar(select(func.count()).select_from(FindingGroup)) == 0
        assert tx.scalar(select(func.count()).select_from(PositionMember)) == 0
    attempt = run(client, group_case, h)["units"][0]["attempt"]
    assert attempt["coverage"] is None and attempt["grouping_result"] is None


def test_replay_concurrent_accept_capabilities_and_public_start_denied(client, app, group_case):
    key = uuid4()
    h = prepare(app, client, group_case, command_key=key)
    replay = prepare(app, client, group_case, command_key=key)
    assert replay["replayed"] and replay["owner_token"] is None and replay["request"] is None
    with pytest.raises(AppError, match="another command"):
        prepare(app, client, group_case, command_key=key, finding_refs=group_case["refs"][:1])
    out = synthetic_response(h)
    with ThreadPoolExecutor(max_workers=2) as pool:
        receipts = list(pool.map(lambda _: accept(app, h, out), range(2)))
    assert receipts[0] == receipts[1]
    assert accept(app, h, {"invalid replay payload": True}) == receipts[0]
    with pytest.raises(AppError):
        grouping.accept_grouping(app.state.sessions, h["unit_id"], uuid4(), out)
    with app.state.sessions() as tx:
        assert tx.scalar(select(func.count()).select_from(FindingGroup)) == 2
    assert (
        client.post(
            group_case["path"] + "/runs",
            headers={"Idempotency-Key": str(uuid4())},
            json={"operation": "group_findings", "inputs": []},
        ).status_code
        == 422
    )
    assert (
        client.post(
            group_case["path"] + f"/units/{h['unit_id']}/retries",
            headers={"Idempotency-Key": str(uuid4())},
            json={"expected_attempt_id": str(h["attempt_id"])},
        ).status_code
        == 409
    )


@pytest.mark.parametrize("change", ["source", "revoke", "lease", "deadline"])
def test_late_publication_rechecks_current_state_access_and_time(client, app, group_case, change):
    member = signup(client, "f2-member")
    assert (
        client.put(
            group_case["path"] + "/access/" + member["id"], json={"can_approve": False}
        ).status_code
        == 200
    )
    signin(client, "f2-member")
    h = prepare(app, client, group_case)
    with app.state.sessions.begin() as tx:
        if change == "revoke":
            tx.delete(tx.get(ProjectAccess, (group_case["project_id"], UUID(member["id"]))))
        elif change == "source":
            source = tx.get(FeedbackSource, UUID(group_case["sources"][0]["id"]))
            replacement = SourceTextState(
                id=uuid4(),
                project_id=source.project_id,
                source_id=source.id,
                text="Новая редакция",
                author_id=UUID(member["id"]),
                origin="human",
            )
            tx.add(replacement)
            tx.flush()
            source.current_state_id = replacement.id
        else:
            attempt = tx.get(Attempt, h["attempt_id"])
            instant = service.now(tx)
            attempt.lease_expires_at = instant - timedelta(seconds=1)
            if change == "deadline":
                attempt.started_at = instant - timedelta(seconds=200)
                attempt.deadline_at = instant - timedelta(seconds=1)
    if change in {"lease", "deadline"}:
        assert not grouping.renew_grouping(app.state.sessions, h["unit_id"], h["owner_token"])
        with pytest.raises(AppError):
            accept(app, h, synthetic_response(h))
        service.recover_one(app.state.sessions)
        signin(client, "f2-owner")
        attempt = run(client, group_case, h)["units"][0]["attempt"]
        assert attempt["reason_code"] == (
            "lease_expired" if change == "lease" else "deadline_exceeded"
        )
    else:
        assert accept(app, h, synthetic_response(h))["state"] == "cancelled"
    with app.state.sessions() as tx:
        assert tx.scalar(select(func.count()).select_from(FindingGroup)) == 0


def test_transaction_rollback_and_independent_result_survives(client, app, group_case):
    first = prepare(app, client, group_case)
    accept(app, first, synthetic_response(first))
    h = prepare(app, client, group_case)

    def fail_after_some_inserts(conn, cursor, statement, parameters, context, executemany):
        if statement.startswith("INSERT INTO conflict_positions"):
            raise ConnectionError("synthetic SQL write failure")

    event.listen(app.state.engine, "before_cursor_execute", fail_after_some_inserts)
    try:
        with pytest.raises(ConnectionError):
            accept(app, h, synthetic_response(h))
    finally:
        event.remove(app.state.engine, "before_cursor_execute", fail_after_some_inserts)
    assert len(client.get(group_case["path"] + "/groups").json()["items"]) == 2
    assert run(client, group_case, h)["state"] == "running"
    assert accept(app, h, synthetic_response(h))["state"] == "completed"


def test_unknown_commit_is_readable_and_receipt_replay_does_not_duplicate(client, app, group_case):
    h = prepare(app, client, group_case)

    class Uncertain:
        @contextmanager
        def begin(self):
            with app.state.sessions.begin() as tx:
                yield tx
            raise ConnectionError("Lost COMMIT acknowledgement")

    with pytest.raises(ConnectionError):
        grouping.accept_grouping(Uncertain(), h["unit_id"], h["owner_token"], synthetic_response(h))
    assert run(client, group_case, h)["state"] == "completed"
    assert len(accept(app, h, synthetic_response(h))["group_ids"]) == 2


def test_http_isolation_cursor_and_authentication(client, app, group_case):
    h = prepare(app, client, group_case)
    accept(app, h, synthetic_response(h))
    app.state.settings.page_size = 1
    prefix = group_case["path"] + "/groups"
    page = client.get(prefix).json()
    assert len(page["items"]) == 1 and page["next_cursor"]
    second = client.get(prefix, params={"cursor": page["next_cursor"]}).json()
    assert len(second["items"]) == 1 and second["next_cursor"] is None
    assert second["items"][0]["id"] != page["items"][0]["id"]
    summary = page["items"][0]
    assert client.get(prefix + "/" + summary["id"]).headers["cache-control"] == "no-store"
    assert client.get(prefix, params={"cursor": "bad"}).status_code == 422
    assert client.get(prefix, params={"attempt_id": str(uuid4())}).json()["items"] == []
    assert (
        client.get(prefix + f"/{summary['id']}/states/{second['items'][0]['state_id']}").status_code
        == 404
    )
    other = project(client)
    assert client.get(f"/api/v1/projects/{other['id']}/groups/{summary['id']}").status_code == 404
    with TestClient(app, base_url=ORIGIN, headers={"Origin": ORIGIN}) as outsider:
        assert outsider.get(prefix).status_code == 401
        signup(outsider, "f2-outsider")
        signin(outsider, "f2-outsider")
        assert outsider.get(prefix).status_code == 404
        assert outsider.get(prefix + "/" + summary["id"]).status_code == 404
    with pytest.raises(AppError):
        prepare(
            app, client, group_case, finding_refs=[{"id": str(uuid4()), "state_id": str(uuid4())}]
        )
    alien = dict(group_case, project_id=UUID(other["id"]))
    with pytest.raises(AppError):
        prepare(app, client, alien)


def test_documents_previous_groups_and_late_human_state(client, app, group_case):
    doc = client.post(
        group_case["path"] + "/documents", json={"title": "Контекст", "text": "Документ 🙂"}
    ).json()
    h = prepare(
        app, client, group_case, document_refs=[{"id": doc["id"], "state_id": doc["state_id"]}]
    )
    out = synthetic_response(h)
    out["result"]["groups"][0]["context_keys"] = ["d1"]
    accept(app, h, out)
    with app.state.sessions() as tx:
        assert tx.scalar(select(func.count()).select_from(GroupContext)) == 1
    g = next(
        v
        for v in client.get(group_case["path"] + "/groups").json()["items"]
        if v["title"] == "Уведомления"
    )
    pending = prepare(
        app, client, group_case, previous_group_refs=[{"id": g["id"], "state_id": g["state_id"]}]
    )
    assert len(pending["request"]["input"]["previous_groups"]) == 1
    human_id = uuid4()
    with app.state.sessions.begin() as tx:
        tx.add(
            GroupState(
                id=human_id,
                project_id=group_case["project_id"],
                group_id=UUID(g["id"]),
                previous_state_id=UUID(g["state_id"]),
                title="Правка человека",
                summary="Сохранить",
                authorship="human",
                author_id=UUID(group_case["owner"]["id"]),
            )
        )
        tx.flush()
        # A human state still needs its own exact scope and members.
        for model in (GroupScope, GroupMember):
            for previous in tx.scalars(
                select(model).where(model.group_state_id == UUID(g["state_id"]))
            ):
                tx.add(
                    model(
                        project_id=group_case["project_id"],
                        group_state_id=human_id,
                        finding_id=previous.finding_id,
                        finding_state_id=previous.finding_state_id,
                    )
                )
            tx.flush()
        header = tx.get(FindingGroup, UUID(g["id"]))
        header.current_state_id = human_id
    assert accept(app, pending, synthetic_response(pending))["state"] == "cancelled"
    assert client.get(group_case["path"] + "/groups/" + g["id"]).json()["state_id"] == str(human_id)
    assert (
        client.get(group_case["path"] + f"/groups/{g['id']}/states/{g['state_id']}").json()["title"]
        == "Уведомления"
    )


def test_database_composite_foreign_keys(client, app, group_case):
    h = prepare(app, client, group_case)
    accept(app, h, synthetic_response(h))
    with app.state.sessions() as tx:
        states = tx.scalars(select(GroupState).order_by(GroupState.local_id)).all()
        conflict = tx.scalar(select(GroupConflict))
        pos = tx.scalar(select(ConflictPosition))
        member = tx.scalar(select(GroupMember).where(GroupMember.group_state_id == states[0].id))
        state1, state2 = states[0].id, states[1].id
        finding_id, conflict_id, position_id = member.finding_id, conflict.id, pos.id
    with pytest.raises(IntegrityError), app.state.sessions.begin() as tx:
        tx.add(
            ConflictPosition(
                project_id=group_case["project_id"],
                group_state_id=state2,
                conflict_id=conflict_id,
                ordinal=4,
                description="wrong group",
            )
        )
    with pytest.raises(IntegrityError), app.state.sessions.begin() as tx:
        tx.add(
            PositionMember(
                project_id=group_case["project_id"],
                group_state_id=state2,
                position_id=position_id,
                finding_id=finding_id,
                finding_state_id=finding_id,
            )
        )
    with pytest.raises(IntegrityError), app.state.sessions.begin() as tx:
        tx.execute(
            text("UPDATE finding_groups SET current_state_id=:s WHERE id=:g"),
            {"s": state2, "g": states[0].group_id},
        )
    other = project(client)
    with pytest.raises(IntegrityError), app.state.sessions.begin() as tx:
        tx.add(
            GroupingInput(
                project_id=UUID(other["id"]),
                unit_id=h["unit_id"],
                key="alien",
                finding_id=finding_id,
                finding_state_id=finding_id,
            )
        )
    with pytest.raises(IntegrityError), app.state.sessions.begin() as tx:
        tx.execute(
            text("UPDATE group_members SET finding_state_id=:s WHERE group_state_id=:g"),
            {"s": uuid4(), "g": state1},
        )


@pytest.mark.parametrize(
    "damage", ["no_group_members", "one_conflict_position", "no_position_members"]
)
def test_database_enforces_cross_row_cardinalities(client, app, group_case, damage):
    h = prepare(app, client, group_case)
    accept(app, h, synthetic_response(h))
    with pytest.raises(IntegrityError), app.state.sessions.begin() as tx:
        if damage == "no_group_members":
            state = tx.scalar(select(GroupState.id).where(GroupState.local_id == "g2"))
            tx.execute(text("DELETE FROM group_members WHERE group_state_id=:s"), {"s": state})
        elif damage == "one_conflict_position":
            position = tx.scalar(select(ConflictPosition.id).limit(1))
            tx.execute(text("DELETE FROM position_members WHERE position_id=:p"), {"p": position})
            tx.execute(text("DELETE FROM conflict_positions WHERE id=:p"), {"p": position})
        else:
            position = tx.scalar(select(ConflictPosition.id).limit(1))
            tx.execute(text("DELETE FROM position_members WHERE position_id=:p"), {"p": position})


def test_failure_is_technical_and_rejected_json_duplicate_keys(client, app, group_case):
    h = prepare(app, client, group_case)
    result = grouping.fail_grouping(
        app.state.sessions, h["unit_id"], h["owner_token"], "provider_not_configured"
    )
    assert result["state"] == "failed"
    receipt = run(client, group_case, h)["units"][0]["attempt"]
    assert receipt["coverage"] is None and receipt["grouping_result"] is None
    with pytest.raises(AppError):
        accept(app, h, synthetic_response(h))
    second = prepare(app, client, group_case)
    assert (
        accept(app, second, '{"coverage": [], "coverage": []}')["reason_code"] == "invalid_response"
    )


def test_contract_fixture_is_accepted():
    import json
    from pathlib import Path

    root = Path(__file__).parents[2] / "docs/contracts/ai/examples"
    for name in ("group_findings.valid", "group.conflict"):
        req = json.loads((root / f"{name}.request.json").read_text(encoding="utf-8"))
        out = json.loads((root / f"{name}.response.json").read_text(encoding="utf-8"))
        validation.accept(req, out)


def test_unknown_prepare_commit_replay_does_not_return_execution_capability(
    client, app, group_case
):
    key = uuid4()

    class Uncertain:
        @contextmanager
        def begin(self):
            with app.state.sessions.begin() as tx:
                yield tx
            raise ConnectionError("Lost prepare COMMIT acknowledgement")

    with pytest.raises(ConnectionError):
        grouping.prepare_grouping(
            Uncertain(),
            app.state.identity,
            client.cookies.get(app.state.settings.session_cookie),
            group_case["project_id"],
            key,
            group_case["refs"],
            provenance=grouping.Provenance("synthetic-test", "fixture-v1", True),
        )
    replay = prepare(app, client, group_case, command_key=key)
    assert replay["replayed"] and replay["request"] is None and replay["owner_token"] is None
    assert run(client, group_case, replay)["state"] == "running"


def test_final_ownership_check_rolls_back_publication(client, app, group_case):
    h = prepare(app, client, group_case)

    def expire_during_insert(conn, cursor, statement, parameters, context, executemany):
        if statement.startswith("INSERT INTO conflict_positions"):
            conn.execute(
                text(
                    "UPDATE stage_attempts SET lease_expires_at=clock_timestamp() "
                    "- interval '1 second' WHERE id=:a"
                ),
                {"a": h["attempt_id"]},
            )

    event.listen(app.state.engine, "before_cursor_execute", expire_during_insert)
    try:
        with pytest.raises(RuntimeError, match="ownership expired"):
            accept(app, h, synthetic_response(h))
    finally:
        event.remove(app.state.engine, "before_cursor_execute", expire_during_insert)
    assert client.get(group_case["path"] + "/groups").json()["items"] == []
    assert run(client, group_case, h)["state"] == "running"


def test_prepare_requires_current_session_and_unique_refs(client, app, group_case):
    with pytest.raises(AppError) as failure:
        grouping.prepare_grouping(
            app.state.sessions,
            app.state.identity,
            "invalid-session-token",
            group_case["project_id"],
            uuid4(),
            group_case["refs"],
            provenance=grouping.Provenance("synthetic-test", "fixture-v1", True),
        )
    assert failure.value.status == 401
    with pytest.raises(AppError) as failure:
        prepare(app, client, group_case, finding_refs=[group_case["refs"][0]] * 2)
    assert failure.value.status == 422
    key = uuid4()
    first = prepare(app, client, group_case, command_key=key)
    replay = prepare(
        app, client, group_case, command_key=key, finding_refs=list(reversed(group_case["refs"]))
    )
    assert first["run_id"] == replay["run_id"]


def test_changed_document_cancels_pending_receipt_and_marks_saved_group_stale(
    client, app, group_case
):
    from feedback2req.persistence.models import DocumentState, ProductDocument

    doc = client.post(
        group_case["path"] + "/documents", json={"title": "Контекст", "text": "v1"}
    ).json()
    refs = [{"id": doc["id"], "state_id": doc["state_id"]}]
    first = prepare(app, client, group_case, document_refs=refs)
    out = synthetic_response(first)
    out["result"]["groups"][0]["context_keys"] = ["d1"]
    accept(app, first, out)
    pending = prepare(app, client, group_case, document_refs=refs)
    with app.state.sessions.begin() as tx:
        header = tx.get(ProductDocument, UUID(doc["id"]))
        changed = DocumentState(
            id=uuid4(),
            project_id=group_case["project_id"],
            document_id=header.id,
            text="v2",
            title="Контекст",
            author_id=UUID(group_case["owner"]["id"]),
            origin="human",
        )
        tx.add(changed)
        tx.flush()
        header.current_state_id = changed.id
    assert accept(app, pending, synthetic_response(pending))["reason_code"] == "input_changed"
    saved = client.get(group_case["path"] + "/groups").json()["items"]
    target = next(g for g in saved if g["title"] == "Уведомления")
    assert target["freshness"] == "requires_update"
    detail = client.get(group_case["path"] + "/groups/" + target["id"]).json()
    assert detail["context"][0]["ref"]["state_id"] == doc["state_id"]


def test_previous_group_preserves_questions_about_considered_nonmembers(client, app, group_case):
    h = prepare(app, client, group_case)
    out = synthetic_response(h)
    out["questions"][0]["related"] = [{"origin": "input", "key": "f3"}]
    accept(app, h, out)
    summary = next(
        g
        for g in client.get(group_case["path"] + "/groups").json()["items"]
        if g["title"] == "Уведомления"
    )
    next_handle = prepare(
        app,
        client,
        group_case,
        previous_group_refs=[
            {"id": summary["id"], "state_id": summary["state_id"]},
        ],
    )
    previous = next_handle["request"]["input"]["previous_groups"][0]
    assert previous["open_questions"][0]["text"] == out["questions"][0]["text"]
    assert previous["open_questions"][0]["blocking"] is True


@pytest.mark.parametrize("action", ["renew", "fail"])
def test_internal_finalization_after_access_revocation(client, app, group_case, action):
    member = signup(client, "f2-revoked-worker")
    client.put(group_case["path"] + "/access/" + member["id"], json={"can_approve": False})
    signin(client, "f2-revoked-worker")
    h = prepare(app, client, group_case)
    with app.state.sessions.begin() as tx:
        tx.delete(tx.get(ProjectAccess, (group_case["project_id"], UUID(member["id"]))))
    if action == "renew":
        assert grouping.renew_grouping(app.state.sessions, h["unit_id"], h["owner_token"]) is False
    else:
        result = grouping.fail_grouping(
            app.state.sessions, h["unit_id"], h["owner_token"], "provider_error"
        )
        assert result["state"] == "cancelled"
    signin(client, "f2-owner")
    receipt = run(client, group_case, h)["units"][0]["attempt"]
    assert receipt["reason_code"] == "access_revoked"
    assert receipt["grouping_result"] is None


def test_database_rejects_foreign_finding_independently_of_unit_project(client, app, group_case):
    h = prepare(app, client, group_case)
    other = project(client)
    path = f"/api/v1/projects/{other['id']}"
    source = client.post(path + "/sources", json={"kind": "text", "text": "Чужой проект"}).json()
    start(client, path, source)
    service.execute_one(app.state.sessions, app.state.settings, Synthetic())
    foreign = client.get(path + "/findings").json()["items"][0]
    with pytest.raises(IntegrityError), app.state.sessions.begin() as tx:
        tx.add(
            GroupingInput(
                project_id=group_case["project_id"],
                unit_id=h["unit_id"],
                key="foreign",
                finding_id=UUID(foreign["id"]),
                finding_state_id=UUID(foreign["state_id"]),
            )
        )


def test_document_range_canonicalization_rejects_aliases():
    ref = {"id": str(uuid4()), "state_id": str(uuid4())}
    with pytest.raises(AppError) as failure:
        grouping.normalized(
            [
                ref | {"locator": {"start": 0, "end": 10}},
                ref | {"locator": {"end": 10, "start": 0}},
            ],
            "product_document",
            documents=True,
        )
    assert failure.value.status == 422
