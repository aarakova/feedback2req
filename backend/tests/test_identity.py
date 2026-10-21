from datetime import timedelta

import pytest
from sqlalchemy import select

from feedback2req.identity.service import token_hash
from feedback2req.persistence.models import Session, User

from .conftest import PASSWORD, signin, signup


def test_registration_and_login(client, app):
    """FR-032 / AC-01 subset: local account and non-enumerating login errors."""
    user = signup(client, "  ТЕСТ_Ａ  ")
    assert user["login"] == "тест_a"
    assert set(user) == {"id", "login"}
    assert client.get("/api/v1/auth/session").status_code == 401
    signin(client, "тест_a")
    assert client.get("/api/v1/auth/session").json()["user"] == user
    errors = []
    for login in ["тест_a", "no_such_user"]:
        response = client.post(
            "/api/v1/auth/session",
            json={
                "login": login,
                "password": "wrong-password-long-enough",
            },
        )
        assert response.status_code == 401
        errors.append({k: v for k, v in response.json()["error"].items() if k != "request_id"})
    assert errors[0] == errors[1]
    with app.state.sessions() as tx:
        stored = tx.scalar(select(User))
        assert stored.password_hash.startswith("$argon2id$")
        assert app.state.identity.hasher.verify(stored.password_hash, PASSWORD)


def test_duplicate_login(client):
    signup(client, "  UserＡ ")
    response = client.post("/api/v1/auth/register", json={"login": "usera", "password": PASSWORD})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "login_unavailable"


def test_session_storage_and_logout(client, app):
    signup(client, "owner")
    signin(client, "owner")
    raw = client.cookies["f2r_session"]
    with app.state.sessions() as tx:
        session = tx.scalar(select(Session))
        assert session.token_hash == token_hash(raw)
        assert raw not in (session.token_hash, session.csrf_secret)
        assert session.revoked_at is None
    response = client.delete("/api/v1/auth/session")
    assert response.status_code == 204 and not response.content
    assert "f2r_session" not in client.cookies
    client.cookies.set("f2r_session", raw)
    assert client.get("/api/v1/auth/session").status_code == 401
    with app.state.sessions() as tx:
        assert tx.get(Session, token_hash(raw)).revoked_at is not None


@pytest.mark.parametrize("expiry", ["absolute", "idle"])
def test_expired_session(client, app, expiry):
    signup(client, "owner")
    signin(client, "owner")
    with app.state.sessions.begin() as tx:
        session = tx.scalar(select(Session))
        session.created_at -= timedelta(days=3)
        if expiry == "absolute":
            session.expires_at = session.created_at + timedelta(days=1)
        else:
            session.last_seen_at -= timedelta(days=2)
            session.expires_at += timedelta(days=1)
    assert client.get("/api/v1/auth/session").status_code == 401


def test_login_rotates_token(client):
    signup(client, "owner")
    client.cookies.set("f2r_session", "attacker-supplied-token", domain="localhost.local", path="/")
    signin(client, "owner")
    first = client.cookies["f2r_session"]
    signin(client, "owner")
    assert client.cookies["f2r_session"] not in {first, "attacker-supplied-token"}


def test_cookie_and_sliding_idle(client, app):
    signup(client, "owner")
    response = client.post("/api/v1/auth/session", json={"login": "owner", "password": PASSWORD})
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie and "path=/" in cookie
    assert "secure" not in cookie  # Explicit loopback HTTP profile only.
    with app.state.sessions.begin() as tx:
        session = tx.scalar(select(Session))
        session.created_at -= timedelta(seconds=100)
        session.last_seen_at -= timedelta(seconds=100)
        before = session.last_seen_at
        absolute = session.expires_at
    assert client.get("/api/v1/auth/session").status_code == 200
    with app.state.sessions() as tx:
        session = tx.scalar(select(Session))
        assert session.last_seen_at > before
        assert session.expires_at == absolute
