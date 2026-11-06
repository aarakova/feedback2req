"""Approved previous-group annotation targets: exact refs, PG isolation and HTTP."""

from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from feedback2req.errors import AppError
from feedback2req.persistence.grouping import (
    FindingGroup,
    GroupingPreviousGroup,
    GroupMember,
    GroupScope,
    GroupState,
)
from feedback2req.persistence.models import ProjectAccess
from feedback2req.persistence.processing import Attempt, Run
from feedback2req.processing import service

from .conftest import project, signin, signup
from .test_grouping import accept, prepare, run, synthetic_response
from .test_grouping import group_case as group_case
from .test_processing import Synthetic, start


@pytest.fixture
def saved_groups(client, app, group_case):
    handle = prepare(app, client, group_case)
    assert accept(app, handle, synthetic_response(handle))["state"] == "completed"
    details = [
        client.get(group_case["path"] + "/groups/" + item["id"]).json()
        for item in client.get(group_case["path"] + "/groups").json()["items"]
    ]
    return sorted(details, key=lambda item: not bool(item["conflicts"]))


def previous_ref(group):
    return {"id": group["id"], "state_id": group["state_id"]}


def previous_response(handle, kind):
    response = synthetic_response(handle)
    response[kind][0]["related"] = [
        {"origin": "input", "key": handle["request"]["input"]["previous_groups"][0]["key"]}
    ]
    return response


def advance_group(app, case, group):
    """Simulate a later human state directly in PG; no human-write API added."""
    state_id = uuid4()
    with app.state.sessions.begin() as tx:
        tx.add(
            GroupState(
                id=state_id,
                project_id=case["project_id"],
                group_id=UUID(group["id"]),
                previous_state_id=UUID(group["state_id"]),
                title="Later human state",
                summary="Existing annotations must keep the selected historical state",
                authorship="human",
                author_id=UUID(case["owner"]["id"]),
            )
        )
        tx.flush()
        for model in (GroupScope, GroupMember):
            for prior in tx.scalars(
                select(model).where(model.group_state_id == UUID(group["state_id"]))
            ).all():
                tx.add(
                    model(
                        project_id=case["project_id"],
                        group_state_id=state_id,
                        finding_id=prior.finding_id,
                        finding_state_id=prior.finding_state_id,
                    )
                )
            tx.flush()
        tx.get(FindingGroup, UUID(group["id"])).current_state_id = state_id
    return str(state_id)


@pytest.mark.parametrize("kind", ["questions", "uncertainties"])
def test_annotations_bind_mixed_origins_and_keep_history(
    client, app, group_case, saved_groups, kind
):
    previous = saved_groups[0]
    handle = prepare(app, client, group_case, previous_group_refs=[previous_ref(previous)])
    response = previous_response(handle, kind)
    # Input g1 and output g1 deliberately have the same local key.
    response[kind][0]["related"] += [
        {"origin": "input", "key": "f1"},
        {"origin": "output", "key": "g1"},
    ]
    result = accept(app, handle, response)
    assert result["state"] == "completed"
    receipt = run(client, group_case, handle)
    assert receipt["units"][0]["input"]["previous_groups"] == [
        {"kind": "finding_group", **previous_ref(previous)}
    ]
    annotations = receipt["units"][0]["attempt"]["annotations"]
    links = annotations[kind][0]["related"]
    assert links[0] == {
        "origin": "input",
        "key": "g1",
        "kind": "finding_group",
        **previous_ref(previous),
    }
    finding = handle["request"]["input"]["findings"][0]["ref"]
    assert links[1] == {"origin": "input", "key": "f1", **finding}
    output = next(
        client.get(group_case["path"] + "/groups/" + str(identity)).json()
        for identity in result["group_ids"]
        if client.get(group_case["path"] + "/groups/" + str(identity)).json()["conflicts"]
    )
    assert links[2] == {
        "origin": "output",
        "key": "g1",
        "kind": "finding_group",
        **previous_ref(output),
    }
    assert output["annotations"] == annotations
    for group in saved_groups:
        assert client.get(group_case["path"] + "/groups/" + group["id"]).json() == group
    # A receipt replay does not close the old questions or alter either group.
    assert accept(app, handle, response) == result
    assert run(client, group_case, handle)["units"][0]["attempt"]["annotations"] == annotations
    later_id = advance_group(app, group_case, previous)
    historical = client.get(
        group_case["path"] + f"/groups/{previous['id']}/states/{previous['state_id']}"
    ).json()
    assert historical == previous
    assert (
        client.get(group_case["path"] + "/groups/" + previous["id"]).json()["state_id"] == later_id
    )
    # Both Run and an exact output-state GET retain the old input state id.
    assert run(client, group_case, handle)["units"][0]["attempt"]["annotations"] == annotations
    output_path = group_case["path"] + f"/groups/{output['id']}/states/{output['state_id']}"
    assert client.get(output_path).json()["annotations"] == annotations
    assert client.get(output_path).json()["freshness"] == "requires_update"


