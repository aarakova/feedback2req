"""Owned synthetic F2/F3 fixtures; run before starting this project's worker.

No public grouping POST is invented. Historical human states are ORM fixtures,
not evidence of a supported human-write API. Queued work is left to the real worker.
"""

import json
import os
from pathlib import Path
from uuid import UUID, uuid4

import httpx
from feedback2req.config import Settings
from feedback2req.grouping.execution import execute_grouping
from feedback2req.grouping.provider import SyntheticGrouping
from feedback2req.grouping.service import enqueue_grouping
from feedback2req.main import create_app
from feedback2req.processing import service
from sqlalchemy.engine import make_url

from backend.tests.test_grouping_previous_annotations import advance_group
from backend.tests.test_processing import Synthetic

raw = os.environ["F2R_DATABASE_URL"]
assert make_url(raw).database == "feedback2req_processing_f1_test"
app = create_app(Settings(database_url=raw, local_http=True, processing_test_mode=True))
login = "groups-fixture-" + uuid4().hex
credentials = {"login": login, "password": "frontend-test-only-2026"}
origin = os.environ.get("F1_TEST_ORIGIN", "http://localhost:18080")
with httpx.Client(
    base_url=os.environ["F1_TEST_API"], headers={"Origin": origin}, trust_env=False
) as client:
    assert client.post("/api/v1/auth/register", json=credentials).status_code == 201
    session = client.post("/api/v1/auth/session", json=credentials).json()
    client.headers["X-CSRF-Token"] = session["csrf_token"]
    project = client.post(
        "/api/v1/projects", json={"name": "СИНТЕТИЧЕСКИЙ ТЕСТ · группы и позиции"}
    ).json()
    project_id = UUID(project["id"])
    root = "/api/v1/projects/" + project["id"]
    refs = []
    for text in [
        "СИНТЕТИЧЕСКИЙ ТЕСТ: отправлять автоматически ё🙂\r\n",
        "СИНТЕТИЧЕСКИЙ ТЕСТ: отправлять только после подтверждения",
        "СИНТЕТИЧЕСКИЙ ТЕСТ: отдельное ожидание",
    ]:
        source = client.post(root + "/sources", json={"kind": "text", "text": text}).json()
        response = client.post(
            root + "/runs",
            headers={"Idempotency-Key": str(uuid4())},
            json={
                "operation": "extract_feedback",
                "inputs": [{"kind": "source", "id": source["id"], "state_id": source["state_id"]}],
            },
        )
        assert response.status_code == 202
        assert service.execute_one(app.state.sessions, app.state.settings, Synthetic())
        run = client.get(root + "/runs/" + response.json()["id"]).json()
        assert run["state"] == "completed"
        identity = run["units"][0]["attempt"]["finding_ids"][0]
        refs.append({"kind": "finding", "id": identity, "state_id": identity})
    token = client.cookies.get(app.state.settings.session_cookie)

    class Annotated(SyntheticGrouping):
        def group(self, request):
            value = json.loads(super().group(request))
            value["questions"] = [
                {
                    "local_id": "q",
                    "text": "Синтетический вопрос группировки",
                    "reason": "Уточнить условия применения",
                    "blocking": True,
                    "related": [{"origin": "input", "key": request["input"]["findings"][0]["key"]}],
                }
            ]
            return json.dumps(value)

    result = execute_grouping(
        app.state.sessions,
        app.state.identity,
        token,
        project_id,
        uuid4(),
        refs,
        provider=Annotated("many"),
    )
    assert result["result"]["state"] == "completed"
    groups = [
        client.get(root + "/groups/" + str(identity)).json()
        for identity in result["result"]["group_ids"]
    ]
    historical = next(group for group in groups if group["conflicts"])
    current_state = advance_group(
        app, {"project_id": project_id, "owner": session["user"]}, historical
    )
    empty = execute_grouping(
        app.state.sessions,
        app.state.identity,
        token,
        project_id,
        uuid4(),
        refs,
        provider=SyntheticGrouping("ungrouped"),
    )
    assert empty["result"]["state"] == "completed"
    queued = enqueue_grouping(
        app.state.sessions, app.state.identity, token, project_id, uuid4(), refs
    )
    assert queued["attempt_id"] is None
    value = {
        "login": login,
        "projectId": project["id"],
        "groupId": historical["id"],
        "historicalStateId": historical["state_id"],
        "currentStateId": current_state,
        "groupRunId": str(result["run_id"]),
        "ungroupedRunId": str(empty["run_id"]),
        "queuedRunId": str(queued["run_id"]),
        "findingRefs": refs,
    }
    target = Path("/workspace/.local/workflow/groups.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
app.state.engine.dispose()
print("Prepared owned synthetic groups/history; queued F3 must finish in the real worker.")
