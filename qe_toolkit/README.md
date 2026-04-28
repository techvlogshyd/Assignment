# qe_toolkit — reusable QE building blocks

A small Python package extracted from this assignment so a second customer solution can adopt the same testing and reporting infrastructure without copy-pasting code. The Order Processing app uses every module here:

| Module | Used by | What it provides |
|--------|---------|------------------|
| `qe_toolkit.pytest_fixtures` | `app/backend/tests/conftest.py` | `postgres_url` session fixture (testcontainers + `PYTEST_DATABASE_URL` fallback), `run_alembic_migrations`, `patch_engine_to_nullpool`, `register_and_login` helper, honest-CI guardrail hook |
| `qe_toolkit.junit` | `dashboard/main.py`, `scripts/flag_flakes_from_junit.py` | `parse_junit_files(root)` and `find_flakes(root)` — works on any JUnit XML |
| `qe_toolkit.playwright` | `dashboard/main.py` | `parse_playwright_json(path, artifacts_root)` — Playwright JSON reporter parser with attachment URL rewriting |
| `qe_toolkit.coverage_gate` | `scripts/check_coverage_vs_baseline.py` | `line_coverage_percent`, `check_against_baseline` |

## Onboarding a new customer

See `docs/ONBOARDING_NEW_CUSTOMER.md` at the repo root for step-by-step instructions.

## Why no `pyproject.toml`

For the assignment time-box this is a `pythonpath = ../..` repo-local package, so it works without a packaging story. Promoting to a real package would mean adding `pyproject.toml`, a release pipeline, and an internal index — out of scope, but the module boundaries are already drawn so the lift is mechanical.
