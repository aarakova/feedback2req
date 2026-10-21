import json
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from feedback2req.persistence.models import DocumentState, SourceTextState

from .conftest import ORIGIN, project, signin, signup

EXACT_TEXT = " \tКириллица ё Е\u0308 👩🏽‍💻\nПервая\r\nВторая\tстрока \r\n "


@pytest.fixture
def material_project(client):
    user = signup(client, "owner")
    signin(client, "owner")
    return project(client), user


def payload(kind, text=EXACT_TEXT):
    return (
        {"kind": "text", "text": text}
        if kind == "sources"
        else {
            "title": " Контекст продукта ",
            "text": text,
        }
    )


@pytest.mark.parametrize("kind", ["sources", "documents"])
def test_create_list_read(client, app, material_project, kind):
    """FR-002,032 → AC-01 subset: owner and member enter/read distinct materials."""
    p, owner = material_project
    path = f"/api/v1/projects/{p['id']}/{kind}"
    assert client.get(path).json() == {"items": [], "next_cursor": None}
    response = client.post(path, json=payload(kind))
    assert response.status_code == 201, response.text
    saved = response.json()
    assert set(saved) == {"id", "state_id", "text", "kind" if kind == "sources" else "title"}
    assert saved["id"] != saved["state_id"]
    assert saved["text"] == EXACT_TEXT
    assert client.get(path + "/" + saved["id"]).json() == saved
    assert client.get(path).json()["items"] == [saved]
    with TestClient(app, base_url=ORIGIN, headers={"Origin": ORIGIN}) as member:
        user = signup(member, "member")
        signin(member, "member")
        assert (
            client.put(
                f"/api/v1/projects/{p['id']}/access/{user['id']}", json={"can_approve": False}
            ).status_code
            == 200
        )
        assert member.get(path + "/" + saved["id"]).json() == saved
        assert member.post(path, json=payload(kind)).status_code == 201
        assert len(member.get(path).json()["items"]) == 2
    state_type = SourceTextState if kind == "sources" else DocumentState
    with app.state.sessions() as tx:
        states = tx.scalars(select(state_type)).all()
        assert {str(state.author_id) for state in states} == {owner["id"], user["id"]}
        assert all(state.origin == "human" and state.created_at.tzinfo for state in states)
    # No processing or analysis tables exist; document data is separate from feedback.
    opposite = "documents" if kind == "sources" else "sources"
    assert client.get(f"/api/v1/projects/{p['id']}/{opposite}").json()["items"] == []


@pytest.mark.parametrize("kind", ["sources", "documents"])
def test_isolation_and_revocation(client, app, material_project, kind):
    p, _ = material_project
    path = f"/api/v1/projects/{p['id']}/{kind}"
    saved = client.post(path, json=payload(kind)).json()
    other_project = project(client)
    # Even an actor with both projects cannot look up a material in the wrong project.
    wrong = f"/api/v1/projects/{other_project['id']}/{kind}/{saved['id']}"
    assert client.get(wrong).status_code == 404
    assert client.get(path + f"/{uuid4()}").status_code == 404
    with TestClient(app, base_url=ORIGIN, headers={"Origin": ORIGIN}) as other:
        assert other.get(path).status_code == 401
        assert other.get(path + "/" + saved["id"]).status_code == 401
        assert other.post(path, json=payload(kind)).status_code == 401
        user = signup(other, "other")
        signin(other, "other")
        for action in [
            lambda: other.get(path),
            lambda: other.get(path + "/" + saved["id"]),
            lambda: other.post(path, json=payload(kind)),
        ]:
            denied = action()
            assert denied.status_code == 404
            assert EXACT_TEXT not in denied.text
        access_path = f"/api/v1/projects/{p['id']}/access/{user['id']}"
        assert client.put(access_path, json={"can_approve": True}).status_code == 200
        assert other.get(path).status_code == 200
        assert client.delete(access_path).status_code == 204
        assert other.get(path).status_code == 404
        assert other.get(path + "/" + saved["id"]).status_code == 404
        assert other.post(path, json=payload(kind)).status_code == 404


