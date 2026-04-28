"""Reusable pytest building blocks for FastAPI services backed by Postgres.

Customers should declare ``pytest_plugins = ["qe_toolkit.pytest_fixtures"]``
in their conftest to gain ``postgres_url``, then compose their own
``database_ready`` and ``asgi_app`` fixtures using the helpers below.

The split between *fixtures* and *helpers* is deliberate: the fixture
points are reusable as-is across customers, but ``database_ready`` and the
ASGI app injection are inevitably customer-specific (they reference the
customer's alembic directory and the import path of their app object).
"""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient


# ---------------------------------------------------------------------------
# Session-scoped Postgres source
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def postgres_url() -> str:
    """Yield an asyncpg-style URL.

    CI sets ``PYTEST_DATABASE_URL`` and we use it directly.
    Locally, we try testcontainers; if Docker is unavailable we ``skip`` the
    test so the suite is honest rather than failing for environmental reasons.
    """
    explicit = os.environ.get("PYTEST_DATABASE_URL")
    if explicit:
        yield explicit
        return
    try:
        from testcontainers.postgres import PostgresContainer

        postgres = PostgresContainer("postgres:15")
        postgres.start()
    except Exception as exc:  # noqa: BLE001 — docker daemon, image pull, etc.
        pytest.skip(
            "Postgres for integration tests unavailable "
            "(start Docker, or export PYTEST_DATABASE_URL). "
            f"Underlying error: {exc!r}"
        )
    url = postgres.get_connection_url().replace(
        "postgresql://", "postgresql+asyncpg://", 1
    )
    try:
        yield url
    finally:
        postgres.stop()


# ---------------------------------------------------------------------------
# Composable helpers — call from a customer-specific fixture
# ---------------------------------------------------------------------------

def run_alembic_migrations(cwd: Path) -> None:
    """Run ``alembic upgrade head`` from the given working directory.

    The customer is responsible for ensuring ``DATABASE_URL`` is set in the
    environment before this is called (typical pattern: bind ``postgres_url``
    into ``DATABASE_URL`` inside ``database_ready``).
    """
    env = os.environ.copy()
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=str(cwd),
        check=True,
        env=env,
    )


def patch_engine_to_nullpool(database_module: Any, database_url: str) -> None:
    """Rebuild ``database_module.engine`` with ``NullPool`` for test runs.

    pytest-asyncio runs each test on a fresh event loop. asyncpg connections
    pooled by SQLAlchemy would be bound to whichever loop created them, then
    fail with "another operation is in progress" the next test. ``NullPool``
    creates a fresh connection per request — slower, but bulletproof.

    Customers call this after their app modules have imported ``database`` but
    before any test traffic flows through it.
    """
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    database_module.engine = create_async_engine(
        database_url, echo=False, poolclass=NullPool
    )
    database_module.async_session_factory = async_sessionmaker(
        database_module.engine, expire_on_commit=False
    )


async def asgi_client(asgi_app: Any) -> AsyncIterator[AsyncClient]:
    """Async context manager-friendly httpx client over an ASGI app.

    Customers typically wrap this in a ``@pytest.fixture`` of their own to
    bind their ``asgi_app`` fixture name; we keep this as a plain async
    generator so it's reusable in non-pytest contexts too (e.g. a smoke
    runner script).
    """
    transport = ASGITransport(app=asgi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def register_and_login(
    client: AsyncClient,
    *,
    register_path: str = "/auth/register",
    login_path: str = "/auth/login",
    payload: dict[str, Any],
    token_field: str = "access_token",
) -> str:
    """Generic register-then-login flow returning the bearer token.

    Customers pass their app-specific ``payload`` (email/password/role on this
    repo, but could be username/api_key elsewhere). ``register_path`` and
    ``login_path`` default to the Order Processing shape but are overridable.
    """
    r = await client.post(register_path, json=payload)
    assert r.status_code == 201, r.text
    login_payload = {k: v for k, v in payload.items() if k in ("email", "username", "password")}
    r2 = await client.post(login_path, json=login_payload)
    assert r2.status_code == 200, r2.text
    return r2.json()[token_field]


# ---------------------------------------------------------------------------
# Honest-CI guardrail (pytest hook)
# ---------------------------------------------------------------------------

_ci_call_outcomes = 0


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):  # noqa: ARG001 — pytest hook signature
    outcome = yield
    rep = outcome.get_result()
    global _ci_call_outcomes
    if rep.when == "call":
        _ci_call_outcomes += 1


def pytest_sessionfinish(session, exitstatus):  # noqa: ARG001 — pytest hook signature
    """Fail in CI if zero tests reached the call phase.

    Prevents 'green by skip' runs when integration infrastructure is
    misconfigured. Set the ``CI`` env var to opt in (default behaviour is
    unchanged for local dev where skipping is expected).
    """
    if os.environ.get("CI") != "true":
        return
    if _ci_call_outcomes == 0:
        session.exitstatus = 1
        print(
            "ERROR: No tests reached the call phase (likely all skipped). "
            "Check Postgres service and PYTEST_DATABASE_URL.",
            file=sys.stderr,
        )
