#!/usr/bin/env python3
"""Synthetic F2 persistence probe across separate Python processes and DB restart.

Only a dedicated *_f2_test database on an explicitly named f2r-f2-* test host.
This tool does not start/stop Docker or delete any database objects.
"""

import json
import os
import sys
from pathlib import Path
from uuid import UUID, uuid4

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from feedback2req.config import Settings
from feedback2req.grouping.service import Provenance, accept_grouping, prepare_grouping
from feedback2req.main import create_app
from feedback2req.processing.service import execute_one
from sqlalchemy.engine import make_url
from tests.conftest import ORIGIN, project, signin, signup
from tests.test_grouping import synthetic_response
from tests.test_processing import Synthetic, start


def main():
    mode, state_file = sys.argv[1:]
    url = make_url(os.environ["F2R_TEST_DATABASE_URL"])
    if (
        url.drivername != "postgresql+psycopg"
        or not (url.host or "").startswith("f2r-f2-")
        or not (url.database or "").endswith("_f2_test")
        or mode not in {"seed", "verify"}
    ):
        raise RuntimeError(
            "A dedicated named F2 test database and seed/verify mode are required"
        )
    state_file = Path(state_file)
    raw = url.render_as_string(hide_password=False)
    if mode == "seed":
        if state_file.exists():
            raise RuntimeError("Refusing to overwrite an existing persistence snapshot")
        cfg = Config(str(Path(__file__).parents[1] / "backend/alembic.ini"))
        cfg.attributes["database_url"] = raw
        command.upgrade(cfg, "head")
    settings = Settings(
        database_url=raw,
        allowed_origin=ORIGIN,
        local_http=True,
        argon_memory_cost=8192,
        argon_time_cost=1,
    )
    app = create_app(settings)
    with TestClient(app, base_url=ORIGIN, headers={"Origin": ORIGIN}) as client:
        if mode == "seed":
            login = "f2-restart-" + uuid4().hex
            signup(client, login)
            signin(client, login)
            p = project(client, "Synthetic F2 restart probe")
            path = f"/api/v1/projects/{p['id']}"
            for value in ("Автоматически", "С подтверждением", "Отдельная просьба"):
                source = client.post(
                    path + "/sources", json={"kind": "text", "text": value}
                ).json()
                assert start(client, path, source).status_code == 202
                assert execute_one(app.state.sessions, settings, Synthetic())
            findings = client.get(path + "/findings").json()["items"]
            h = prepare_grouping(
                app.state.sessions,
                app.state.identity,
                client.cookies.get(settings.session_cookie),
                UUID(p["id"]),
                uuid4(),
                [{"id": f["id"], "state_id": f["state_id"]} for f in findings],
                provenance=Provenance("synthetic-test", "restart-probe", True),
            )
            assert (
                accept_grouping(
                    app.state.sessions,
                    h["unit_id"],
                    h["owner_token"],
                    synthetic_response(h),
                )["state"]
                == "completed"
            )
            group_ids = client.get(path + "/groups").json()["items"]
            snapshot = {
                "login": login,
                "path": path,
                "run_id": str(h["run_id"]),
                "groups": [
                    client.get(path + "/groups/" + g["id"]).json() for g in group_ids
                ],
                "run": client.get(path + "/runs/" + str(h["run_id"])).json(),
            }
            state_file.parent.mkdir(parents=True, exist_ok=True)
            state_file.write_text(
                json.dumps(snapshot, ensure_ascii=False), encoding="utf-8"
            )
            print(
                "PASS synthetic F2 seed: exact evidence, conflicts, ungrouped and Run saved"
            )
        else:
            snapshot = json.loads(state_file.read_text(encoding="utf-8"))
            signin(client, snapshot["login"])
            path = snapshot["path"]
            assert (
                client.get(path + "/runs/" + snapshot["run_id"]).json()
                == snapshot["run"]
            )
            for group in snapshot["groups"]:
                assert client.get(path + "/groups/" + group["id"]).json() == group
                assert (
                    client.get(
                        path + f"/groups/{group['id']}/states/{group['state_id']}"
                    ).json()
                    == group
                )
            print(
                "PASS synthetic F2 restart: exact group/state/evidence/Run snapshots unchanged"
            )


if __name__ == "__main__":
    main()
