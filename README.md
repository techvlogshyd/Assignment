# Order Processing — Lead SDET Assignment

Welcome, and thank you for taking the time to work on this assignment. We have designed it to mirror a real slice of quality engineering work at RapidCanvas. There are no trick questions — we want to see how you think, how you prioritise, and how you use your tools.

---

## Context

You are joining the quality engineering function at RapidCanvas, where engineering teams deploy React DataApps and FastAPI services to production on our platform. Your job is to help teams ship with confidence. This assignment mirrors a real slice of that work.

RapidCanvas builds solutions for many different customers. Each solution can look very different — some are UI-heavy DataApps, some are pure API services, some involve LLM pipelines that need evaluation frameworks, some require performance and concurrency harnesses, and many require a combination of all of these. A key part of the Lead SDET role is designing test infrastructure that is not purpose-built for one app, but is extensible enough to onboard new customer solutions without starting from scratch each time.

**Keep this in mind throughout the assignment.** The Order Processing app is your test subject, but the infrastructure you build around it — your test framework, fixtures, reporting, and CI gates — should be designed as if the next engineer will point it at a completely different customer solution tomorrow. Your strategy document should explicitly address how your design accommodates that.

---

## The System

The app you will be working with is an **Order Processing** service: a React frontend that lets users create, view, filter, and bulk-upload orders, backed by a FastAPI service that persists data to Postgres.

```
React DataApp → FastAPI Backend → Postgres
```

The app has non-trivial issues across all layers. Finding, characterising, and demonstrating those issues is central to Part 1.

---

## Getting Started

```bash
git clone <your-private-fork>
cd Assignment
docker-compose -f infra/docker-compose.yml up --build
# App:  http://localhost:3000
# API:  http://localhost:8000/docs
# Seed data is applied automatically on first run
```

**Credentials:**
| Email | Password | Role |
|---|---|---|
| admin@example.com | password123 | admin |
| editor@example.com | password123 | editor |
| viewer@example.com | password123 | viewer |

---

## Part 1 — Quality Engineering (Primary Deliverable)

This is the main event. We expect 80% of your time here.

### 1. Test Strategy Document (1–2 pages)

Write this first. Cover: what you will test and at what layer, what is explicitly out of scope, and a risk-based prioritisation of the issues you have found. This is the first thing reviewers read, and a strong strategy doc can carry a submission even when the test suite is incomplete.

Critically, your strategy doc must address **scalability of the test infrastructure itself**: how would your framework extend to a solution that has no UI (API-only), or one that is entirely an LLM pipeline requiring eval harnesses, or one that needs a performance/concurrency suite? You do not need to build all of these — but your design decisions should make it clear you have thought about them. A framework that only works for this one app is not at bar.

### 2. Tests

Write tests that give you confidence in the system. There are no constraints on tooling, layer, or format — use whatever combination of UI tests, API tests, unit tests, or integration tests you think best covers the risk surface you identified in your strategy doc.

What we care about: do your tests actually catch the bugs you found? Would they catch a regression if someone "fixed" the bug incorrectly? The choice of what to test, at what layer, and with which tools is itself part of the signal.

### 3. Bug Discovery Report (Markdown)

Document every issue you find: severity, steps to reproduce, evidence (logs, screenshots, test output), suspected root cause, and recommended fix. We score depth and reasoning, not count. A well-analysed bug beats five bullet points.

### 4. Logging Gap-Fill

Identify where structured logging is missing or insufficient and add it. Explain your choices. Don't add a log statement to every line — add logs where they materially improve debuggability.

### 5. CI Pipeline (GitHub Actions)

Wire up `.github/workflows/` to run your pyramid on every PR. The pipeline should:
- Fail on coverage regression.
- Include basic flake detection (re-run + flag).
- Publish test artifacts (reports, screenshots, traces).

Include a one-paragraph written **definition of done** for any feature shipping on this system.

---

## Part 2 — Test Insights Dashboard

See `automation-framework/dashboard/README.md` for the full brief.

This part is intentionally open-ended. Your architecture and scoping decisions are the signal. Time-box it — a working, focused dashboard beats an impressive incomplete one.

**Acceptance demo:** Run your Part 1 suite (including a deliberately failing E2E), then open your dashboard and walk us through how you would triage on a Monday morning.

---

## AI Usage

You are encouraged to use any AI tooling. We evaluate what you effectively built and the judgment you applied — not raw effort or line count.

**Required deliverable: AI Decision Journal** (markdown, ~2 pages):
- The 5–10 most consequential prompts you used and why.
- Where AI was wrong or misleading and how you caught it.
- What you deliberately did not delegate to AI and why.
- One example of an AI suggestion you overrode, with your reasoning.

---

## Submission