@pytest.mark.parametrize("kind", ["questions", "uncertainties"])
@pytest.mark.parametrize("target", ["unpassed_key", "unpassed_id", "state_id"])
def test_annotations_cannot_auto_load_groups(client, app, group_case, saved_groups, kind, target):
    handle = prepare(app, client, group_case, previous_group_refs=[previous_ref(saved_groups[0])])
    response = previous_response(handle, kind)
    key = {
        "unpassed_key": "g2",  # Also a valid output key; input must not resolve it.
        "unpassed_id": saved_groups[1]["id"],
        "state_id": saved_groups[0]["state_id"],
    }[target]
    response[kind][0]["related"][0]["key"] = key
    assert accept(app, handle, response)["reason_code"] == "invalid_response"
    attempt = run(client, group_case, handle)["units"][0]["attempt"]
    assert attempt["annotations"] is None and attempt["coverage"] is None
    with app.state.sessions() as tx:
        assert tx.scalar(select(func.count()).select_from(FindingGroup)) == 2
    for group in saved_groups:
        assert client.get(group_case["path"] + "/groups/" + group["id"]).json() == group


@pytest.mark.parametrize(
    "damage", ["missing_group", "missing_state", "other_group_state", "stale_state"]
)
def test_prepare_rejects_wrong_previous_states(client, app, group_case, saved_groups, damage):
    group = saved_groups[0]
    ref = previous_ref(group)
    if damage == "missing_group":
        ref["id"] = str(uuid4())
    elif damage == "missing_state":
        ref["state_id"] = str(uuid4())
    elif damage == "other_group_state":
        ref["state_id"] = saved_groups[1]["state_id"]
    else:
        advance_group(app, group_case, group)
    with app.state.sessions() as tx:
        runs = tx.scalar(select(func.count()).select_from(Run))
    with pytest.raises(AppError) as caught:
        prepare(app, client, group_case, previous_group_refs=[ref])
    assert caught.value.code == ("input_changed" if damage == "stale_state" else "not_found")
    with app.state.sessions() as tx:
        assert tx.scalar(select(func.count()).select_from(Run)) == runs
    if damage != "stale_state":
        assert (
            client.get(
                group_case["path"] + f"/groups/{ref['id']}/states/{ref['state_id']}"
            ).status_code
            == 404
        )


@pytest.mark.parametrize("kind", ["questions", "uncertainties"])
def test_changed_previous_context_cancels_publication(client, app, group_case, saved_groups, kind):
    group = saved_groups[0]
    handle = prepare(app, client, group_case, previous_group_refs=[previous_ref(group)])
    response = previous_response(handle, kind)
    advance_group(app, group_case, group)
    result = accept(app, handle, response)
    assert result["state"] == "cancelled" and result["reason_code"] == "input_changed"
    assert run(client, group_case, handle)["units"][0]["attempt"]["annotations"] is None


@pytest.mark.parametrize("kind", ["questions", "uncertainties"])
def test_previous_annotations_do_not_bypass_revoked_access(
    client, app, group_case, saved_groups, kind
):
    member = signup(client, "previous-group-member")
    client.put(group_case["path"] + "/access/" + member["id"], json={"can_approve": False})
    signin(client, "previous-group-member")
    handle = prepare(app, client, group_case, previous_group_refs=[previous_ref(saved_groups[0])])
    with app.state.sessions.begin() as tx:
        tx.delete(tx.get(ProjectAccess, (group_case["project_id"], UUID(member["id"]))))
    result = accept(app, handle, previous_response(handle, kind))
    assert result["state"] == "cancelled" and result["reason_code"] == "access_revoked"
    assert client.get(group_case["path"] + "/runs/" + str(handle["run_id"])).status_code == 404
    signin(client, "f2-owner")
    assert run(client, group_case, handle)["units"][0]["attempt"]["annotations"] is None


def test_previous_group_from_another_project_is_rejected(client, app, group_case, saved_groups):
    other = project(client)
    path = f"/api/v1/projects/{other['id']}"
    source = client.post(path + "/sources", json={"kind": "text", "text": "Other project"}).json()
    assert start(client, path, source).status_code == 202
    assert service.execute_one(app.state.sessions, app.state.settings, Synthetic())
    findings = client.get(path + "/findings").json()["items"]
    case = {"project_id": UUID(other["id"]), "refs": [previous_ref(f) for f in findings]}
    # The actor can access both projects; project scope must still reject the group.
    with pytest.raises(AppError) as caught:
        prepare(app, client, case, previous_group_refs=[previous_ref(saved_groups[0])])
    assert caught.value.code == "not_found"
    assert client.get(path + "/groups/" + saved_groups[0]["id"]).status_code == 404


@pytest.mark.parametrize("damage", ["other_group_state", "foreign_project"])
def test_previous_group_composite_fk_is_enforced_by_postgres(
    client, app, group_case, saved_groups, damage
):
    handle = prepare(app, client, group_case)
    ref = previous_ref(saved_groups[0])
    if damage == "other_group_state":
        ref["state_id"] = saved_groups[1]["state_id"]
        project_id = group_case["project_id"]
    else:
        project_id = UUID(project(client)["id"])
    with pytest.raises(IntegrityError), app.state.sessions.begin() as tx:
        tx.add(
            GroupingPreviousGroup(
                project_id=project_id,
                unit_id=handle["unit_id"],
                key="g1",
                group_id=UUID(ref["id"]),
                group_state_id=UUID(ref["state_id"]),
            )
        )
    with app.state.sessions() as tx:
        assert tx.get(Attempt, handle["attempt_id"]).annotations is None
