"""Real saved F1/F2 DTOs with synthetic sources; no production exporter or verifier."""

from copy import deepcopy
from uuid import UUID

import pytest
from ai.formal_expectations import Limits
from ai.formal_expectations_bridge import Verification, check_pair, fingerprint, prepare
from ai.formal_expectations_bridge.compatibility import audit_saved_inputs
from ai.formal_expectations_bridge.synthetic import base
from backend.tests.conftest import project, signin, signup
from backend.tests.test_grouping import (
    accept,
    run,
    synthetic_response,
)
from backend.tests.test_grouping import (
    prepare as prepare_grouping,
)
from backend.tests.test_processing import Synthetic, start
from feedback2req.persistence.models import ProjectAccess
from feedback2req.processing import service
from sqlalchemy import delete


@pytest.fixture
def saved_case(app, client):
    signup(client, "formal-c-owner")
    signin(client, "formal-c-owner")
    p = project(client)
    path = f"/api/v1/projects/{p['id']}"
    sources = []

    def extract(request, response):
        response["result"]["findings"][0]["text"] = request["input"]["segments"][0]["text"]

    for value in (
        "Между сеансами сохраняйте фильтры. 🙂",
        "Между сеансами сбрасывайте фильтры. 🙂",
        "Другой запрос к продукту.",
    ):
        result = client.post(path + "/sources", json={"kind": "text", "text": value})
        assert result.status_code == 201
        sources.append(result.json())
        assert start(client, path, sources[-1]).status_code == 202
        assert service.execute_one(app.state.sessions, app.state.settings, Synthetic(extract))
    findings = client.get(path + "/findings").json()["items"]
    # Explicit order chosen from actual source provenance, not API list order.
    findings = sorted(
        findings,
        key=lambda f: next(
            i for i, s in enumerate(sources) if f["evidence"][0]["source_ref"]["id"] == s["id"]
        ),
    )
    case = {
        "project_id": UUID(p["id"]),
        "path": path,
        "refs": [{"id": f["id"], "state_id": f["state_id"]} for f in findings],
    }
    handle = prepare_grouping(app, client, case)
    response = synthetic_response(handle)
    keys = {f["text"]: f for f in handle["request"]["input"]["findings"]}
    selected_keys = [keys[s["text"]]["key"] for s in sources[:2]]
    group = response["result"]["groups"][0]
    group["finding_keys"] = selected_keys
    for pos, key in zip(group["conflicts"][0]["positions"], selected_keys, strict=True):
        pos["finding_keys"] = [key]
    other = response["result"]["groups"][1]
    other["finding_keys"] = other["considered_keys"] = [selected_keys[0]]
    response["result"]["ungrouped_finding_keys"] = [keys[sources[2]["text"]]["key"]]
    assert accept(app, handle, response)["state"] == "completed"
    details = []
    for group in client.get(path + "/groups").json()["items"]:
        exact = client.get(path + f"/groups/{group['id']}/states/{group['state_id']}")
        assert exact.status_code == 200
        details.append(exact.json())
    # Test curator registers known associations for this controlled fixture only.
    # This is deliberately not a production mapping reconstruction algorithm.
    bindings = []
    for candidate in response["result"]["groups"]:
        chosen = next(g for g in details if g["title"] == candidate["title"])
        bindings.append(
            {
                "local_id": candidate["local_id"],
                "ref": {
                    "kind": "finding_group",
                    "id": chosen["id"],
                    "state_id": chosen["state_id"],
                },
                "conflicts": [{"local_id": "c1", "id": chosen["conflicts"][0]["id"]}]
                if chosen["conflicts"]
                else [],
            }
        )
    data = base()
    data["grouping_request"], data["grouping_response"] = handle["request"], response
    # Atom sources are explicitly selected by their known fixture statements.
    for index, source in enumerate(sources[:2]):
        finding = keys[source["text"]]
        data["proposal"]["atoms"][index]["sources"] = [
            {
                "finding_key": finding["key"],
                "finding_ref": deepcopy(finding["ref"]),
                "evidence_keys": [e["fragment_key"] for e in finding["evidence"]],
            }
        ]
    # Explicit selected positions remain independent of canonical key allocation.
    positions = response["result"]["groups"][0]["conflicts"][0]["positions"]
    data["selection"]["left_finding_keys"] = positions[0]["finding_keys"]
    data["selection"]["right_finding_keys"] = positions[1]["finding_keys"]
    saved = {
        "findings": findings,
        "groups": details,
        "sources": sources,
        "group_bindings": bindings,
    }
    return data, saved, case, handle


