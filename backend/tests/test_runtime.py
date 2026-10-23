"""DEC-011: actual PostgreSQL transactions, failure and proxy trust boundaries."""

import os
import subprocess
import sys
from time import monotonic, sleep
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine, make_url
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from feedback2req import runtime
from feedback2req.config import Settings
from feedback2req.main import create_app

from .conftest import ORIGIN, PASSWORD, project, signin, signup

LOCK = 19758515832833874


def settings(url):
    return Settings(database_url=url, local_http=True, argon_memory_cost=8192, argon_time_cost=1)


def test_schema_and_populated_upgrade(m01_database_url):
    config = settings(m01_database_url)
    with pytest.raises(RuntimeError, match="incompatible"):
        runtime.check_schema(config)
    with TestClient(create_app(config), base_url=ORIGIN, headers={"Origin": ORIGIN}) as client:
        signup(client, "migration-owner")
        signin(client, "migration-owner")
        saved = project(client)
        runtime.migrate(config)
        runtime.check_schema(config)
        runtime.migrate(config)
        assert client.get(f"/api/v1/projects/{saved['id']}").json() == saved
        response = client.post(
            f"/api/v1/projects/{saved['id']}/sources", json={"kind": "text", "text": " ё\r\n🙂 "}
        )
        assert response.status_code == 201
        assert response.json()["text"] == " ё\r\n🙂 "


@pytest.mark.parametrize("fail", [False, True])
def test_lock_covers_ddl_and_failure_rolls_back(m01_database_url, fail):
    observer = create_engine(m01_database_url)
    observed = []

    def after_execute(conn, cursor, statement, parameters, context, executemany):
        if "CREATE TABLE feedback_sources" not in statement:
            return
        with observer.begin() as other:
            assert not other.scalar(text(f"SELECT pg_try_advisory_xact_lock({LOCK})"))
        observed.append(True)
        if fail:
            raise RuntimeError("injected migration failure")

    event.listen(Engine, "after_cursor_execute", after_execute)
    try:
        if fail:
            with pytest.raises(RuntimeError, match="injected"):
                runtime.migrate(settings(m01_database_url))
        else:
            runtime.migrate(settings(m01_database_url))
    finally:
        event.remove(Engine, "after_cursor_execute", after_execute)
    assert observed
    with observer.begin() as conn:
        assert conn.scalar(text(f"SELECT pg_try_advisory_xact_lock({LOCK})"))
        assert conn.scalar(text("SELECT version_num FROM alembic_version")) == (
            "m01" if fail else "m02a"
        )
        assert (conn.scalar(text("SELECT to_regclass('feedback_sources')")) is None) == fail
    observer.dispose()


def test_standalone_migrators_wait_for_database_lock(m01_database_url):
    name = "migrator_" + uuid4().hex
    url = make_url(m01_database_url).update_query_dict({"application_name": name})
    env = dict(
        os.environ,
        F2R_DATABASE_URL=url.render_as_string(hide_password=False),
        F2R_LOCAL_HTTP="true",
    )
    engine = create_engine(m01_database_url)
    processes = []
    try:
        with engine.begin() as lock:
            lock.execute(text(f"SELECT pg_advisory_xact_lock({LOCK})"))
            for _ in range(2):
                processes.append(
                    subprocess.Popen(
                        [sys.executable, "-m", "feedback2req.runtime", "migrate"],
                        env=env,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                    )
                )
            deadline = monotonic() + 20
            waiting = 0
            while monotonic() < deadline:
                with engine.connect() as observer:
                    waiting = observer.scalar(
                        text(
                            "SELECT count(*) FROM pg_stat_activity WHERE application_name=:name "
                            "AND wait_event_type='Lock' AND lower(wait_event)='advisory'"
                        ),
                        {"name": name},
                    )
                if waiting == 2:
                    break
                sleep(0.05)
            assert waiting == 2
            assert lock.scalar(text("SELECT version_num FROM alembic_version")) == "m01"
        for process in processes:
            process.communicate(timeout=30)
            assert process.returncode == 0
        runtime.check_schema(settings(m01_database_url))
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
                process.communicate(timeout=10)
        engine.dispose()


def test_failed_migration_never_starts_backend(monkeypatch, database_url):
    def fail(config):
        raise RuntimeError("migration failed")

    def forbidden_exec(*args):
        pytest.fail("Uvicorn must not start after migration failure")

    monkeypatch.setattr(runtime, "migrate", fail)
    monkeypatch.setattr(runtime.os, "execv", forbidden_exec)
    with pytest.raises(RuntimeError, match="migration failed"):
        runtime.backend(settings(database_url))


def test_worker_check_refuses_old_schema_without_migrating(m01_database_url):
    result = subprocess.run(
        [sys.executable, "-m", "feedback2req.runtime", "worker-check"],
        env=dict(os.environ, F2R_DATABASE_URL=m01_database_url, F2R_LOCAL_HTTP="true"),
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 1
    assert "Deployment command failed" in result.stderr
    engine = create_engine(m01_database_url)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "m01"
    engine.dispose()


def test_deployment_error_does_not_print_secret_config():
    secret = "private-config-must-not-appear"
    result = subprocess.run(
        [sys.executable, "-m", "feedback2req.runtime", "backend"],
        env=dict(os.environ, F2R_DATABASE_URL=secret, F2R_LOCAL_HTTP="true"),
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 1
    assert secret not in result.stdout + result.stderr


def test_proxy_trust_and_spoofed_headers(database_url):
    config = settings(database_url).model_copy(update={"login_limit": 2})
    app = ProxyHeadersMiddleware(create_app(config), trusted_hosts="172.28.244.2")
    # A peer other than Nginx cannot use spoofed XFF to get new rate-limit buckets.
    with TestClient(app, base_url=ORIGIN, client=("172.28.244.3", 1234)) as client:
        for number, expected in enumerate([401, 401, 429]):
            response = client.post(
                "/api/v1/auth/session",
                json={"login": "missing", "password": PASSWORD},
                headers={"Origin": ORIGIN, "X-Forwarded-For": f"192.0.2.{number}"},
            )
            assert response.status_code == expected
    # Only the configured proxy may identify different client IPs.
    app = ProxyHeadersMiddleware(create_app(config), trusted_hosts="172.28.244.2")
    with TestClient(app, base_url=ORIGIN, client=("172.28.244.2", 1234)) as client:
        for number in range(3):
            response = client.post(
                "/api/v1/auth/session",
                json={"login": "missing", "password": PASSWORD},
                headers={"Origin": ORIGIN, "X-Forwarded-For": f"192.0.2.{number}"},
            )
            assert response.status_code == 401
