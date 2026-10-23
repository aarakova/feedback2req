"""Serve F1a browser checks with a unique schema in a dedicated PostgreSQL test DB."""

import os
import sys
from pathlib import Path

import uvicorn

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.tests.conftest import isolated_database

from feedback2req.config import Settings
from feedback2req.main import create_app


def main():
    with isolated_database() as database_url:
        app = create_app(
            Settings(
                database_url=database_url,
                allowed_origin=os.environ.get("F2R_E2E_ORIGIN", "http://localhost:5173"),
                local_http=True,
                login_limit=1000,
                page_size=2,
                argon_memory_cost=8192,
                argon_time_cost=1,
            )
        )
        uvicorn.run(
            app,
            host=os.environ.get("F2R_E2E_HOST", "127.0.0.1"),
            port=18000,
            access_log=False,
            proxy_headers=False,
        )


if __name__ == "__main__":
    main()
