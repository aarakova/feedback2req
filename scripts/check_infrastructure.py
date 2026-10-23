"""HTTP checks against the isolated infrastructure Compose overlay, no working DB."""

import argparse
import json
from http.cookiejar import MozillaCookieJar
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import HTTPCookieProcessor, ProxyHandler, Request, build_opener
from uuid import uuid4

ORIGIN = "http://localhost:18080"
BASE = "http://frontend"
STATE = Path("/state")


def client(name):
    jar = MozillaCookieJar(str(STATE / f"{name}.cookies"))
    if Path(jar.filename).exists():
        jar.load(ignore_discard=True, ignore_expires=True)
    return build_opener(ProxyHandler({}), HTTPCookieProcessor(jar)), jar


def call(opener, path, method="GET", data=None, headers=None, base=BASE):
    fields = {"Origin": ORIGIN, **(headers or {})}
    if data is not None:
        fields["Content-Type"] = "application/json"
    request = Request(
        base + path,
        method=method,
        headers=fields,
        data=json.dumps(data).encode() if data is not None else None,
    )
    try:
        response = opener.open(request, timeout=10)
    except HTTPError as error:
        response = error
    with response:
        raw = response.read()
        body = (
            json.loads(raw)
            if raw and "application/json" in response.headers.get("Content-Type", "")
            else raw
        )
        return response.status, body, response.headers


def smoke():
    STATE.mkdir(exist_ok=True)
    owner, jar = client("owner")
    credentials = {"login": "infra_" + uuid4().hex, "password": "test-only-infrastructure"}
    assert call(owner, "/")[0] == 200
    for path in ["/.env", "/private.txt"]:
        status = call(owner, path)[0]
        assert status == 404, (path, status)
    # Nginx rejects a traversal above the root as malformed before routing.
    assert call(owner, "/../compose.yaml")[0] == 400
    assert call(owner, "/api/v1/auth/session")[0] == 401
    assert call(owner, "/api/v1/missing")[0] == 404
    assert (
        call(
            owner,
            "/api/v1/auth/register",
            "POST",
            credentials,
            {"Origin": "https://evil.example", "X-Forwarded-Host": "localhost:18080"},
        )[0]
        == 403
    )
    assert call(owner, "/api/v1/auth/register", "POST", credentials)[0] == 201
    status, session, headers = call(owner, "/api/v1/auth/session", "POST", credentials)
    assert status == 200 and "HttpOnly" in headers["Set-Cookie"]
    assert "SameSite=lax" in headers["Set-Cookie"]
    assert headers["Cache-Control"].lower() == "no-store"
    csrf = {"X-CSRF-Token": session["csrf_token"]}
    assert call(owner, "/api/v1/projects", "POST", {"name": "blocked"})[0] == 403
    status, project, _ = call(owner, "/api/v1/projects", "POST", {"name": "Infrastructure"}, csrf)
    assert status == 201
    root = f"/api/v1/projects/{project['id']}"
    exact = "  ё Е\u0308 🙂\t\r\nLF\n<script>text</script>  "
    saved = []
    for kind, data in [
        ("sources", {"kind": "text", "text": exact}),
        ("documents", {"title": "Контекст", "text": exact}),
    ]:
        status, material, _ = call(owner, f"{root}/{kind}", "POST", data, csrf)
        assert status == 201 and material["text"] == exact
        saved.append({"path": f"{root}/{kind}/{material['id']}", "value": material})
    status, error, _ = call(
        owner, root + "/sources", "POST", {"kind": "text", "text": "x" * 20000}, csrf
    )
    assert status == 413 and error["error"]["code"] == "body_too_large"
    other, _ = client("outsider")
    credentials["login"] += "_other"
    assert call(other, "/api/v1/auth/register", "POST", credentials)[0] == 201
    assert call(other, "/api/v1/auth/session", "POST", credentials)[0] == 200
    for record in saved:
        assert call(other, record["path"])[0] == 404
    jar.save(ignore_discard=True, ignore_expires=True)
    (STATE / "saved.json").write_text(json.dumps(saved), encoding="utf-8")
    verify()


def verify():
    opener, _ = client("owner")
    status, body, _ = call(opener, "/api/v1/.missing")
    assert status == 404 and body["error"]["code"] == "http_error"
    assert call(opener, "/api/v1/auth/session")[0] == 200
    for record in json.loads((STATE / "saved.json").read_text(encoding="utf-8")):
        status, body, _ = call(opener, record["path"])
        assert status == 200 and body == record["value"]


def rate():
    # Run after recreating isolated backend with F2R_TEST_LOGIN_LIMIT=2.
    opener = build_opener(ProxyHandler({}))
    for number, (base, expected) in enumerate(
        [("http://backend:8000", 401), (BASE, 401), (BASE, 429)]
    ):
        status, _, _ = call(
            opener,
            "/api/v1/auth/session",
            "POST",
            {"login": "unknown", "password": "test-only"},
            {
                "X-Forwarded-For": f"192.0.2.{number}",
                "Forwarded": f"for=198.51.100.{number};proto=https",
                "X-Real-IP": f"203.0.113.{number}",
                "X-Forwarded-Proto": "https",
            },
            base=base,
        )
        assert status == expected


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["smoke", "verify", "rate"])
    args = parser.parse_args()
    {"smoke": smoke, "verify": verify, "rate": rate}[args.action]()
    print(f"Infrastructure {args.action}: PASS")
