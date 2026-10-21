"""Restart only the disposable I1 API and PostgreSQL; never a user database.

Requires F2R_TEST_DATABASE_URL. Compose mode uses compose.test.yaml exclusively.
Native mode accepts only this repository's .local/i1-postgres cluster.
"""

import argparse
import os
import re
import socket
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4

import httpx
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]


def run(*args):
    subprocess.run(args, cwd=ROOT, check=True, stdout=subprocess.DEVNULL)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pg-ctl", type=Path, help="Native pg_ctl; otherwise use test Compose"
    )
    args = parser.parse_args()
    url = make_url(os.environ["F2R_TEST_DATABASE_URL"])
    if (
        url.drivername != "postgresql+psycopg"
        or url.database != "feedback2req_i1_test"
        or url.host not in {"127.0.0.1", "localhost"}
    ):
        raise RuntimeError("Only loopback feedback2req_i1_test is allowed")
    data = (ROOT / ".local" / "i1-postgres").resolve()
    if args.pg_ctl:
        if (
            not data.is_relative_to(ROOT / ".local")
            or not (data / "PG_VERSION").is_file()
        ):
            raise RuntimeError("Expected dedicated .local/i1-postgres cluster")
    else:
        if url.port != 55433:
            raise RuntimeError("Test Compose requires port 55433")
    schema = "f2r_test_" + uuid4().hex
    engine = create_engine(url, hide_parameters=True)
    with engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    scoped = url.update_query_dict({"options": f"-csearch_path={schema}"})
    config = Config(str(ROOT / "backend" / "alembic.ini"))
    config.attributes["database_url"] = scoped.render_as_string(hide_password=False)
    command.upgrade(config, "head")
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        api_port = sock.getsockname()[1]
    origin = f"http://127.0.0.1:{api_port}"
    env = os.environ.copy()
    env.update(
        {
            "F2R_DATABASE_URL": scoped.render_as_string(hide_password=False),
            "F2R_ALLOWED_ORIGIN": origin,
            "F2R_LOCAL_HTTP": "true",
        }
    )
    process = None

    def start_api():
        nonlocal process
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "feedback2req.main:create_app",
                "--factory",
                "--host",
                "127.0.0.1",
                "--port",
                str(api_port),
                "--no-access-log",
                "--no-proxy-headers",
            ],
            env=env,
            cwd=ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        for _ in range(100):
            if process.poll() is not None:
                raise RuntimeError("API process exited before startup")
            try:
                if (
                    httpx.get(origin + "/api/v1/auth/session", timeout=1).status_code
                    == 401
                ):
                    return
            except httpx.TransportError:
                pass
            time.sleep(0.2)
        raise RuntimeError("API startup timed out")

    def stop_api():
        if process and process.poll() is None:
            process.terminate()
            process.wait(timeout=15)

    def restart_postgres():
        engine.dispose()
        if args.pg_ctl:
            run(str(args.pg_ctl), "-D", str(data), "-m", "fast", "-w", "stop")
            run(
                str(args.pg_ctl),
                "-D",
                str(data),
                "-l",
                str(ROOT / ".local/i1-postgres.log"),
                "-o",
                f"-h 127.0.0.1 -p {url.port}",
                "-w",
                "start",
            )
        else:
            run("docker", "compose", "-f", "compose.test.yaml", "stop", "db")
            run(
                "docker",
                "compose",
                "-f",
                "compose.test.yaml",
                "up",
                "-d",
                "--wait",
                "db",
            )

    password = "restart-test-" + uuid4().hex

    def account(client, login):
        body = {"login": login, "password": password}
        response = client.post("/api/v1/auth/register", json=body)
        assert response.status_code == 201
        user_id = response.json()["id"]
        response = client.post("/api/v1/auth/session", json=body)
        assert response.status_code == 200
        client.headers["X-CSRF-Token"] = response.json()["csrf_token"]
        return user_id

    try:
        start_api()
        with (
            httpx.Client(base_url=origin, headers={"Origin": origin}) as owner,
            httpx.Client(base_url=origin, headers={"Origin": origin}) as member,
        ):
            account(owner, "owner")
            revoked_cookie = owner.cookies.get("f2r_session")
            assert owner.delete("/api/v1/auth/session").status_code == 204
            response = owner.post(
                "/api/v1/auth/session", json={"login": "owner", "password": password}
            )
            owner.headers["X-CSRF-Token"] = response.json()["csrf_token"]
            member_id = account(member, "member")
            response = owner.post(
                "/api/v1/projects", json={"name": "Сохранится после restart"}
            )
            assert response.status_code == 201
            project_id = response.json()["id"]
            path = "/api/v1/projects/" + project_id
            assert (
                owner.put(
                    path + "/access/" + member_id, json={"can_approve": True}
                ).status_code
                == 200
            )
            # Actual API OS process is stopped; PostgreSQL is stopped and started using the same data.
            stop_api()
            restart_postgres()
            start_api()
            assert owner.get("/api/v1/auth/session").status_code == 200
            assert owner.get(path).json()["name"] == "Сохранится после restart"
            assert owner.get(path).json()["permissions"]["is_owner"]
            assert member.get(path).json()["permissions"]["can_approve"]
            assert len(owner.get(path + "/access").json()["items"]) == 2
            with httpx.Client(base_url=origin) as revoked:
                revoked.cookies.set("f2r_session", revoked_cookie)
                assert revoked.get("/api/v1/auth/session").status_code == 401
            # Persist a changed name and revoked access through a second real restart.
            assert (
                owner.patch(path, json={"name": "После второго restart"}).status_code
                == 200
            )
            assert owner.delete(path + "/access/" + member_id).status_code == 204
            stop_api()
            restart_postgres()
            start_api()
            assert owner.get(path).json()["name"] == "После второго restart"
            assert member.get(path).status_code == 404
        print(
            "PASS: two API process + PostgreSQL stop/start cycles; accounts, session/revocation, "
            "project name, owner rights, access grant/revocation persisted"
        )
    finally:
        stop_api()
        assert re.fullmatch(r"f2r_test_[0-9a-f]{32}", schema)
        with engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        engine.dispose()


if __name__ == "__main__":
    main()
