"""Real PG/F2/component path; explicitly synthetic HTTP transport, never inference."""

import json

import pytest
from backend.tests.test_grouping import group_case as group_case  # noqa: PLC0414 -- pytest fixture re-export.
from backend.tests.test_grouping import synthetic_response
from backend.tests.test_grouping_execution import execute
from backend.tests.test_grouping_previous_annotations import advance_group
from feedback2req.persistence.grouping import FindingGroup
from sqlalchemy import func, select

from experiments.qwen.adapter import ExperimentalOllama
from experiments.qwen.portable import matrix


class SyntheticTransport:
    name, model, synthetic = "synthetic_ollama_transport", "none", True

    def __init__(self, profile="experimental", transform=None):
        self.cfg = matrix()["qwen35-9b-" + profile + "-matched"]
        self.transform = transform
        self.messages = []
        self.adapter = ExperimentalOllama(
            self.cfg, enabled=True, transport=self.transport
        )

    def transport(self, path, body, timeout, limit):
        assert path == "/api/chat"
        self.messages.append(body["messages"])
        request = json.loads(body["messages"][1]["content"])
        response = synthetic_response({"request": request})
        if self.transform:
            self.transform(request, response)
        return json.dumps(
            {
                "model": self.cfg["model"],
                "done": True,
                "done_reason": "stop",
                "prompt_eval_count": 1000,
                "message": {"role": "assistant", "content": json.dumps(response)},
            }
        ).encode()

    def group(self, request):
        return self.adapter.group(request)


@pytest.mark.parametrize("profile", ["product", "experimental"])
def test_adapter_component_f2_storage_and_read(client, app, group_case, profile):
    provider = SyntheticTransport(profile)
    receipt = execute(app, client, group_case, provider)
    assert receipt["result"]["state"] == "completed"
    attempt = client.get(group_case["path"] + "/runs/" + str(receipt["run_id"])).json()[
        "units"
    ][0]["attempt"]
    assert attempt["synthetic"] is True and attempt["ai_performed"] is False
    assert len(attempt["coverage"]) == 3
    assert (
        attempt["annotations"]["questions"] and attempt["annotations"]["uncertainties"]
    )
    assert len(attempt["grouping_result"]["ungrouped_findings"]) == 1
    groups = [
        client.get(group_case["path"] + "/groups/" + str(key)).json()
        for key in receipt["result"]["group_ids"]
    ]
    assert len(groups) == 2
    memberships = [{item["ref"]["id"] for item in group["members"]} for group in groups]
    assert len(memberships[0] & memberships[1]) == 1
    assert sum(len(group["conflicts"]) for group in groups) == 1
    conflict = next(group["conflicts"][0] for group in groups if group["conflicts"])
    assert len(conflict["positions"]) == 2
    for group in groups:
        exact = client.get(
            group_case["path"] + f"/groups/{group['id']}/states/{group['state_id']}"
        ).json()
        assert exact == group
        for item in group["members"]:
            assert item["ref"]["state_id"] == item["finding"]["state_id"]
            assert item["finding"]["evidence"][0]["source_ref"]["state_id"] in {
                s["state_id"] for s in group_case["sources"]
            }


@pytest.mark.parametrize("annotation", ["questions", "uncertainties"])
def test_previous_group_annotations_keep_exact_history(
    client, app, group_case, annotation
):
    first = execute(app, client, group_case, SyntheticTransport())
    key = first["result"]["group_ids"][0]
    previous = client.get(group_case["path"] + "/groups/" + str(key)).json()

    def annotate(request, response):
        response[annotation][0]["related"] = [
            {"origin": "input", "key": request["input"]["previous_groups"][0]["key"]}
        ]

    second = execute(
        app,
        client,
        group_case,
        SyntheticTransport(transform=annotate),
        previous_group_refs=[{"id": previous["id"], "state_id": previous["state_id"]}],
    )
    assert second["result"]["state"] == "completed"
    path = group_case["path"] + "/runs/" + str(second["run_id"])
    annotations = client.get(path).json()["units"][0]["attempt"]["annotations"]
    link = annotations[annotation][0]["related"][0]
    assert link["kind"] == "finding_group" and link["state_id"] == previous["state_id"]
    advance_group(app, group_case, previous)
    assert client.get(path).json()["units"][0]["attempt"]["annotations"] == annotations
    assert (
        client.get(
            group_case["path"]
            + f"/groups/{previous['id']}/states/{previous['state_id']}"
        ).json()
        == previous
    )


@pytest.mark.parametrize(
    "damage",
    ["unknown_member", "duplicate_position", "annotation_fragment", "nul_string"],
)
def test_invalid_output_has_no_partial_publication(client, app, group_case, damage):
    def corrupt(request, response):
        if damage == "unknown_member":
            response["result"]["groups"][1]["finding_keys"] = ["unknown"]
        elif damage == "duplicate_position":
            positions = response["result"]["groups"][0]["conflicts"][0]["positions"]
            positions[1] = dict(positions[0])
        elif damage == "annotation_fragment":
            response["uncertainties"][0]["related"] = [
                {"origin": "input", "key": request["input"]["fragments"][0]["key"]}
            ]
        else:
            response["result"]["groups"][1]["title"] = "invalid\x00title"

    receipt = execute(app, client, group_case, SyntheticTransport(transform=corrupt))
    assert receipt["result"]["state"] == "failed"
    assert receipt["result"]["reason_code"] == "invalid_response"
    attempt = client.get(group_case["path"] + "/runs/" + str(receipt["run_id"])).json()[
        "units"
    ][0]["attempt"]
    assert attempt["coverage"] is None and attempt["grouping_result"] is None
    assert attempt["synthetic"] is True and attempt["ai_performed"] is False
    with app.state.sessions() as tx:
        assert tx.scalar(select(func.count()).select_from(FindingGroup)) == 0
