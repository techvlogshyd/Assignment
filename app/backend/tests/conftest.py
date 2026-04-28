"""Customer-specific pytest wiring for the Order Processing backend.

Generic building blocks live in ``qe_toolkit.pytest_fixtures`` and are
loaded as a pytest plugin (see ``pytest_plugins`` below). This file only
defines what is genuinely Order-Processing-specific: the alembic dir, the
``app.main:app`` import path, the role-token fixtures, and the ``many_orders``
seeding fixture. A new customer would have a similarly small conftest that
points at *their* app.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from httpx import AsyncClient

from qe_toolkit.pytest_fixtures import (
    asgi_client as _asgi_client,
    patch_engine_to_nullpool,
    register_and_login,
    run_alembic_migrations,
)

# Re-export qe_toolkit's session-scoped fixtures and pytest hooks.
pytest_plugins = ["qe_toolkit.pytest_fixtures"]

BACKEND_DIR = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Customer-specific bootstrap (composes qe_toolkit helpers)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def database_ready(postgres_url: str) -> None:
    os.environ["DATABASE_URL"] = postgres_url
    os.environ.setdefault("SECRET_KEY", "test-secret-key-for-ci-and-local-pytest-only")
    run_alembic_migrations(BACKEND_DIR)


@pytest.fixture(scope="session")
def asgi_app(database_ready: None):
    from app import database
    from app.config import settings

    patch_engine_to_nullpool(database, settings.DATABASE_URL)
    from app.main import app

    return app


@pytest.fixture
async def client(asgi_app) -> AsyncIterator[AsyncClient]:
    async for c in _asgi_client(asgi_app):
        yield c


# ---------------------------------------------------------------------------
# Role tokens — Order Processing has admin/editor/viewer
# ---------------------------------------------------------------------------

async def _token_for_role(client: AsyncClient, role: str) -> str:
    import uuid as _uuid

    return await register_and_login(
        client,
        payload={
            "email": f"pytest-{role}-{_uuid.uuid4().hex[:8]}@example.com",
            "password": "password123",
            "role": role,
        },
    )


@pytest.fixture
async def admin_token(client: AsyncClient) -> str:
    return await _token_for_role(client, "admin")


@pytest.fixture
async def editor_token(client: AsyncClient) -> str:
    return await _token_for_role(client, "editor")


@pytest.fixture
async def viewer_token(client: AsyncClient) -> str:
    return await _token_for_role(client, "viewer")


# ---------------------------------------------------------------------------
# Domain seeding fixture
# ---------------------------------------------------------------------------

@pytest.fixture
async def many_orders(client: AsyncClient, editor_token: str) -> None:
    """Create enough orders to exercise pagination (page size 20)."""
    headers = {"Authorization": f"Bearer {editor_token}"}
    for i in range(25):
        await client.post(
            "/orders",
            headers=headers,
            json={
                "external_id": f"PAG-{i:04d}",
                "customer_name": f"Customer {i}",
                "items": [{"name": "Item", "price": 10.0, "quantity": 1}],
                "status": "pending",
            },
        )
