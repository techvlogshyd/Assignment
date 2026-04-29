# Part 2 — Test insights dashboard (implementation)

## What it does

A small FastAPI app (`main.py`) that ingests test artifacts produced by Part 1 and answers, on a single page, the three questions the brief asks:

1. **What is failing right now?** — top-of-page summary cards plus per-failure cards split into pytest and Playwright.
2. **Is it newly failing or chronically flaky?** — a "newly failing" panel (failed in latest run, not in the previous), and a "flaky" table (mixed pass/fail across the last *N* runs, default 10).
3. **Trends over the last N runs?** — a coloured sparkline (one tile per run, green ≥ 95% pass, amber ≥ 70%, red below) plus run-level rows in `/api/runs`.

For Playwright failures, the failure card embeds `<video>` and `<img>` attachments inline (whatever Playwright recorded under `attachments` — videos, screenshots, traces). The viewer never has to leave the dashboard to triage a red E2E.

Vendor-neutral OSS only; no external SaaS reporters.

## Architecture

```
   pytest --junitxml -> test-results/junit-*.xml
   Playwright JSON   -> test-results/playwright-report.json
   Playwright media  -> test-results/playwright-output/...
                        |
                        v
                +---------------------------+
                |  POST /api/ingest         |
                |  (auto-runs on startup)   |
                +-------------+-------------+
                              |
                              v
                  test-results/dashboard.sqlite
                  (runs, outcomes; deduped by content hash)
                              |
                              v
                +---------------------------+
                |  /             HTML page  |
                |  /api/summary  JSON       |
                |  /api/runs     JSON       |
                |  /artifacts/   videos +   |
                |                screenshots|
                +---------------------------+
```

The SQLite database lives on a writable Docker volume (`dashboard_data`) so history persists across container restarts. The artifacts directory is mounted read-only.

## How to run

```bash
# Produce artifacts via the test suite, then:
docker compose -f infra/docker-compose.yml up dashboard
```

Open http://localhost:4000.

To ingest after new files land under `test-results/`:

```bash
curl -X POST http://localhost:4000/api/ingest
```

Ingest dedupes using **JUnit / Playwright report paths, mtimes, sizes, and file bytes** — so a real re-run that rewrites those files should produce a **new** run. (Older versions keyed only on pass/fail counts and wrongly treated every green re-run as the same run.)

If nothing on disk changed since the last ingest, the API returns `ingested: false`. To record **another run** with the same files (e.g. trend demos), use:

```bash
curl -X POST 'http://localhost:4000/api/ingest?force_duplicate=true'
```

To wipe history and start over:

```bash
curl -X DELETE http://localhost:4000/api/runs
```

## Configuration

| Env var | Default | Notes |
|---------|---------|-------|
| `ARTIFACTS_ROOT` | `../test-results` (in dev) / `/data/test-results` (in compose) | Where to scan for `junit*.xml` and `playwright-report.json` |
| `DASHBOARD_DB` | `<ARTIFACTS_ROOT>/dashboard.sqlite` (dev) / `/data/db/dashboard.sqlite` (compose) | SQLite history file |
| `FLAKE_WINDOW` | `10` | Look-back window for flake detection |
| `TREND_WINDOW` | `20` | Number of runs in the sparkline |

## Scope decisions

- **SQLite, not Postgres.** A single dashboard instance is enough; no migrations, no external service, ships in the same `docker compose` invocation as the rest of the stack.
- **Server-rendered HTML, not a SPA.** The brief is explicit that scoping is the signal. Charts (Chart.js / Plotly) and a multi-page React UI would have looked impressive but added bundling and routing complexity for no rubric value. The sparkline is plain coloured `<span>`s; it works in any browser.
- **Vendor-neutral by construction.** JUnit XML and Playwright JSON are the only inputs. Any test runner that writes JUnit XML can feed the dashboard tomorrow with zero code changes — that's the extensibility argument from `TEST_STRATEGY.md` made concrete.

## CI integration

The `insights-snapshot` job in `.github/workflows/ci.yml` downloads the backend and Playwright artifacts at the end of each run, ingests them into a fresh `dashboard.sqlite`, and uploads the SQLite file as a workflow artifact. That proves the pipeline end-to-end without standing up a long-running dashboard service.
