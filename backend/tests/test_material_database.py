from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event
from time import monotonic, sleep
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select, text, update
from sqlalchemy.exc import IntegrityError

from feedback2req.config import Settings
from feedback2req.main import create_app
from feedback2req.persistence.models import (
    DocumentState,
    FeedbackSource,
    ProductDocument,
    SourceTextState,
)
from feedback2req.persistence.projects import ProjectRepository

from .conftest import ORIGIN, project, signin, signup
from .test_materials import payload


def test_upgrade_from_m01(m01_database_url):
    app = create_app(
        Settings(
            database_url=m01_database_url,
            local_http=True,
            login_limit=100,
            argon_memory_cost=8192,
            argon_time_cost=1,
        )
    )
    with (
        TestClient(app, base_url=ORIGIN, headers={"Origin": ORIGIN}) as owner,
        TestClient(app, base_url=ORIGIN, headers={"Origin": ORIGIN}) as member,
    ):
        user = signup(owner, "owner")
        signin(owner, "owner")
        p = project(owner)
        m = signup(member, "member")
        signin(member, "member")
        assert (
            owner.put(
                f"/api/v1/projects/{p['id']}/access/{m['id']}", json={"can_approve": True}
            ).status_code
            == 200
        )
        tables = ["users", "sessions", "projects", "project_access"]

        def snapshot():
            with app.state.engine.connect() as connection:
                return {
                    table: connection.execute(text(f"SELECT * FROM {table}")).all()
                    for table in tables
                }

        before = snapshot()
        config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
        config.attributes["database_url"] = m01_database_url
        command.upgrade(config, "head")
        assert snapshot() == before
        assert owner.get("/api/v1/auth/session").json()["user"] == user
        assert member.get(f"/api/v1/projects/{p['id']}").json()["permissions"]["can_approve"]
        for kind in ["sources", "documents"]:
            path = f"/api/v1/projects/{p['id']}/{kind}"
            saved = member.post(path, json=payload(kind))
            assert saved.status_code == 201, saved.text
            assert owner.get(path + "/" + saved.json()["id"]).json() == saved.json()


@pytest.mark.parametrize("kind", ["sources", "documents"])
def test_constraints(client, app, kind):
    signup(client, "owner")
    signin(client, "owner")
    first_project, second_project = project(client), project(client)
    first_path = f"/api/v1/projects/{first_project['id']}/{kind}"
    foreign_path = f"/api/v1/projects/{second_project['id']}/{kind}"
    a, b = [client.post(first_path, json=payload(kind)).json() for _ in range(2)]
    c = client.post(foreign_path, json=payload(kind)).json()
    header, state = (
        (FeedbackSource, SourceTextState) if kind == "sources" else (ProductDocument, DocumentState)
    )
    owner_column = state.source_id if kind == "sources" else state.document_id
    invalid = [
        update(header)
        .where(header.id == UUID(a["id"]))
        .values(current_state_id=UUID(b["state_id"])),
        update(header)
        .where(header.id == UUID(a["id"]))
        .values(current_state_id=UUID(c["state_id"])),
        update(header).where(header.id == UUID(a["id"])).values(current_state_id=uuid4()),
        update(header).where(header.id == UUID(a["id"])).values(current_state_id=None),
        update(header).where(header.id == UUID(a["id"])).values(project_id=uuid4()),
        update(state)
        .where(state.id == UUID(a["state_id"]))
        .values(project_id=UUID(second_project["id"])),
        update(state).where(state.id == UUID(a["state_id"])).values({owner_column: UUID(c["id"])}),
        update(state).where(state.id == UUID(a["state_id"])).values({owner_column: UUID(b["id"])}),
        update(state).where(state.id == UUID(a["state_id"])).values(author_id=uuid4()),
        update(state).where(state.id == UUID(a["state_id"])).values(author_id=None),
        update(state).where(state.id == UUID(a["state_id"])).values(origin="ai"),
        update(state).where(state.id == UUID(a["state_id"])).values(text=""),
        update(state).where(state.id == UUID(a["state_id"])).values(text=None),
        update(state).where(state.id == UUID(a["state_id"])).values(created_at=None),
        update(state).where(state.id == UUID(a["state_id"])).values(id=UUID(b["state_id"])),
    ]
    if kind == "sources":
        invalid.append(update(header).where(header.id == UUID(a["id"])).values(kind="video"))
    else:
        invalid.append(update(state).where(state.id == UUID(a["state_id"])).values(title=" "))
    for statement in invalid:
        with pytest.raises(IntegrityError), app.state.sessions.begin() as tx:
            tx.execute(statement)  # Also checks deferred FK failures at COMMIT.
    assert client.get(first_path + "/" + a["id"]).json() == a


@pytest.mark.parametrize("kind", ["sources", "documents"])
def test_rollback(client, app, kind, caplog):
    signup(client, "owner")
    signin(client, "owner")
    p = project(client)
    header, state = (
        (FeedbackSource, SourceTextState) if kind == "sources" else (ProductDocument, DocumentState)
    )

    def fail_state(mapper, connection, target):
        target.author_id = None  # Fail actual state INSERT after the header INSERT succeeded.

    event.listen(state, "before_insert", fail_state)
    try:
        response = client.post(
            f"/api/v1/projects/{p['id']}/{kind}", json=payload(kind, "private-original-material")
        )
        assert response.status_code == 500
    finally:
        event.remove(state, "before_insert", fail_state)
    with app.state.sessions() as tx:
        assert tx.scalar(select(func.count()).select_from(header)) == 0
        assert tx.scalar(select(func.count()).select_from(state)) == 0
    assert "private-original-material" not in response.text + caplog.text
    assert "INSERT" not in response.text


def test_concurrent_revocation(client, app, monkeypatch):
    """FR-003: a write waiting behind committed revocation must recheck membership."""
    signup(client, "owner")
    signin(client, "owner")
    p = project(client)
    written, release = Event(), Event()
    original = ProjectRepository.remove_access

    def paused_revoke(repo, project_id, user_id):
        original(repo, project_id, user_id)
        repo.tx.flush()
        written.set()
        assert release.wait(10)

    monkeypatch.setattr(ProjectRepository, "remove_access", paused_revoke)
    with TestClient(app, base_url=ORIGIN, headers={"Origin": ORIGIN}) as member:
        user = signup(member, "member")
        signin(member, "member")
        access = f"/api/v1/projects/{p['id']}/access/{user['id']}"
        assert client.put(access, json={"can_approve": False}).status_code == 200
        with ThreadPoolExecutor(max_workers=2) as executor:
            revoke = executor.submit(client.delete, access)
            assert written.wait(5)
            create = executor.submit(
                member.post, f"/api/v1/projects/{p['id']}/sources", json=payload("sources")
            )
            locked = False
            try:
                deadline = monotonic() + 5
                while monotonic() < deadline:
                    with app.state.engine.connect() as connection:
                        locked = bool(
                            connection.scalar(
                                text("""
                            SELECT EXISTS (SELECT FROM pg_stat_activity
                            WHERE datname=current_database() AND wait_event_type='Lock'
                              AND query LIKE '%projects%FOR UPDATE%')
                        """)
                            )
                        )
                    if locked:
                        break
                    sleep(0.02)
            finally:
                release.set()
            assert revoke.result(timeout=10).status_code == 204
            assert create.result(timeout=10).status_code == 404
            assert locked, "Expected the material write to wait for the project lock"
    with app.state.sessions() as tx:
        assert tx.scalar(select(func.count()).select_from(FeedbackSource)) == 0
