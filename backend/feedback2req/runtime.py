"""Local deployment commands; no job executor or queue is implemented here."""

import argparse
import json
import os
import sys
from ipaddress import ip_address
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener

from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text

from feedback2req.config import Settings


def migration_config(database_url: str) -> Config:
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.attributes["database_url"] = database_url
    return config


def migrate(settings: Settings):
    # The lock belongs to Alembic env.py, not just this particular launcher.
    command.upgrade(migration_config(settings.database_url), "head")


def check_schema(settings: Settings):
    expected = set(ScriptDirectory.from_config(migration_config(settings.database_url)).get_heads())
    engine = create_engine(
        settings.database_url, hide_parameters=True, connect_args={"connect_timeout": 3}
    )
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            current = set(MigrationContext.configure(connection).get_current_heads())
            if current != expected:
                raise RuntimeError("Database schema is incompatible with this image")
    finally:
        engine.dispose()


def check_http():
    # No new public endpoint and no cookie; do not read proxy environment vars.
    request = Request("http://127.0.0.1:8000/api/v1/auth/session")
    try:
        with build_opener(ProxyHandler({})).open(request, timeout=2):
            raise RuntimeError("Anonymous session unexpectedly succeeded")
    except HTTPError as response:
        with response:
            if response.code != 401 or json.load(response)["error"]["code"] != "unauthenticated":
                raise RuntimeError("Backend HTTP readiness failed") from None


def backend(settings: Settings):
    proxy = os.environ.get("F2R_TRUSTED_PROXY_IP", "")
    # Accept exactly one explicit address, never '*' or an arbitrary network.
    flags = (
        ["--proxy-headers", "--forwarded-allow-ips", str(ip_address(proxy))]
        if proxy
        else ["--no-proxy-headers"]
    )
    migrate(settings)
    check_schema(settings)
    args = [
        sys.executable,
        "-m",
        "uvicorn",
        "feedback2req.main:create_app",
        "--factory",
        "--host",
        "0.0.0.0",
        "--port",
        "8000",
        "--no-access-log",
        *flags,
    ]
    # Uvicorn replaces the launcher and receives Docker shutdown signals directly.
    os.execv(sys.executable, args)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["backend", "migrate", "check", "worker-check"])
    parser.add_argument("--http", action="store_true")
    args = parser.parse_args()
    try:
        settings = Settings()
        if args.action == "backend":
            backend(settings)
        elif args.action == "migrate":
            migrate(settings)
        else:
            check_schema(settings)
            if args.http:
                check_http()
            if args.action == "worker-check":
                print("Worker infrastructure check passed; job execution awaits I2b approval.")
    except Exception:
        # SQL/URL/config validation exceptions can contain secrets. Fail closed.
        print(
            "Deployment command failed; check configuration, database and schema.", file=sys.stderr
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
