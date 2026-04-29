# Video walkthrough — full narration (read-aloud script)

**Target length:** about fifteen to twenty minutes at a natural speaking pace. **How to use this file:** read the **Narration** blocks aloud; use **On screen** as stage directions. Pause between major sections. Personalise bracketed placeholders like `[your name]` and `[your fork URL]`.

---

## Section A — Opening

**Narration.**

Hi, I am `[your name]`, and this is my async walkthrough for the Lead SDET assignment on the Order Processing application: a React frontend, a FastAPI backend, and Postgres. In the next few minutes I will walk through four things in order: what I found in the product and how I documented it; how I chose what to test and at which layer; how continuous integration runs that pyramid and enforces quality gates; and finally how I would use the test insights dashboard on a Monday morning to triage failures.

The repo is organised so a reviewer can go straight to the artefacts: `TEST_STRATEGY.md` is the strategy; `BUG_REPORT.md` plus the `evidence/` folder is the bug narrative with concrete transcripts; `qe_toolkit/` is the shared framework; `.github/workflows/ci.yml` is the pipeline; and `dashboard/` is the insights UI. I will reference those paths as I go.

**On screen.** Optional: show your fork on GitHub and the `main` branch, or your IDE with the repo root open.

---

## Section B — Bug report (complete explanation)

**Narration.**

I will start with the bug report because the assignment treats discovery and characterisation as first-class. Issues are not a bullet list for volume; each entry has severity, how to reproduce it, evidence, suspected root cause, and a recommended fix. I group them by layer—backend, frontend, and logging—using a simple severity scale: P0 for production blockers or clear security exposure, P1 for major functional or data-integrity problems, P2 for incorrect UX or reliability, and P3 for polish or accessibility.

The highest-severity items also have longer reproduction write-ups under `evidence/`. For example, `evidence/B4_stats_unauthenticated.md` walks through unauthenticated access to statistics; `evidence/B1_pagination_overlap.md` shows overlapping page results; and `evidence/B3_decimal_drift.md` discusses floating-point arithmetic versus decimal expectations for money. Those files exist so a reviewer can see curl output, jq comparisons, or pytest snippets without relying only on prose in the main report.

The single most serious backend issue I call out is **B4**, rated P0. The aggregate statistics endpoint `GET /orders/stats` returns HTTP 200 even when the caller sends no `Authorization` header. That means anyone who can reach the API can read portfolio-level aggregates—counts and revenue-style rollups—without proving identity. The root cause is straightforward: the handler does not include the same authentication dependency used on other sensitive routes. The fix is to require `Depends(get_current_user)` and, if the product treats stats as role-gated, to enforce an explicit policy. In a risk-based test plan, this class of bug ranks first because it is an authorisation gap with a wide blast radius.

Next I prioritise **data integrity** issues. **B3** is the currency and totals problem: the implementation sums line items using binary floating-point. For money, that is a well-known foot-gun: combinations like `0.1` times three do not always behave the way decimal-minded users expect, and precision can be lost in subtle ways. The bug report ties this to the actual code path in order creation and CSV handling. The recommended direction is `Decimal` end-to-end, storage as `Numeric`, and an explicit rounding policy. I document drift in `evidence/B3_decimal_drift.md` so the discussion is grounded in observable behaviour, not only in theory.

**B1** is another P1 list-correctness bug: pagination uses an off-by-one offset. Concretely, consecutive pages can overlap—some order IDs appear on both page one and page two—while other rows never show up when you walk the full list. The evidence points at the offset expression in `list_orders`. The fix is the standard `offset = (page - 1) * page_size` without the extra minus one. This matters because paging bugs are silent: users assume the grid is complete, but the data model is wrong.

I also document **B2**, duplicate CSV imports on repeated upload of the same `external_id`; **B7**, where delete returns 204 but the row remains visible with a `failed` status, which is a contract mismatch unless soft-delete is explicitly documented; **B5** naive datetime handling in filters; **B6** N+1 query patterns on list; and several frontend issues such as **F1** stale list data when filters change but `useEffect` only depends on `page`, **F3** wrong total page count from `Math.floor` instead of `Math.ceil`, and smaller reliability and accessibility gaps.

On the logging side, the report notes gaps I closed in this submission: structured events around CSV upload, and binding `request.state.user_id` after JWT validation so request logs correlate to a real principal. Those are **L1** and **L2** in the report.

Finally, I connect bugs to tests. In `app/backend/tests/test_known_defects.py`, I encode the *correct* behaviour for several of these defects and mark the tests as expected failures until the product is fixed. Almost all use `pytest.mark.xfail(..., strict=True)`. That is deliberate: if someone fixes the bug and the test starts passing, pytest reports an **XPASS** and fails the build, which forces the team to remove the `xfail` marker and treat the test as a normal regression guard. The one exception I document in code is **B3**: I use `strict=False` there because Postgres `Numeric` quantisation can mask some float issues at the API boundary, and I do not want a brittle XPASS that fails CI for the wrong reason. The test file’s comment explains that trade-off.

