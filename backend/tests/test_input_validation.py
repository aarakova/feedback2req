"""FR-001/032, AC-01: invalid strings fail safely before persistence/hash work."""

import json

import pytest

from .conftest import project, signin, signup


def send_json(client, method, path, body):
    # JSON escapes can carry unpaired surrogates even though UTF-8 cannot.
    return client.request(
        method,
        path,
        content=json.dumps(body, ensure_ascii=True).encode("ascii"),
        headers={"Content-Type": "application/json"},
    )


def assert_safe_invalid_request(response, marker, caplog):
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "invalid_request"
    assert error["details"] == {}
    assert error["request_id"] == response.headers["x-request-id"]
    assert response.headers["cache-control"] == "no-store"
    assert marker not in response.text
    assert marker not in caplog.text


@pytest.mark.parametrize("method", ["POST", "PATCH"])
@pytest.mark.parametrize("invalid", ["\x00", "\ud800", "\udfff"])
def test_invalid_project_name_does_not_write(client, method, invalid, caplog):
    signup(client, "string-owner")
    signin(client, "string-owner")
    path = "/api/v1/projects"
    original = None
    if method == "PATCH":
        original = project(client, "Сохранить имя ё🙂")
        path += "/" + original["id"]
    marker = "PRIVATE-PROJECT-INPUT"
    response = send_json(client, method, path, {"name": marker + invalid})
    assert_safe_invalid_request(response, marker, caplog)
    projects = client.get("/api/v1/projects").json()["items"]
    assert projects == ([original] if original else [])
    if original:
        assert client.get(path).json() == original


@pytest.mark.parametrize("operation", ["register", "session"])
@pytest.mark.parametrize("invalid", ["\ud800", "\udfff"])
def test_unpaired_password_surrogate_is_rejected(client, operation, invalid, caplog):
    login = "string-password-owner"
    if operation == "session":
        signup(client, login)
    marker = "PRIVATE-PASSWORD-INPUT"
    response = send_json(
        client,
        "POST",
        "/api/v1/auth/" + operation,
        {"login": login, "password": marker + invalid},
    )
    assert_safe_invalid_request(response, marker, caplog)
    assert client.get("/api/v1/auth/session").status_code == 401
    if operation == "register":
        # Failed validation must not reserve the login or create a session.
        signup(client, login)


def test_valid_unicode_password_is_preserved_exactly(client):
    password = "Пароль-е\u0308-🙂-\x00-123456"
    body = {"login": "unicode-password", "password": password}
    assert send_json(client, "POST", "/api/v1/auth/register", body).status_code == 201
    changed = body | {"password": password.replace("е\u0308", "ё")}
    assert send_json(client, "POST", "/api/v1/auth/session", changed).status_code == 401
    assert send_json(client, "POST", "/api/v1/auth/session", body).status_code == 200
