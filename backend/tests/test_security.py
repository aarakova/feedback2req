import pytest
from fastapi.testclient import TestClient

from feedback2req.api.routes import Actor, Tx
from feedback2req.config import Settings
from feedback2req.main import create_app
from feedback2req.projects.service import create_project

from .conftest import ORIGIN, PASSWORD, project, signin, signup


def test_origin_and_csrf(client):
    """FR-032 / slice §7: mutations require exact Origin and session-bound CSRF."""
    credentials = {"login": "owner", "password": PASSWORD}
    for path in ["/auth/register", "/auth/session"]:
        for origin in ["", "null", "https://evil.example", "http://localhost:8000.evil.example"]:
            assert (
                client.post(
                    "/api/v1" + path, json=credentials, headers={"Origin": origin}
                ).status_code
                == 403
            )
        assert (
            client.post(
                "/api/v1" + path, content="{}", headers={"Content-Type": "text/plain"}
            ).status_code
            == 422
        )
    signup(client, "owner")
    signin(client, "owner")
    p = project(client)
    for method, path, body in [
        ("POST", "/api/v1/projects", {"name": "invalid"}),
        ("PATCH", f"/api/v1/projects/{p['id']}", {"name": "invalid"}),
        ("PUT", f"/api/v1/projects/{p['id']}/access/{p['owner_id']}", {"can_approve": False}),
        ("DELETE", f"/api/v1/projects/{p['id']}/access/{p['owner_id']}", None),
        ("DELETE", "/api/v1/auth/session", None),
    ]:
        for csrf in ["", "wrong"]:
            assert (
                client.request(method, path, json=body, headers={"X-CSRF-Token": csrf}).status_code
                == 403
            )
        assert (
            client.request(
                method, path, json=body, headers={"Origin": "https://evil.example"}
            ).status_code
            == 403
        )
    assert client.get("/api/v1/auth/session").status_code == 200
    assert client.get(f"/api/v1/projects/{p['id']}").json()["name"] == p["name"]


def test_csrf_is_session_bound(client, app):
    signup(client, "owner")
    token1 = signin(client, "owner")["csrf_token"]
    with TestClient(app, base_url=ORIGIN, headers={"Origin": ORIGIN}) as second:
        signin(second, "owner")
        assert (
            second.post(
                "/api/v1/projects", json={"name": "x"}, headers={"X-CSRF-Token": token1}
            ).status_code
            == 403
        )


def test_validation_and_errors(client):
    secret = "do-not-reflect-this-password"
    response = client.post(
        "/api/v1/auth/register",
        json={
            "login": "user",
            "password": secret,
            "unexpected": secret,
        },
    )
    assert response.status_code == 422
    assert secret not in response.text
    error = response.json()["error"]
    assert set(error) == {"code", "message", "details", "request_id"}
    assert response.headers["x-request-id"] == error["request_id"]
    assert error["details"] == {}
    assert response.headers["cache-control"] == "no-store"
    assert (
        client.post(
            "/api/v1/auth/register",
            json={
                "login": "user",
                "password": "short",
            },
        ).status_code
        == 422
    )
    signup(client, "owner")
    signin(client, "owner")
    assert client.post("/api/v1/projects", json={"name": "  "}).status_code == 422
    assert client.get("/api/v1/projects/not-a-uuid").status_code == 422
    assert client.post("/api/v1/projects", json={"name": "x", "owner_id": "x"}).status_code == 422
    p = project(client)
    assert (
        client.put(
            f"/api/v1/projects/{p['id']}/access/{p['owner_id']}", json={"can_approve": "true"}
        ).status_code
        == 422
    )
    assert client.get("/unknown").status_code == 404


def test_body_limit_and_rate_limit(client, app):
    app.state.settings.max_body_bytes = 300
    response = client.post(
        "/api/v1/auth/session", content="x" * 301, headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 413
    # A new app has a new, deliberately small process-local limiter.
    settings = app.state.settings.model_copy(update={"login_limit": 2})
    limited = create_app(settings)
    with TestClient(limited, base_url=ORIGIN, headers={"Origin": ORIGIN}) as other:
        for _ in range(2):
            assert (
                other.post(
                    "/api/v1/auth/session",
                    json={
                        "login": "unknown",
                        "password": PASSWORD,
                    },
                ).status_code
                == 401
            )
        assert (
            other.post(
                "/api/v1/auth/session",
                json={
                    "login": "unknown",
                    "password": PASSWORD,
                },
            ).status_code
            == 429
        )


def test_https_cookie_and_transport(database_url):
    app = create_app(
        Settings(
            database_url=database_url,
            allowed_origin="https://feedback.example",
            argon_memory_cost=8192,
            argon_time_cost=1,
        )
    )
    with TestClient(
        app, base_url="https://feedback.example", headers={"Origin": "https://feedback.example"}
    ) as client:
        signup(client, "owner")
        response = client.post(
            "/api/v1/auth/session", json={"login": "owner", "password": PASSWORD}
        )
        assert "secure" in response.headers["set-cookie"].lower()
    with pytest.raises(ValueError, match="HTTP requires"):
        Settings(database_url=database_url, allowed_origin="http://192.168.1.10", local_http=True)


def test_anonymous_and_internal_errors(client, app):
    assert client.post("/api/v1/projects", json={"name": "x"}).status_code == 401

    @app.get("/test-error")
    def fail():
        raise RuntimeError("sensitive-body-or-sql-value")

    response = client.get("/test-error")
    assert response.status_code == 500
    assert "sensitive" not in response.text
    assert response.json()["error"]["code"] == "internal_error"


def test_failed_transaction_rolls_back_without_secret_logs(client, app, caplog):
    signup(client, "owner")
    signin(client, "owner")

    @app.post("/test-rollback")
    def fail(tx: Tx, actor: Actor):
        create_project(tx, actor.user.id, "Must roll back")
        raise RuntimeError("private-value-from-request")

    response = client.post("/test-rollback")
    assert response.status_code == 500
    assert client.get("/api/v1/projects").json()["items"] == []
    for secret in ["private-value-from-request", PASSWORD, client.cookies["f2r_session"]]:
        assert secret not in caplog.text
        assert secret not in response.text
