"""Reuse approved isolated PG fixtures; never connect without an explicit test URL."""

pytest_plugins = ("backend.tests.conftest",)