**On screen.** Scroll `BUG_REPORT.md`; open one or two `evidence/` files; show `test_known_defects.py` and the `xfail` lines.

**Optional live demo.** If Docker is running, you can run `curl -sS -o /dev/null -w "%{http_code}\n" http://localhost:8000/orders/stats` and narrate that `200` without a token illustrates B4.

---

## Section C — Test strategy (complete explanation)

**Narration.**

The strategy document is deliberately short—about two pages—but it answers what reviewers asked for: what I test, at what layer, what I explicitly defer, and how I prioritise risk.

**Scope.** I treat this stack as a reference implementation while building automation that could be repointed at another customer solution. In scope are authentication and authorisation boundaries, order lifecycle including list filters, detail, update, the delete contract, CSV bulk ingest, aggregate statistics, pagination, and observability hooks. Out of scope for this time-box are full visual regression, load and performance testing, penetration testing, mobile browsers beyond Chromium, and third-party SaaS reporting—the dashboard is self-hosted and reads standard artefacts.

**Risk-based prioritisation** mirrors the bug report. First, money-adjacent behaviour and duplicate ingest: wrong totals and non-idempotent CSV inflate trust in bad numbers. Second, authorisation gaps such as unauthenticated stats. Third, pagination correctness, because silent duplication or missing rows breaks list views. Fourth, fast regression feedback: happy-path API tests with real Postgres guard refactors without always booting the UI. Fifth, UI stability through a small Playwright slice. I also keep a **deliberately failing** Playwright spec tagged for dashboard demos; it is excluded from CI so the pipeline stays green while the demo still shows a realistic red test.

**Test pyramid.** At the bottom, **unit tests** use Vitest and Testing Library—for example the pagination component, where `it.fails` documents the `Math.floor` versus `Math.ceil` bug without pretending the product is already fixed. The **service layer** is **pytest** against the real ASGI app with **httpx**, backed by Postgres—either a URL supplied in CI or testcontainers locally. That layer proves contracts, RBAC, CSV behaviour, and the known-defect assertions. **End-to-end**, **Playwright** on Chromium covers login and orders smoke paths, and records traces, screenshots, and video on failure so triage is cheap.

**Extensibility** is not only prose. I extracted **`qe_toolkit`** at the repository root: shared pytest fixtures and an “honest CI” hook, JUnit XML parsing and flake detection helpers, Playwright JSON parsing, and the coverage baseline gate. The backend `conftest`, the CI scripts under `scripts/`, and the dashboard all import from that package. `docs/ONBOARDING_NEW_CUSTOMER.md` is the recipe for wiring a different FastAPI service the same way—session database URL, Alembic migrations, NullPool patch for async tests, and the same artefact layout so the dashboard does not care which customer produced the XML.

**Deferrals** are explicit judgment: I am not running axe on every PR yet; I am not matrixing every browser; I am not building a load harness in this slice. The strategy points to `docs/DEFINITION_OF_DONE.md` for the one-paragraph shipping bar.

**On screen.** Scroll `TEST_STRATEGY.md`; optionally show the pyramid table and the `qe_toolkit` import snippet; optionally open `Pagination.test.tsx` for `it.fails`.

---

## Section D — CI pipeline (complete explanation)

**Narration.**

Continuous integration lives in `.github/workflows/ci.yml`. It runs on pushes and pull requests to `main` or `master`. There are four jobs: backend tests, frontend unit tests, Playwright end-to-end tests, and a final **insights snapshot** that proves the dashboard ingestion path.

The **backend** job starts a **Postgres 15 service container** on the runner, exports `PYTEST_DATABASE_URL` pointing at that database, installs Python dependencies from `app/backend/requirements.txt`, and runs pytest from `app/backend`. The command is intentionally rich: it writes **JUnit XML** to `test-results/junit-backend.xml`, produces **coverage** as `test-results/coverage.xml`, enforces a **minimum line coverage** with `--cov-fail-under=48`, and adds **`--reruns 2`** with a short delay as a lightweight flake harness—if a test fails once and passes on retry, that pattern becomes visible in the XML.

After pytest, a dedicated step runs **`scripts/check_coverage_vs_baseline.py`**, comparing the generated coverage file to **`app/backend/coverage_baseline.txt`**. That is a regression gate: you cannot silently lower coverage below an agreed baseline without updating the baseline file deliberately. Another step, **`scripts/flag_flakes_from_junit.py`**, scans the JUnit output and emits **GitHub Actions warning annotations** for tests that only passed after a rerun, so flakes surface in the Actions UI even when the job is green.

The **frontend-unit** job checks out the repo, sets up Node 20 with npm cache, runs **`npm ci`** and **`npm test`** under `app/frontend`, which executes Vitest.