1. Work in your private fork.
2. Open a PR when done (Day 5 target).
3. Record a 15–20 minute async walkthrough video covering: your bug report, your test strategy, how to run the CI pipeline, and the dashboard Monday-morning triage demo.
4. A 90-minute live review will follow: 60 min deep-dive on your PR, 30 min live AI orchestration task we will give you fresh on the day.

---

## Time Expectation

We expect **15–20 hours self-paced over 3–5 calendar days**. If you are significantly over this, you are probably going too deep on something that can be noted as "would do next" in your strategy doc. Judgment about what to defer is itself part of the signal.

---

## Rubric

| Dimension | Weight |
|---|---|
| Decision-making and prioritisation (strategy doc, what was deferred and why) | 20% |
| Bug discovery quality (depth, repro, severity reasoning) | 20% |
| Test architecture (pyramid balance, contracts, fixtures, isolation) | 20% |
| Test insights dashboard (product judgment, scope decisions, would an engineer use it?) | 15% |
| CI/CD quality gates (meaningful gates, not theater) | 10% |
| Logging gap-fill (where, why, what changed) | 5% |
| AI orchestration and judgment (Decision Journal + live session) | 10% |

### How this submission addresses each rubric dimension

| Dimension | Where to look | One-line summary |
| --- | --- | --- |
| Decision-making (20%) | `TEST_STRATEGY.md` | Risk-based prioritisation, layer ownership, Deferrals section, extensibility argument with `qe_toolkit/`. |
| Bug discovery (20%) | `BUG_REPORT.md` + `evidence/` | 14 issues with severity, **Actual vs Expected**, evidence, root cause, fix; top three (B4 / B1 / B3) have full curl + pytest transcripts. |
| Test architecture (20%) | `qe_toolkit/`, `automation-framework/apps/order_processing/`, `app/backend/tests/`, `app/frontend/src/components/Pagination.test.tsx` | Pyramid: Vitest unit + 14 backend pytest + 8 Playwright/API/LLM. Reusable core lives in `qe_toolkit/`; new customer onboarding is a ~30-line conftest (`docs/ONBOARDING_NEW_CUSTOMER.md`). |
| Dashboard (15%) | `automation-framework/dashboard/` ([overview screenshot](docs/screenshots/dashboard-overview-with-failures.png), [AI analysis screenshot](docs/screenshots/dashboard-ai-analysis.png)) | Single-page HTML + SQLite history. Answers the three Monday questions: what is failing, what is newly failing, what is flaky. Vendor-neutral JUnit + Playwright JSON ingest. |
| CI/CD (10%) | `.github/workflows/ci.yml`, `scripts/check_coverage_vs_baseline.py`, `scripts/flag_flakes_from_junit.py` | 4 jobs. Real gates: `--cov-fail-under=48` + `coverage_baseline.txt` regression check + `--reruns 2` flake harness emitted as `::warning::` annotations + `insights-snapshot` ingest job. |
| Logging gap-fill (5%) | `BUG_REPORT.md` § L1, L2 + `app/backend/app/middleware/logging.py` | `csv_upload_started` / `csv_upload_completed` events, plus authenticated `user_id` bound on `request.state` for every request log. |
| AI orchestration (10%) | `AI_DECISION_JOURNAL.md` | Three overrides (discovery vs silent fixes, dashboard storage layer, extracting `qe_toolkit/`), three places AI was wrong, four non-delegations. |

Walkthrough recording script: `docs/VIDEO_WALKTHROUGH_NARRATION.md`.

---

## Automated testing & insights dashboard (submission addendum)

Deliverables for reviewers:

- `TEST_STRATEGY.md` — strategy, prioritisation, extensibility argument
- `BUG_REPORT.md` — every bug with severity, repro, evidence, root cause, fix
- `evidence/` — concrete reproduction transcripts (curl, pytest output, source diffs) for the highest-severity bugs
- `qe_toolkit/` — shared QE framework (pytest fixtures, JUnit/Playwright parsers, coverage gate) reused by the backend conftest, CI scripts, and dashboard
- `automation-framework/dashboard/` — FastAPI test-insights UI (ingest + SQLite history)
- `docs/ONBOARDING_NEW_CUSTOMER.md` — step-by-step recipe for pointing this framework at a different customer solution
- `AI_DECISION_JOURNAL.md` — prompts, mistakes, non-delegations, three override examples
- `docs/DEFINITION_OF_DONE.md` — one-paragraph shipping bar for the system

