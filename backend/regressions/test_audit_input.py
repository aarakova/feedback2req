#!/usr/bin/env python3
"""AUD-01: opt-in expected failures, outside backend/tests and the required suite."""

import json

import pytest

from tests.conftest import PASSWORD, project, signin, signup

pytest_plugins = ["tests.conftest"]


def request_json(client, path, payload, method="POST"):
    return client.request(
        method,
        "/api/v1" + path,
        content=json.dumps(payload, ensure_ascii=True).encode("ascii"),
        headers={"Content-Type": "application/json"},
    )


def assert_safe_client_error(response, marker):
    assert marker not in response.text
    assert "Traceback" not in response.text
    error = response.json()["error"]
    assert error["details"] == {}
    assert error["request_id"] == response.headers["x-request-id"]
    assert response.status_code == 422, response.text


@pytest.mark.parametrize("method", ["POST", "PATCH"])
def test_project_name_nul_is_a_client_error(client, method):
    signup(client, "qa-owner")
    signin(client, "qa-owner")
    path = "/projects"
    if method == "PATCH":
        saved = project(client, "Preserve original name")
        path += "/" + saved["id"]
    marker = "PRIVATE-NAME-SENTINEL"
    response = request_json(client, path, {"name": marker + "\x00"}, method)
    if method == "PATCH":
        assert client.get("/api/v1" + path).json()["name"] == saved["name"]
    else:
        assert client.get("/api/v1/projects").json()["items"] == []
    assert_safe_client_error(response, marker)


@pytest.mark.parametrize("operation", ["register", "session"])
def test_unpaired_password_surrogate_is_a_client_error(client, operation):
    if operation == "session":
        signup(client, "qa-password-owner")
    marker = "PRIVATE-PASSWORD-SENTINEL"
    response = request_json(
        client,
        "/auth/" + operation,
        {"login": "qa-password-owner", "password": marker + "\ud800"},
    )
    assert PASSWORD not in response.text
    assert_safe_client_error(response, marker)