The **e2e** job brings up the full stack with **`docker compose -f infra/docker-compose.yml up -d --build`**, then polls until the API health endpoint and the frontend root URL respond. It installs Playwright in the `e2e` package with **`npm ci`** and **`npx playwright install --with-deps chromium`**. The tests run with **`npm run test`**, which translates to Playwright with **`--grep-invert @demo-intentional-fail`**. So the **intentional red** demo spec is excluded from CI; the pipeline stays mergeable while the spec still exists for demos and local runs. Reports and media go under **`test-results/`**—JSON, HTML, traces, screenshots, video—and upload as the **playwright-artifacts** artifact.

The **insights-snapshot** job depends on backend and e2e and uses **`if: always()`** so it still runs when an upstream job fails, which is useful for debugging. It downloads the backend and Playwright artifacts into `test-results`, installs dashboard requirements, and runs a small Python one-liner that imports `dashboard.main` and calls **`ingest_current_artifacts()`**, writing **`dashboard.sqlite`**. That file uploads as **dashboard-snapshot**, demonstrating that the same ingestion logic used locally can run headlessly in CI.

For reviewers who want to reproduce locally, the **README** table lists the exact commands: compose for the product, pytest with the same env shape as CI, Vitest, Playwright, dashboard on port 4000, and optional **`./scripts/run-full-suite.sh`**.

**On screen.** Walk through `ci.yml` in the editor; show `e2e/package.json` scripts; optionally show a green Actions run and the uploaded artifacts list.

---

## Section E — Dashboard: Monday-morning triage (complete explanation)

**Narration.**

Part two of the assignment is a test insights dashboard. Mine is a small FastAPI app that **ingests vendor-neutral inputs**: JUnit XML and Playwright’s JSON report, plus the media paths Playwright writes. It stores **run history in SQLite** so the UI can answer three questions the brief cares about: what is failing right now; whether failures are **new** compared to the previous ingested run or look **chronically flaky** over a window; and how pass rates **trend** over the last several runs.

Imagine **Monday morning**. Overnight CI is green on the main branch, but you still want to rehearse triage—or you have a branch where one end-to-end test is red. You need to see the failure, decide if it is new, and avoid opening five different folders on disk.

First, produce artefacts. For this video I am including the **intentional failing** Playwright test, so I run **`npm run test:all`** in `e2e`, not the CI-only **`npm run test`**. That writes a red result into `test-results` along with attachments. I also run backend pytest with JUnit and coverage output into the same `test-results` tree so the dashboard shows both layers—or I use **`./scripts/run-full-suite.sh`** if my environment already has a database URL and browsers installed.

Then I start the dashboard service with Docker Compose—for example **`docker compose -f infra/docker-compose.yml up dashboard`**—and open **http://localhost:4000**. On startup the app ingests what is on disk. If I rerun tests and need a refresh without restarting the container, I **`POST /api/ingest`**.

On the page I narrate what I see. The **summary** tells me whether pytest and Playwright are green or red for the latest ingest. The **failure cards** list the specific tests; for Playwright I can often **play the video** or see the **screenshot** inline, which is the point of Monday triage: fewer clicks to understand “what broke.” The **newly failing** panel compares the latest run to the previous one so I can tell if this is a fresh regression. The **flaky** table looks at mixed outcomes over a configurable window—conceptually aligned with our CI rerun warnings. The **trend** strip gives a quick visual history of pass rate per run. If I onboard another customer, the same dashboard supports a **`project`** dimension so trends do not collide.

If my SQLite history is noisy from older experiments, I can **`DELETE /api/runs`** and ingest twice: first a baseline run, then a failing run, to make the “newly failing” story obvious on camera.

I will close by tying back to **extensibility**: the dashboard does not know about Order Processing specifically; it knows about **JUnit and Playwright artefacts**. The parsers live in **`qe_toolkit`**, so the next engineer can point the same machinery at a different repository tomorrow.

**On screen.** Terminal: compose, `npm run test:all`, dashboard up, `curl` ingest. Browser: scroll summary, failures with media, flaky and trend sections.

---

## Section F — Closing

**Narration.**

That completes the walkthrough: **bugs** with evidence and severities; **strategy** aligned to risk and a reusable **`qe_toolkit`**; **CI** with coverage floors, baseline regression, rerun-based flake signal, artefact upload, and a headless **dashboard ingest** job; and the **Monday-morning** story on the insights UI. Thank you for watching; I am happy to go deeper on any of these areas in the live review.

**On screen.** Optional: return to the repo root or the PR page.

---

## Timing guide

| Section              | Approximate duration |
|----------------------|----------------------|
| A — Opening        | 1–2 minutes          |
| B — Bug report       | 5–7 minutes          |
| C — Test strategy    | 3–4 minutes          |
| D — CI pipeline      | 4–5 minutes          |
| E — Dashboard triage | 4–6 minutes          |
| F — Closing          | under 1 minute       |
| **Total**            | **~15–25 minutes**   |

If you run long, shorten Section B by covering only B4, B1, B3, and the xfail story, and summarise the rest as “also documented in `BUG_REPORT.md`.”
