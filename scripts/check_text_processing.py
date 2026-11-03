"""Isolated Docker HTTP harness and unmistakably synthetic Ollama test double."""

import json
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from uuid import uuid4

STATE = Path("/state/extraction.json")
TEXT = "СИНТЕТИЧЕСКИЙ ТЕСТ: хочу сохранять фильтры. ё🙂\r\n"


def provider():
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_POST(self):
            value = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            req = json.loads(value["messages"][-1]["content"])
            text = req["input"]["segments"][0]["text"]
            if text.startswith("TEST-SLOW"):
                time.sleep(35)
            if text.startswith("TEST-FAIL"):
                self.send_error(503)
                return
            response = {
                "coverage": [
                    {"input_key": "s1", "reviewed": True, "disposition": "completed"}
                ],
                "questions": [],
                "uncertainties": [],
                "result": {
                    "fragments": [
                        {
                            "local_id": "f",
                            "segment_key": "s1",
                            "quote": text,
                            "occurrence": 0,
                        }
                    ],
                    "findings": [
                        {
                            "local_id": "n",
                            "text": "Синтетическая находка HTTP-теста",
                            "types": ["request"],
                            "mode": "direct",
                            "fragment_ids": ["f"],
                            "considered_keys": ["s1"],
                            "context_keys": [],
                        }
                    ],
                },
            }
            raw = json.dumps(
                {"done": True, "message": {"content": json.dumps(response)}}
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

    ThreadingHTTPServer(("0.0.0.0", 11434), Handler).serve_forever()


def client(state=None):
    import httpx

    value = httpx.Client(
        base_url="http://api:8000",
        headers={"Origin": "http://localhost:8000"},
        timeout=10,
        trust_env=False,
    )
    if state:
        value.cookies.update(state["cookies"])
        value.headers["X-CSRF-Token"] = state["csrf"]
    return value


def wait_run(http, path, run_id, expected):
    for _ in range(100):
        result = http.get(path + "/runs/" + run_id)
        assert result.status_code == 200
        run = result.json()
        if run["state"] in expected:
            return run
        time.sleep(1)
    raise RuntimeError("Timed out waiting for persisted run state")


def create_run(http, path, text):
    response = http.post(path + "/sources", json={"kind": "text", "text": text})
    assert response.status_code == 201
    source = response.json()
    response = http.post(
        path + "/runs",
        headers={"Idempotency-Key": str(uuid4())},
        json={
            "operation": "extract_feedback",
            "inputs": [
                {"kind": "source", "id": source["id"], "state_id": source["state_id"]}
            ],
        },
    )
    assert response.status_code == 202
    return source, response.json()


def seed():
    with client() as http:
        credentials = {
            "login": "docker-" + uuid4().hex,
            "password": "synthetic-test-only-password",
        }
        assert http.post("/api/v1/auth/register", json=credentials).status_code == 201
        session = http.post("/api/v1/auth/session", json=credentials).json()
        http.headers["X-CSRF-Token"] = session["csrf_token"]
        response = http.post(
            "/api/v1/projects", json={"name": "Synthetic extraction Docker test"}
        )
        assert response.status_code == 201
        path = "/api/v1/projects/" + response.json()["id"]
        source, run = create_run(http, path, TEXT)
        completed = wait_run(http, path, run["id"], {"completed"})
        assert completed["units"][0]["attempt"]["synthetic"] is True
        assert completed["units"][0]["attempt"]["ai_performed"] is False
        found = http.get(path + "/findings").json()["items"]
        assert len(found) == 1 and found[0]["evidence"][0]["quote"] == TEXT
        STATE.write_text(
            json.dumps(
                {
                    "cookies": dict(http.cookies),
                    "csrf": session["csrf_token"],
                    "path": path,
                    "source": source,
                    "run": completed,
                    "finding": found[0],
                }
            )
        )
    print(
        "PASS: real HTTP -> durable queue -> worker -> synthetic provider -> accepted PG result"
    )


def verify():
    state = json.loads(STATE.read_text())
    with client(state) as http:
        path = state["path"]
        assert http.get("/api/v1/auth/session").status_code == 200
        assert (
            http.get(path + "/sources/" + state["source"]["id"]).json()
            == state["source"]
        )
        assert http.get(path + "/runs/" + state["run"]["id"]).json() == state["run"]
        assert (
            http.get(path + "/findings/" + state["finding"]["id"]).json()
            == state["finding"]
        )
        assert len(http.get(path + "/findings").json()["items"]) == 1
    print(
        "PASS: session, exact text, run, fragment/evidence and finding survived restart"
    )


def failure():
    state = json.loads(STATE.read_text())
    with client(state) as http:
        _, run = create_run(http, state["path"], "TEST-FAIL synthetic provider failure")
        failed = wait_run(http, state["path"], run["id"], {"failed"})
        unit = failed["units"][0]
        assert unit["attempt"]["reason_code"] == "provider_error"
        assert unit["attempt"]["finding_ids"] == []
        key = str(uuid4())
        body = {"expected_attempt_id": unit["attempt"]["id"]}
        url = state["path"] + "/units/" + unit["id"] + "/retries"
        one = http.post(url, headers={"Idempotency-Key": key}, json=body)
        assert one.status_code == 202
        two = http.post(url, headers={"Idempotency-Key": key}, json=body)
        assert two.status_code == 202 and two.json()["id"] == one.json()["id"]
        wait_run(http, state["path"], one.json()["id"], {"failed"})
        assert len(http.get(state["path"] + "/findings").json()["items"]) == 1
    print("PASS: provider failure, no fabricated findings, explicit idempotent retry")


def slow():
    state = json.loads(STATE.read_text())
    with client(state) as http:
        _, run = create_run(
            http, state["path"], "TEST-SLOW synthetic normal 35 second compute"
        )
        completed = wait_run(http, state["path"], run["id"], {"completed"})
        assert completed["units"][0]["attempt"]["synthetic"] is True
    print("PASS: 35 second provider compute with heartbeat, beyond short SQL budget")


if __name__ == "__main__":
    {
        "provider": provider,
        "seed": seed,
        "verify": verify,
        "failure": failure,
        "slow": slow,
    }[sys.argv[1]]()
