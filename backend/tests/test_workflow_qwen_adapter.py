"""Current integrated F2 with a synthetic research transport, never real Qwen.

The original research suite retains its pinned 4c62684 reference guard. This
separate integration check exercises the actual checkout without changing it.
"""

import pytest
from experiments.qwen.f2_checks.test_f2_path import SyntheticTransport

from .test_grouping import group_case as group_case
from .test_grouping_execution import execute


@pytest.mark.parametrize("profile", ["product", "experimental"])
def test_qwen_transport_with_integrated_group_storage(client, app, group_case, profile):
    provider = SyntheticTransport(profile)
    receipt = execute(app, client, group_case, provider)
    assert receipt["result"]["state"] == "completed"
    run = client.get(group_case["path"] + "/runs/" + str(receipt["run_id"])).json()
    attempt = run["units"][0]["attempt"]
    assert attempt["synthetic"] is True and attempt["ai_performed"] is False
    assert len(attempt["coverage"]) == 3
    assert len(attempt["grouping_result"]["ungrouped_findings"]) == 1
    assert len(provider.messages) == 1
    groups = [
        client.get(group_case["path"] + "/groups/" + str(identity)).json()
        for identity in attempt["grouping_result"]["group_ids"]
    ]
    assert len(groups) == 2
    members = [{item["ref"]["id"] for item in group["members"]} for group in groups]
    assert len(members[0] & members[1]) == 1
    assert sum(len(group["conflicts"]) for group in groups) == 1
    for group in groups:
        exact = client.get(
            group_case["path"] + f"/groups/{group['id']}/states/{group['state_id']}"
        ).json()
        assert exact == group
        for item in group["members"]:
            assert item["ref"]["state_id"] == item["finding"]["state_id"]
            assert item["finding"]["evidence"]