@pytest.mark.parametrize("kind", ["sources", "documents"])
@pytest.mark.parametrize("text", [EXACT_TEXT, "\r\nТекст\r\n", "e\u0301\u00e9", " A\tB\n\n "])
def test_exact_text(client, material_project, kind, text):
    p, _ = material_project
    path = f"/api/v1/projects/{p['id']}/{kind}"
    created = client.post(path, json=payload(kind, text))
    assert created.status_code == 201
    saved = created.json()
    read = client.get(path + "/" + saved["id"]).json()
    assert read == saved
    assert read["text"].encode("utf-8") == text.encode("utf-8")


@pytest.mark.parametrize("kind", ["sources", "documents"])
def test_validation_and_limits(client, app, material_project, kind, caplog):
    p, _ = material_project
    path = f"/api/v1/projects/{p['id']}/{kind}"
    for text in ["", " \t\r\n", "\u00a0\u2003", "contains\x00nul", "surrogate\ud800"]:
        encoded = json.dumps(payload(kind, text), ensure_ascii=True).encode("ascii")
        assert (
            client.post(
                path, content=encoded, headers={"Content-Type": "application/json"}
            ).status_code
            == 422
        )
    assert client.post(path, json=payload(kind) | {"extra": "private-input"}).status_code == 422
    if kind == "sources":
        assert client.post(path, json={"kind": "audio", "text": "x"}).status_code == 422
        assert client.post(path, json={"text": "x"}).status_code == 422
    else:
        for title in ["", " \t", "x" * 201, "nul\x00title"]:
            assert client.post(path, json={"title": title, "text": "x"}).status_code == 422
    app.state.settings.max_material_text_chars = 4
    assert client.post(path, json=payload(kind, "ё👩AB")).status_code == 201
    oversized = client.post(path, json=payload(kind, "private-long-text"))
    assert oversized.status_code == 413
    assert oversized.json()["error"]["code"] == "text_too_large"
    app.state.settings.max_material_text_chars = 1000
    app.state.settings.max_body_bytes = 300
    oversized = client.post(path, json=payload(kind, "ё" * 200))
    assert oversized.status_code == 413
    assert oversized.json()["error"]["code"] == "body_too_large"
    for secret in ["private-input", "private-long-text"]:
        assert secret not in caplog.text
        assert secret not in oversized.text


@pytest.mark.parametrize("kind", ["sources", "documents"])
def test_origin_csrf(client, app, material_project, kind):
    p, _ = material_project
    path = f"/api/v1/projects/{p['id']}/{kind}"
    for headers in [
        {"Origin": ""},
        {"Origin": "https://foreign.example"},
        {"X-CSRF-Token": ""},
        {"X-CSRF-Token": "wrong"},
    ]:
        assert client.post(path, json=payload(kind), headers=headers).status_code == 403
    assert client.get(path).json()["items"] == []
    state_type = SourceTextState if kind == "sources" else DocumentState
    with app.state.sessions() as tx:
        assert tx.scalar(select(func.count()).select_from(state_type)) == 0


@pytest.mark.parametrize("kind", ["sources", "documents"])
def test_pagination(client, app, material_project, kind):
    p, _ = material_project
    path = f"/api/v1/projects/{p['id']}/{kind}"
    app.state.settings.page_size = 2
    ids = {client.post(path, json=payload(kind, str(i))).json()["id"] for i in range(5)}
    observed, cursor = [], None
    while True:
        page = client.get(path, params={"cursor": cursor} if cursor else {}).json()
        assert len(page["items"]) <= 2
        observed.extend(item["id"] for item in page["items"])
        cursor = page["next_cursor"]
        if cursor is None:
            break
    assert observed == sorted(ids)
