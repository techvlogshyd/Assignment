# Onboarding a new customer solution to this QE framework

The `qe_toolkit/` package at the repo root is the shared QE framework. The Order Processing app is the *first* customer of it; this guide describes onboarding the *second* customer ("new-app") so the framework lives up to the brief: "the next engineer points it at a completely different customer solution tomorrow."

## What is reusable as-is (no edits)

- **Postgres source.** `qe_toolkit.pytest_fixtures.postgres_url` — testcontainers locally, `PYTEST_DATABASE_URL` in CI.
- **Engine NullPool patch.** `qe_toolkit.pytest_fixtures.patch_engine_to_nullpool(database_module, url)` — sidesteps pytest-asyncio's per-test event-loop trap.
- **Honest-CI guardrail.** `pytest_sessionfinish` hook in the same plugin fails CI runs that produce zero call-phase tests.
- **Generic register/login.** `qe_toolkit.pytest_fixtures.register_and_login` — pass your own auth payload shape.
- **JUnit and Playwright parsers.** `qe_toolkit.junit.parse_junit_files`, `qe_toolkit.junit.find_flakes`, `qe_toolkit.playwright.parse_playwright_json` — vendor-neutral.
- **Coverage gate.** `qe_toolkit.coverage_gate.check_against_baseline(coverage_xml, baseline_txt)`.
- **Dashboard.** Already multi-project — set `DASHBOARD_PROJECT=new-app` and the same dashboard ingests new-app's artifacts on a separate timeline.

## What you write per customer

Create the customer's directory, e.g. `app/new-app/`, mirroring `app/backend/`.

### 1. Conftest (~30 lines, mostly composition)

```python
# app/new-app/tests/conftest.py
import os
from pathlib import Path

import pytest
from httpx import AsyncClient

from qe_toolkit.pytest_fixtures import (
    asgi_client as _asgi_client,
    patch_engine_to_nullpool,
    register_and_login,
    run_alembic_migrations,
)

pytest_plugins = ["qe_toolkit.pytest_fixtures"]
SERVICE_DIR = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def database_ready(postgres_url: str) -> None:
    os.environ["DATABASE_URL"] = postgres_url
    os.environ.setdefault("SECRET_KEY", "test-secret")
    run_alembic_migrations(SERVICE_DIR)


@pytest.fixture(scope="session")
def asgi_app(database_ready: None):
    from app import database
    from app.config import settings
    patch_engine_to_nullpool(database, settings.DATABASE_URL)
    from app.main import app
    return app


@pytest.fixture
async def client(asgi_app):
    async for c in _asgi_client(asgi_app):
        yield c


# ---- customer-specific role tokens (or whatever auth shape this app has) ----
@pytest.fixture
async def superuser_token(client: AsyncClient) -> str:
    return await register_and_login(
        client,
        register_path="/api/v1/users",
        login_path="/api/v1/auth/token",
        payload={"username": "superuser", "password": "test", "is_superuser": True},
    )
```

### 2. `pytest.ini`

```ini
[pytest]
asyncio_mode = auto
testpaths = tests
pythonpath = . ../..   ; ../.. exposes qe_toolkit at the repo root
```

### 3. CI job

Copy the `backend` job in `.github/workflows/ci.yml`, change the `working-directory`, and update the JUnit/coverage paths. Keep the `Coverage regression vs baseline` and `Flake flag` steps — they call into `qe_toolkit` and need no per-customer edits.

### 4. Dashboard project name

Set `DASHBOARD_PROJECT=new-app` for the new dashboard ingest job. The dashboard already supports `?project=new-app` as a URL query parameter for filtering, and shows a project picker in the header when more than one project has runs.

## What is *not* in scope of this framework (intentional non-goals)

- **Customer-specific seeding fixtures.** `many_orders` lives in `app/backend/tests/conftest.py`; new-app would have its own seed helpers. The framework does not try to abstract domain models.
- **Domain-specific contract tests.** The encoded-bug `xfail strict=True` and Vitest `it.fails` patterns are documented in `TEST_STRATEGY.md` but each customer writes their own.
- **UI-test authoring conventions.** Playwright is the chosen tool, but page objects, selectors, and helper utilities belong in each customer's `e2e/` directory.

## Acceptance criteria for a successful onboarding

- The new customer's CI job runs pytest with `--junitxml`, `--cov-report=xml`, and `--reruns 2`. The reused gate scripts pass.
- Test artifacts land under a path included in the dashboard's artifact mount.
- The dashboard, with `DASHBOARD_PROJECT=new-app`, shows newly failing / flaky / trends for the new-app suite — separately from the Order Processing timeline.
- No edits to `qe_toolkit/` were needed. If you found yourself editing the toolkit to ship the new customer, that's a sign a generic abstraction is missing — file an issue and either generalise or push the workaround into the customer-side conftest.
