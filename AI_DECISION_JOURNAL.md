# AI decision journal

This journal documents how AI assistance was used throughout the Lead SDET assignment, where human judgment overrode tooling suggestions, and what was deliberately kept out of the model's hands.

---

## Consequential prompts and decisions

1. **"Map the intentional defects and align tests to encoded correct behaviour with `xfail`."**
   The codebase already annotated several bugs (`# BUG B1` … `# BUG B6`). I used those annotations as a worklist to author API-level contract tests in `tests/test_known_defects.py` that describe the **desired** contract, and wrapped them in `pytest.mark.xfail(strict=True)`. The strictness matters: when a future developer correctly fixes the bug, the test transitions to `XPASS` and **fails the build**, forcing the author to remove the marker and acknowledge the regression guard is now armed. The first iteration used `strict=False` (silent on fix); a self-review caught the gap before submission.

2. **"Design CI for an environment that may not have Docker on a laptop but must have Postgres on GitHub Actions."**
   Several agent suggestions assumed a Docker daemon was always available. I rejected "tests only run in Docker Compose" as a single path because sandbox runners frequently lack a daemon. The compromise is `PYTEST_DATABASE_URL` for CI (a `services: postgres:15` container) plus opt-in testcontainers when Docker is available locally. A `pytest_sessionfinish` hook also flips the exit code to 1 in CI if zero tests reach the *call* phase, so a misconfigured DB cannot produce a "green by skip" CI run.

3. **"Keep the insights dashboard vendor-neutral and file-based — but actually answer the brief's three questions."**
   The first dashboard pass parsed JUnit and Playwright JSON for the *current* artifact set only. That answers question 1 of the brief ("what is failing right now?") but not 2 or 3 (newly-failing vs flaky, and trends). Self-review forced a redesign: a SQLite run history (`runs` and `outcomes` tables), a content-hashed ingest endpoint, and analytics queries (newly-failing diff vs previous run, mixed pass/fail across the last *N* runs). Failure cards now also embed the Playwright `<video>` and `<img>` attachments inline via the `/artifacts/` mount — directly addressing the brief's "watch the step video without leaving the dashboard" requirement.

4. **"Split Playwright CI from the deliberate red demo."**
   The brief requires a deliberately failing E2E for the Monday triage story but CI must stay mergeable. I tagged the intentional assertion in the test title (`@demo-intentional-fail`) and excluded it via `--grep-invert` in `npm run test`, leaving `npm run test:all` for the full demo. The dashboard's history table makes this triage demo concrete: the failing test shows up as "newly failing" once the demo run is ingested.

5. **"Use Vitest `it.fails` for a UI defect without blocking green unit CI."**
   The pagination component bug (F3, `Math.floor` instead of `Math.ceil`) is encoded as `it.fails(...)` in `Pagination.test.tsx`. The semantics are equivalent to `xfail strict=True` on the Python side: when the bug is fixed, the assertion passes, `it.fails` reports it as failing, and the build breaks, prompting removal of the marker.

6. **"Make 'flake detection + flag' a real signal, not a checkbox."**
   `pytest-rerunfailures` is wired into the backend job (`--reruns 2`). On its own that's just a retry. To make the *flag* visible, a follow-up step (`scripts/flag_flakes_from_junit.py`) parses the JUnit XML, finds tests whose final status was `passed` but had at least one `<rerun>` child, and emits a GitHub Actions `::warning::` annotation per flaky test plus a summary `::notice::`. The same data also feeds the dashboard's "flaky tests" panel via the rerun count column on the `outcomes` table.

7. **"Pick a coverage gate that won't let entropy creep in."**
   Two complementary gates: `pytest --cov-fail-under=48` is a hard floor inside the test command, and `scripts/check_coverage_vs_baseline.py` re-checks the produced `coverage.xml` against the committed `coverage_baseline.txt` before passing. Raising the baseline is an explicit, reviewable diff; lowering it is the only way to ship code without tests, and that diff stands out in code review.

---

## Where AI was wrong or misleading

- **Initial pytest layout imported `app` at collection time**, which froze `DATABASE_URL` before testcontainers had started. Every test errored. The fix was to defer all `app.*` imports until session-scoped fixtures had set the environment variables, then return the ASGI app lazily — a non-obvious pattern when fitting pytest into a stack that reads env at module import.