def test_saved_inputs_match_and_original_run_is_completed(saved_case, app, client):
    data, saved, case, handle = saved_case
    result = audit_saved_inputs(data, saved)
    assert result.status == "matched", result.to_dict()
    assert result.verification_created is False and result.classification is None
    assert prepare(data).status == "prepared"
    assert check_pair(data, verify=None).status == "verification_required"
    assert run(client, case, handle)["state"] == "completed"
    assert saved["findings"][0]["evidence"][0]["source_ref"]["state_id"]


def test_groupdetail_does_not_reconstruct_canonical_or_mapping(saved_case):
    data, saved, _, _ = saved_case
    saved["group_bindings"] = []
    result = audit_saved_inputs(data, saved)
    assert result.status == "missing" and result.classification is None
    assert audit_saved_inputs(saved["groups"][0], saved).status == "preparation_required"


@pytest.mark.parametrize("damage", ["quote", "source_state", "member_state", "partial_position"])
def test_wrong_saved_states_and_basis_cannot_confirm(saved_case, damage):
    data, saved, _, _ = saved_case
    if damage == "quote":
        saved["sources"][0]["text"] = "x" * len(saved["sources"][0]["text"])
    elif damage == "source_state":
        saved["sources"][0]["state_id"] = saved["sources"][1]["state_id"]
    elif damage == "member_state":
        group = next(g for g in saved["groups"] if g["conflicts"])
        group["members"][0]["ref"]["state_id"] = saved["sources"][0]["state_id"]
    else:
        group = next(g for g in saved["groups"] if g["conflicts"])
        positions = group["conflicts"][0]["positions"]
        positions[0]["findings"] = deepcopy(positions[1]["findings"])
    result = audit_saved_inputs(data, saved)
    expected = (
        "invalid_input"
        if damage == "member_state"
        else "mismatch"
        if damage in ("quote", "partial_position")
        else "missing"
    )
    assert result.status == expected, result.to_dict()
    assert result.verification_created is False


def test_conditional_Z3_failure_does_not_change_completed_grouping(saved_case, client):
    data, saved, case, handle = saved_case
    prepared = prepare(data)
    expected = fingerprint(prepared.packet)

    def test_only_review(packet):
        assert fingerprint(packet) == expected
        assert audit_saved_inputs(data, saved).status == "matched"
        # Explicit engineering test approval of this immutable synthetic structure.
        # No public/runtime verifier is registered and no source meaning is claimed.
        return Verification(
            expected,
            "isolated-test-curator",
            "Exact synthetic structure only",
            True,
            True,
            True,
            True,
            True,
        )

    checked = check_pair(data, verify=test_only_review)
    assert checked.status == "checked" and checked.formal_result["classification"] == "K"
    failed = check_pair(data, verify=test_only_review, limits=Limits(solver_rlimit=1))
    assert failed.status == "formal_failure"
    assert failed.formal_result["classification"] is None
    assert run(client, case, handle)["state"] == "completed"


def test_cached_matching_DTO_does_not_prove_current_access(saved_case, app, client):
    data, saved, case, _ = saved_case
    assert audit_saved_inputs(data, saved).status == "matched"
    member = signup(client, "formal-c-member")
    member_id = UUID(member["id"])
    with app.state.sessions.begin() as tx:
        tx.add(ProjectAccess(project_id=case["project_id"], user_id=member_id, can_approve=False))
    signin(client, "formal-c-member")
    group = saved["groups"][0]
    exact_path = case["path"] + f"/groups/{group['id']}/states/{group['state_id']}"
    assert client.get(exact_path).status_code == 200
    with app.state.sessions.begin() as tx:
        tx.execute(
            delete(ProjectAccess).where(
                ProjectAccess.project_id == case["project_id"], ProjectAccess.user_id == member_id
            )
        )
    assert client.get(exact_path).status_code == 404
    # Offline hashes and a cached matched report do not bypass application access.
    assert (
        "current_access_and_source_availability_revalidation"
        in audit_saved_inputs(data, saved).outstanding_gates
    )
    assert check_pair(data, verify=None).formal_result is None
