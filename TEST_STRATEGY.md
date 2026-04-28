# Test strategy — Order Processing (Lead SDET assignment)

## Scope and intent

This submission treats the Order Processing stack (React DataApp, FastAPI, Postgres) as a **reference implementation** while designing automation that could be repointed at another customer solution. In scope: authentication and authorisation boundaries, order lifecycle (create, list with filters, detail, update, delete contract), CSV bulk ingest, aggregate statistics, pagination, and observability hooks. Explicitly **out of scope** for this time-box: full visual regression, performance/load testing, security penetration testing, mobile browsers beyond Chromium, and third-party SaaS reporting (the insights dashboard is self-hosted OSS only).

## Risk-based prioritisation

1. **Data integrity and money-adjacent behaviour** — Order totals and CSV import use floating-point arithmetic; duplicate `external_id` on retry can inflate revenue and inventory. **Mitigation:** API-level tests encoding decimal-safe totals and idempotent ingest (marked `xfail` until fixed), plus manual characterisation in the bug report.
2. **Authorisation gaps** — `/orders/stats` is callable without a bearer token in the current build, leaking portfolio-level aggregates. **Mitigation:** contract test expecting `401`, currently `xfail`.
3. **Pagination correctness** — Off-by-one offset causes overlapping pages, so list views silently duplicate rows. **Mitigation:** API test comparing disjoint ID sets across pages (`xfail`).
4. **Regression speed** — Happy-path API tests (auth, CRUD, RBAC) run on every PR against a real Postgres schema via `PYTEST_DATABASE_URL` (CI) or testcontainers (local Docker). They guard refactors without standing up the full UI.
5. **UI stability** — Playwright covers login and orders table smoke; a **deliberately failing** tagged spec exists for dashboard triage demos and is excluded from CI via title grep.

## Pyramid and tooling

| Layer | Tooling | What it proves |
|-------|---------|----------------|
| Unit | Vitest + Testing Library | Isolated component rules (e.g. pagination total-page calculation intent). |
| Service / API | pytest + httpx ASGI transport + Postgres | Contracts, RBAC, pagination, CSV behaviour, structured logging touchpoints. |
| E2E | Playwright (Chromium) | Critical paths through the deployed containers; videos/traces on failure. |

CI publishes JUnit XML, coverage XML, and Playwright HTML/JSON under `test-results/` and uploads them as GitHub Actions artifacts. Pytest uses `--reruns 2` as a lightweight flake harness; coverage must stay at or above `app/backend/coverage_baseline.txt` so lowering quality requires an explicit baseline update.

## Extensibility to other solution shapes

The framework lives in `qe_toolkit/` at the repo root and is consumed by every customer-specific module — the backend conftest, the two CI scripts, and the dashboard. A new customer onboarding gets the same fixtures, gates, and reporting without copy-pasting code (see `docs/ONBOARDING_NEW_CUSTOMER.md` for the full recipe). The customer-side conftest is roughly 30 lines and only describes what is genuinely different about that app:

```python
# app/<customer>/tests/conftest.py
from qe_toolkit.pytest_fixtures import (
    asgi_client, patch_engine_to_nullpool, register_and_login, run_alembic_migrations,
)

pytest_plugins = ["qe_toolkit.pytest_fixtures"]   # postgres_url + honest-CI hook

@pytest.fixture(scope="session")
def database_ready(postgres_url):
    os.environ["DATABASE_URL"] = postgres_url
    run_alembic_migrations(SERVICE_DIR)

@pytest.fixture(scope="session")
def asgi_app(database_ready):
    from app import database; from app.config import settings
    patch_engine_to_nullpool(database, settings.DATABASE_URL)
    from app.main import app
    return app
```

Concrete payoffs for the brief's three "different customer" scenarios:

- **API-only services.** Same conftest shape; the frontend and Playwright jobs drop out. Coverage and flake-flag gates run unchanged because they're pure XML parsers in `qe_toolkit.coverage_gate` and `qe_toolkit.junit`.
- **LLM / eval pipelines.** Replace Playwright with an eval harness that emits JUnit-compatible XML (most do). The dashboard already aggregates any `junit*.xml` under `test-results/`; the parser is in `qe_toolkit.junit`.
- **Performance / concurrency.** Add a non-blocking workflow dispatching k6 or Locust and write metrics JSON next to test artifacts. The dashboard's SQLite schema already carries a `project` column, so multi-tenant trends are a `?project=<name>` away — the page picker is wired.

## Deferrals (judgment)

- Full accessibility audit (axe) on every PR — noted as next step; one Vitest `it.fails` documents a labelling gap.
- Multi-browser matrices — Chromium only to keep CI wall-clock predictable.
- Contract testing of external payment gateways — not applicable to this sample domain.

See `docs/DEFINITION_OF_DONE.md` for the shipping bar used in CI commentary.