- **Playwright JSON reporter schema assumptions:** an early generation hallucinated a top-level `stats` object. The real shape is nested (`suites → specs → tests → results`) with attachments living on the `result` object. I validated against a real Playwright report (and Playwright's docs) before wiring the dashboard ingestion.

- **`xfail strict=False` was the agent's default suggestion** for "documenting known defects". That's actively the wrong default: a successful fix would silently flip to `XPASS` and the developer would never know to remove the marker. Forcing `strict=True` is the only way to make the encoded-contract pattern a real regression guard.

- **The first dashboard rendered only the current artifacts.** It looked complete in isolation but failed the brief on questions 2 and 3 (newly-failing vs flaky, trends). The lesson: when an AI says "the dashboard is done", measure it against the brief's questions one by one.

---

## What was deliberately *not* delegated to AI

- **Severity and compliance framing** for the bug report. The unauthenticated `/orders/stats` endpoint is the easiest example: AI will happily file it as P1 because the technical fix is trivial, but the *business* impact (any visitor can scrape order velocity and revenue) makes it P0. Severity is a product/security judgment, not a code judgment.

- **Choosing the coverage baseline number.** The agent suggested 80% as a generic floor; that would have failed CI on day one because the suite is intentionally narrow (the brief explicitly says depth beats count). I committed a 48% floor that matches what the suite actually measures, so the gate is real (a regression below 48% fails the build) without being theatre.

- **Picking which bugs to fix versus document.** Every defect annotated in the source is a *deliberate* defect for the assignment to find. Silently fixing them would erase the evidence chain. The decision to fix only the logging gaps (which the brief asks for explicitly) and document the rest with `xfail` tests is a scoping call I made and recorded in the commit history.

- **The dashboard product surface.** AI tried to suggest charts (Chart.js, Plotly) and a multi-page React UI. I kept the dashboard as a single static-HTML render with a SQLite-backed `/api/summary` JSON endpoint because the brief explicitly says the *judgment to scope down* is the signal. A single page that nails the three questions in the brief beats a sprawling app that does each one badly.

---

## Override examples

**Override 1 — bug fixes vs bug discovery.** An early suggestion was to *fix* the pagination off-by-one (B1) and the `Math.floor` pagination total (F3) inline while building tests, "so CI is greener." I overrode that because the assignment explicitly scores bug discovery and tests that catch incorrect fixes. Silently fixing the defects would undermine the evidence chain in the PR. The compromise is `xfail(strict=True)` and `it.fails(...)` — the tests stay visible, fail the build the moment a *real* fix lands without removing the marker, and prove the automation has teeth.

**Override 2 — dashboard storage layer.** The agent's first instinct was to keep the dashboard stateless, parsing artifacts on every request. That looked clean but couldn't answer "is this newly failing?" — a question that requires comparing the current run against the previous one. I overrode that with a SQLite layer (sub-100 lines of schema and queries) because the brief is explicit that the dashboard must answer history-aware questions. The trade-off — a writable Docker volume for the SQLite file — is small relative to actually nailing two more of the three brief questions.

**Override 3 — extracting `qe_toolkit/` rather than leaving the framework implicit.** The earlier version of this submission had the right *story* in the strategy doc ("here's how a new customer would onboard") but the *code* still hardcoded `from app.main import app` in the conftest, hardcoded `app/backend` paths in CI, and bundled a JUnit parser inside the dashboard. The agent's default was "the strategy doc explains it, that's enough." I overrode that on a self-review because the brief's "next engineer points it at a different customer tomorrow" is a code-level claim, not a documentation claim. The result is `qe_toolkit/` at the repo root: the four reusable modules (`pytest_fixtures`, `junit`, `playwright`, `coverage_gate`) are now imported by the backend conftest, both CI scripts, and the dashboard. Onboarding a second customer is a ~30-line conftest plus a CI job copy — documented concretely in `docs/ONBOARDING_NEW_CUSTOMER.md`. The dashboard is now multi-project (`?project=` filter, `DASHBOARD_PROJECT` env), which signals the multi-tenant intent even while there's only one customer in the demo.

---

## Note on model selection

For this run I asked which Claude model was best up front. The answer that landed was: **Sonnet for codegen and tool-use loops** (most of this work — multi-file edits, Playwright config, CI YAML, dashboard rewrite), and **Opus for the strategy/bug narrative writeups** when reasoning depth moves the rubric (`TEST_STRATEGY.md`, `BUG_REPORT.md`, this journal). The split was advisory rather than enforced — this submission was produced as a single agent pass — but it remains the right routing in principle: pay Opus prices where reasoning depth changes the artifact, and Sonnet prices where throughput matters.
