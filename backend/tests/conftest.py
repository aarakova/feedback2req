import os
import re
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from feedback2req.config import Settings
from feedback2req.main import create_app

ORIGIN = "http://localhost:8000"
PASSWORD = "test-only-password-И1"


@contextmanager
def isolated_database(target="head"):
    raw = os.environ.get("F2R_TEST_DATABASE_URL")
    if not raw:
        pytest.fail(
            "Set F2R_TEST_DATABASE_URL to an isolated PostgreSQL database containing 'test'"
        )
    url = make_url(raw)
    if url.drivername != "postgresql+psycopg" or "test" not in (url.database or "").lower():
        pytest.fail("Tests require a dedicated PostgreSQL database with 'test' in its name")
    schema = "f2r_test_" + uuid4().hex
    engine = create_engine(url, hide_parameters=True)
    with engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    scoped = url.update_query_dict({"options": f"-csearch_path={schema}"})
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    config.attributes["database_url"] = scoped.render_as_string(hide_password=False)
    try:
        command.upgrade(config, target)
        yield scoped.render_as_string(hide_password=False)
    finally:
        assert re.fullmatch(r"f2r_test_[0-9a-f]{32}", schema)
        with engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        engine.dispose()


@pytest.fixture
def database_url():
    with isolated_database() as url:
        yield url


@pytest.fixture
def m01_database_url():
    with isolated_database("m01") as url:
        yield url


@pytest.fixture
def app(database_url):
    return create_app(
        Settings(
            database_url=database_url,
            allowed_origin=ORIGIN,
            local_http=True,
            login_limit=100,
            argon_memory_cost=8192,
            argon_time_cost=1,
        )
    )


@pytest.fixture
def client(app):
    with TestClient(app, base_url=ORIGIN) as client:
        client.headers["Origin"] = ORIGIN
        yield client


def signup(client, login):
    result = client.post("/api/v1/auth/register", json={"login": login, "password": PASSWORD})
    assert result.status_code == 201, result.text
    return result.json()


def signin(client, login):
    result = client.post("/api/v1/auth/session", json={"login": login, "password": PASSWORD})
    assert result.status_code == 200, result.text
    client.headers["X-CSRF-Token"] = result.json()["csrf_token"]
    return result.json()


def project(client, name="Проект И1"):
    response = client.post("/api/v1/projects", json={"name": name})
    assert response.status_code == 201, response.text
    return response.json()
