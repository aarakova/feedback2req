from uuid import uuid4

from fastapi.testclient import TestClient

from .conftest import ORIGIN, project, signin, signup


def test_owner_and_name(client):
    """FR-001,032 / AC-01 subset: owner has all rights and controls settings."""
    user = signup(client, "owner")
    signin(client, "owner")
    p = project(client)
    assert p["owner_id"] == user["id"]
    assert p["execution_mode"] == "mock"
    assert p["permissions"] == {"is_owner": True, "is_member": True, "can_approve": True}
    path = f"/api/v1/projects/{p['id']}"
    assert client.get(path).json() == p
    renamed = client.patch(path, json={"name": "Новое имя"})
    assert renamed.status_code == 200
    assert client.get(path).json()["name"] == "Новое имя"
    assert client.get("/api/v1/projects").json()["items"][0]["name"] == "Новое имя"
    listed = client.get(path + "/access").json()["items"]
    assert listed == [
        {"user_id": user["id"], "is_owner": True, "is_member": True, "can_approve": True}
    ]


def test_isolation_and_permissions(client, app):
    """FR-003,032: no project disclosure, Member and Approver cannot manage."""
    signup(client, "owner")
    signin(client, "owner")
    p = project(client)
    path = f"/api/v1/projects/{p['id']}"
    with TestClient(app, base_url=ORIGIN, headers={"Origin": ORIGIN}) as other:
        member = signup(other, "member")
        signin(other, "member")
        assert other.get("/api/v1/projects").json()["items"] == []
        for method, suffix, kwargs in [
            ("GET", "", {}),
            ("GET", "/access", {}),
            ("PATCH", "", {"json": {"name": "attack"}}),
            ("PUT", f"/access/{member['id']}", {"json": {"can_approve": True}}),
            ("DELETE", f"/access/{member['id']}", {}),
        ]:
            assert other.request(method, path + suffix, **kwargs).status_code == 404
        unknown = other.get(f"/api/v1/projects/{uuid4()}").json()["error"]
        denied = other.get(path).json()["error"]
        assert {k: v for k, v in unknown.items() if k != "request_id"} == {
            k: v for k, v in denied.items() if k != "request_id"
        }
        for approver in [False, True]:
            assert (
                client.put(
                    path + f"/access/{member['id']}", json={"can_approve": approver}
                ).status_code
                == 200
            )
            assert other.get(path).json()["permissions"] == {
                "is_owner": False,
                "is_member": True,
                "can_approve": approver,
            }
            assert other.get("/api/v1/projects").json()["items"][0]["id"] == p["id"]
            assert other.get(path + "/access").status_code == 403
            assert other.patch(path, json={"name": "attack"}).status_code == 403
            assert (
                other.put(path + f"/access/{member['id']}", json={"can_approve": True}).status_code
                == 403
            )
            assert other.delete(path + f"/access/{member['id']}").status_code == 403
        # Access to a different project never grants this member access there.
        with TestClient(app, base_url=ORIGIN, headers={"Origin": ORIGIN}) as third:
            signup(third, "third")
            signin(third, "third")
            foreign = project(third)
            assert other.get(f"/api/v1/projects/{foreign['id']}").status_code == 404


def test_access_lifecycle(client, app):
    owner = signup(client, "owner")
    signin(client, "owner")
    p = project(client)
    path = f"/api/v1/projects/{p['id']}"
    with TestClient(app, base_url=ORIGIN, headers={"Origin": ORIGIN}) as member_client:
        member = signup(member_client, "member")
        signin(member_client, "member")
        for approver in [False, True, False]:
            response = client.put(path + f"/access/{member['id']}", json={"can_approve": approver})
            assert response.status_code == 200
            assert member_client.get(path).json()["permissions"]["can_approve"] is approver
        assert len(client.get(path + "/access").json()["items"]) == 2
        assert client.delete(path + f"/access/{member['id']}").status_code == 204
        assert member_client.get(path).status_code == 404
        assert member_client.get("/api/v1/projects").json()["items"] == []
        assert client.delete(path + f"/access/{member['id']}").status_code == 204
    for method, kwargs in [("PUT", {"json": {"can_approve": False}}), ("DELETE", {})]:
        assert client.request(method, path + f"/access/{owner['id']}", **kwargs).status_code == 409
        assert client.get(path).json()["permissions"]["can_approve"] is True
    assert client.put(path + f"/access/{uuid4()}", json={"can_approve": True}).status_code == 422


def test_pagination(client, app):
    signup(client, "owner")
    signin(client, "owner")
    app.state.settings.page_size = 2
    ids = {project(client, f"Project {i}")["id"] for i in range(3)}
    first = client.get("/api/v1/projects").json()
    assert len(first["items"]) == 2
    second = client.get("/api/v1/projects", params={"cursor": first["next_cursor"]}).json()
    assert second["next_cursor"] is None
    assert {p["id"] for p in first["items"] + second["items"]} == ids
    path = f"/api/v1/projects/{next(iter(ids))}/access"
    for i in range(3):
        user = signup(client, f"member{i}")
        assert client.put(path + f"/{user['id']}", json={"can_approve": False}).status_code == 200
    first = client.get(path).json()
    second = client.get(path, params={"cursor": first["next_cursor"]}).json()
    assert len({p["user_id"] for p in first["items"] + second["items"]}) == 4
    assert second["next_cursor"] is None
