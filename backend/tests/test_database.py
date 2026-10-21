import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError

from feedback2req.persistence.models import Base, Project, ProjectAccess, Session, User

from .conftest import project, signin, signup


def test_empty_database_upgrade(database_url):
    """M01: migrate a genuinely empty disposable database with the public schema."""
    name = "f2r_test_" + uuid4().hex
    root_url = make_url(database_url).difference_update_query(["options"])
    admin = create_engine(root_url, isolation_level="AUTOCOMMIT", hide_parameters=True)
    with admin.connect() as connection:
        connection.execute(text(f'CREATE DATABASE "{name}"'))
    empty_url = root_url.set(database=name)
    engine = create_engine(empty_url, hide_parameters=True)
    try:
        assert inspect(engine).get_table_names() == []
        config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
        config.attributes["database_url"] = empty_url.render_as_string(hide_password=False)
        command.upgrade(config, "head")
        assert set(inspect(engine).get_table_names()) == {
            "alembic_version",
            "users",
            "sessions",
            "projects",
            "project_access",
        }
    finally:
        engine.dispose()
        with admin.connect() as connection:
            connection.execute(text(f'DROP DATABASE "{name}"'))
        admin.dispose()


def test_migration_and_constraints(client, app, database_url):
    """M01 / FR-001,032: real PostgreSQL DDL, referential integrity and uniqueness."""
    inspector = inspect(app.state.engine)
    assert set(inspector.get_table_names()) == {
        "alembic_version",
        "users",
        "sessions",
        "projects",
        "project_access",
    }
    user = signup(client, "owner")
    signin(client, "owner")
    p = project(client)
    member = signup(client, "member")
    with app.state.engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "m01"
        assert connection.scalar(text("SHOW server_version")).split(".")[0].isdigit()
        assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
    now = datetime.now(UTC)

    def invalid_session(**changes):
        values = dict(
            token_hash=uuid4().hex * 2,
            user_id=UUID(user["id"]),
            csrf_secret="test-only",
            created_at=now,
            last_seen_at=now,
            expires_at=now + timedelta(days=1),
        )
        values.update(changes)
        return Session(**values)

    invalid_records = [
        User(id=uuid4(), login="owner", password_hash="unused"),
        Project(id=uuid4(), owner_id=uuid4(), name="orphan", execution_mode="mock"),
        Project(id=uuid4(), owner_id=UUID(user["id"]), name=" ", execution_mode="mock"),
        Project(id=uuid4(), owner_id=UUID(user["id"]), name="x", execution_mode="other"),
        ProjectAccess(project_id=uuid4(), user_id=UUID(user["id"]), can_approve=False),
        ProjectAccess(project_id=UUID(p["id"]), user_id=uuid4(), can_approve=False),
        invalid_session(user_id=uuid4()),
        invalid_session(expires_at=now),
        invalid_session(last_seen_at=now - timedelta(seconds=1)),
        invalid_session(token_hash="short"),
    ]
    for record in invalid_records:
        with pytest.raises(IntegrityError), app.state.sessions.begin() as tx:
            tx.add(record)
            tx.flush()
    with app.state.sessions.begin() as tx:
        tx.add(
            ProjectAccess(project_id=UUID(p["id"]), user_id=UUID(member["id"]), can_approve=True)
        )
    with pytest.raises(IntegrityError), app.state.sessions.begin() as tx:
        tx.add(
            ProjectAccess(project_id=UUID(p["id"]), user_id=UUID(member["id"]), can_approve=False)
        )
        tx.flush()
    # Applying head a second time must preserve existing rows.
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    config.attributes["database_url"] = database_url
    command.upgrade(config, "head")
    with app.state.sessions() as tx:
        assert tx.get(User, UUID(user["id"])).login == "owner"


def test_fresh_process(client, app, database_url):
    """M01: a new Python API instance reads persisted accounts, sessions and rights."""
    signup(client, "owner")
    signin(client, "owner")
    p = project(client)
    app.state.engine.dispose()
    env = os.environ.copy()
    env.update(
        {
            "F2R_DATABASE_URL": database_url,
            "F2R_LOCAL_HTTP": "true",
            "F2R_TEST_SESSION_TOKEN": client.cookies["f2r_session"],
            "F2R_TEST_PROJECT_ID": p["id"],
        }
    )
    code = """
import os
from fastapi.testclient import TestClient
from feedback2req.main import create_app
with TestClient(create_app(), base_url='http://localhost:8000') as client:
    client.cookies.set('f2r_session', os.environ['F2R_TEST_SESSION_TOKEN'])
    assert client.get('/api/v1/auth/session').status_code == 200
    response = client.get('/api/v1/projects/' + os.environ['F2R_TEST_PROJECT_ID'])
    assert response.status_code == 200
    assert response.json()['permissions']['is_owner']
"""
    result = subprocess.run(
        [sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=30
    )
    assert result.returncode == 0, result.stderr
