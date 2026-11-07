"""Read-only synthetic workflow snapshot before/after an owned stack restart.

This script never starts/stops containers or changes saved product objects.
Use only the dedicated compose.workflow-test.yaml database and fixture account.
"""

import argparse
import json
import os
from pathlib import Path

import httpx
from sqlalchemy.engine import make_url


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["snapshot", "verify"])
    args = parser.parse_args()
    assert make_url(os.environ["F2R_DATABASE_URL"]).database == "feedback2req_processing_f1_test"
    fixture = json.loads(Path(".local/workflow/groups.json").read_text("utf-8"))
    target = Path(".local/workflow/restart.json")
    if args.mode == "snapshot" and target.exists():
        raise RuntimeError("Refusing to overwrite the previous restart evidence")
    with httpx.Client(
        base_url=os.environ["F1_TEST_API"],
        headers={"Origin": os.environ.get("F1_TEST_ORIGIN", "http://localhost:18080")},
        trust_env=False,
    ) as client:
        response = client.post(
            "/api/v1/auth/session",
            json={"login": fixture["login"], "password": "frontend-test-only-2026"},
        )
        assert response.status_code == 200
        root = "/api/v1/projects/" + fixture["projectId"]
        paths = [
            root,
            root + "/groups/" + fixture["groupId"],
            root + "/groups/" + fixture["groupId"] + "/states/" + fixture["historicalStateId"],
            *[
                root + "/runs/" + fixture[key]
                for key in ("groupRunId", "ungroupedRunId", "queuedRunId")
            ],
            *[root + "/findings/" + ref["id"] for ref in fixture["findingRefs"]],
        ]
        values = {}
        for path in paths:
            response = client.get(path)
            assert response.status_code == 200
            values[path] = response.json()
        sources = {
            evidence["source_ref"]["id"]
            for ref in fixture["findingRefs"]
            for evidence in values[root + "/findings/" + ref["id"]]["evidence"]
        }
        for identity in sources:
            path = root + "/sources/" + identity
            response = client.get(path)
            assert response.status_code == 200
            values[path] = response.json()
    if args.mode == "snapshot":
        target.write_text(json.dumps(values, ensure_ascii=False), encoding="utf-8")
    else:
        assert values == json.loads(target.read_text("utf-8"))
    print("PASS: exact synthetic sources/findings/groups/states/runs " + args.mode)


if __name__ == "__main__":
    main()
