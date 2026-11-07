"""Optional real-model F2 path, disabled unless specifically authorized/configured."""

import json
import os
from pathlib import Path

import pytest
from backend.tests.test_grouping import group_case as group_case  # noqa: PLC0414 -- pytest fixture re-export.
from backend.tests.test_grouping_execution import execute

from experiments.qwen.f2_provider import F2LocalProvider
from experiments.qwen.portable import resources
from experiments.qwen.run import write


@pytest.mark.skipif(
    os.environ.get("F2R_QWEN_LIVE") != "approved-synthetic",
    reason="Real runtime/weights/data transfer not authorized or configured",
)
def test_live_qwen_component_accept_and_saved_read(client, app, group_case):
    cfg = json.loads(Path(os.environ["F2R_QWEN_CONFIG"]).read_text("utf-8"))
    lock = json.loads(Path(os.environ["F2R_QWEN_LOCK"]).read_text("utf-8"))
    hardware = resources()
    if cfg["model"].startswith("qwen3.5:") and not (
        hardware["qwen35_9b_gpu_candidate"] or hardware["qwen35_9b_cpu_candidate"]
    ):
        pytest.fail("9B hardware gate failed; inference was not started")
    provider = F2LocalProvider(
        cfg, lock, os.environ["F2R_QWEN_OUTPUT"], approved=True, synthetic_data=True
    )
    write(provider.output / "resource-preflight.json", hardware)
    receipt = execute(app, client, group_case, provider)
    run = client.get(group_case["path"] + "/runs/" + str(receipt["run_id"])).json()
    groups = [
        client.get(group_case["path"] + "/groups/" + str(key)).json()
        for key in receipt["result"].get("group_ids", [])
    ]
    write(
        provider.output / "f2-readback.json",
        {
            "run": run,
            "groups": groups,
            "semantic_review": "pending_preliminary",
            "synthetic_input": True,
        },
    )
    # Technical acceptance is measured, never forced by changing the response.
    assert receipt["result"]["state"] == "completed"
    attempt = run["units"][0]["attempt"]
    assert attempt["synthetic"] is False and attempt["ai_performed"] is True
    for group in groups:
        assert (
            client.get(
                group_case["path"] + f"/groups/{group['id']}/states/{group['state_id']}"
            ).json()
            == group
        )