| Step | Command |
|------|---------|
| Run the product | `docker compose -f infra/docker-compose.yml up --build` — app http://localhost:3000, API http://localhost:8000/docs |
| Backend integration tests | Export `PYTEST_DATABASE_URL` (see `.github/workflows/ci.yml` for the CI shape), then `cd app/backend && pip install -r requirements.txt && python -m pytest tests/ --junitxml=../../test-results/junit-backend.xml --cov=app --cov-report=xml:../../test-results/coverage.xml` |
| Frontend unit tests | `cd app/frontend && npm ci && npm test` |
| Playwright + automation | With the stack up: `cd automation-framework && pip install -r requirements.txt && playwright install chromium && python3 -m pytest -m "not demo_intentional_fail"` — defaults **`AUTOMATION_APP=order_processing`** (legacy **`E2E_CUSTOMER`** / **`INTEGRATION_APP`**); **`AUTOMATION_API_BASE_URL`** overrides API smoke targets; **`RUN_LLM_EVAL=1`** + **`requirements-llm.txt`** enables **`llm_eval`** tests; layer subsets **`python3 -m pytest -m ui`** / **`-m api`** / **`-m functional`** / **`-m llm_eval`**. CI excludes the intentional red marker; full **`python3 -m pytest`** includes it. Use **`python3 -m pytest`** if bare **`pytest`** is not on **`PATH`**. |
| Test insights UI | After artifacts exist under `test-results/`, run `docker compose -f infra/docker-compose.yml up dashboard` and open http://localhost:4000 |
| Ingest | `curl -X POST http://localhost:4000/api/ingest` (no-op if artifacts unchanged; use `?force_duplicate=true` to append a duplicate run for demos) |
| Full scripted run | `./scripts/run-full-suite.sh` (Docker: testcontainers for pytest if `PYTEST_DATABASE_URL` unset; stack up for Playwright; Chromium install via script) |

Step-by-step stack up/down and pre/post checks: `docs/EXECUTION_RUNBOOK.md`.

Continuous integration (`.github/workflows/ci.yml`):

- Postgres service container, backend pytest with `--cov-fail-under=48` plus `coverage_baseline.txt` regression check
- Lightweight flake harness via `pytest-rerunfailures`, surfaced as GitHub Actions `::warning::` annotations by `scripts/flag_flakes_from_junit.py`
- Vitest and integration tests (**`automation-framework/`**: pytest-playwright + API + optional LLM; runs against `docker compose`, excludes the intentional red marker via `-m`)
- All test artifacts uploaded; an `insights-snapshot` job ingests them into a `dashboard.sqlite` and uploads it for download


## Structure

- `app/backend/` — FastAPI service, SQLAlchemy models, Alembic migrations, backend tests
- `app/frontend/` — React/Vite UI with Vitest unit tests
- `automation-framework/` — reusable automation framework (UI/API/LLM layers) plus customer app bundles
- `qe_toolkit/` — shared parsing and quality-gate utilities reused by CI, scripts, and dashboard
- `infra/` — local stack orchestration (`docker-compose.yml`)
- `test-results/` — generated artifacts (JUnit XML, Playwright JSON/media, coverage, dashboard SQLite snapshot)

## Design docs

- `TEST_STRATEGY.md` — risk-based strategy, layer ownership, and extensibility model
- `docs/ONBOARDING_NEW_CUSTOMER.md` — playbook to point the framework at a different customer solution
- `docs/EXECUTION_RUNBOOK.md` — operational run sequence (bring-up, verify, execute, teardown)
- `docs/DEFINITION_OF_DONE.md` — release quality bar

## AI analysis for dashboard

- `AI_DECISION_JOURNAL.md` captures prompt strategy, mistakes corrected, and key override decisions for the dashboard scope and implementation.
- `automation-framework/dashboard/README.md` explains architecture, ingestion model, and scoping choices for the test-insights UI.

## Functional cases mapped to automation

- Authentication / session: `automation-framework/apps/order_processing/tests/ui/test_login.py` and `automation-framework/apps/order_processing/tests/api/test_auth_session.py`
- Orders happy-path UI / API coverage: `automation-framework/apps/order_processing/tests/ui/test_orders_smoke.py` and `automation-framework/apps/order_processing/tests/api/test_orders_api.py`
- Cross-layer stack health: `automation-framework/tests/functional/test_stack_health_functional.py`
- LLM eval smoke (gated by `RUN_LLM_EVAL=1`): `automation-framework/apps/order_processing/tests/llm/test_summary_eval.py`
- Backend service contracts + encoded defects: `app/backend/tests/test_health_and_auth.py`, `app/backend/tests/test_known_defects.py` (5 `xfail(strict=True)`)
- Frontend regression guard: `app/frontend/src/components/Pagination.test.tsx` (1 `it.fails`)
- Dashboard triage anchor (deliberate red test, excluded from CI): `automation-framework/apps/order_processing/tests/ui/test_demo_intentional_fail.py`