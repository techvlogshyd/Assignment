# Lead SDET Assignment — Build Instructions for Claude Code

> **What this file is**: A complete, step-by-step specification for Claude Code to scaffold the entire Lead SDET hiring assignment from scratch. Follow every section in order. Do not skip steps. Do not add features not listed. Do not simplify intentional bugs.

---

## 0. Overview of what you are building

You are building a private GitHub repository that will be handed to Lead SDET candidates. It contains:

1. A deliberately buggy "Order Processing" app (React + FastAPI + Redpanda + Postgres).
2. Enough infra to `docker-compose up` the whole thing in one command.
3. Deterministic seed data and a CSV fixture that triggers specific bugs.
4. A `docs/CANDIDATE_README.md` explaining the assignment to the candidate.
5. A private `docs/INTERVIEWER_GUIDE.md` with the full bug catalog and scoring rubric.
6. An empty `dashboard/` directory for the candidate's Part 2 work.
7. An empty `.github/workflows/` stub for the candidate's CI work.

The app is intentionally broken. Every bug listed in this file **must be present** in the shipped code — do not fix them.

---

## 1. Repository layout

Create exactly this directory tree before writing any file content:

```
Assignment/
├── app/
│   ├── frontend/          # React + Vite DataApp
│   ├── backend/           # FastAPI service
│   └── consumer/          # Python Redpanda consumer
├── infra/
│   └── docker-compose.yml # App + Redpanda + Postgres
├── seed/
│   ├── seed.sql           # Deterministic DB seed
│   └── orders_upload.csv  # CSV fixture for upload idempotency bug
├── dashboard/
│   └── README.md          # One-liner: "Part 2 lives here"
├── docs/
│   ├── CANDIDATE_README.md
│   └── INTERVIEWER_GUIDE.md
└── .github/
    └── workflows/
        └── .gitkeep
```

---

## 2. Infra — `infra/docker-compose.yml`

Write a `docker-compose.yml` that starts:

- **Postgres 15** on port `5432`. DB name `orders_db`, user `orders_user`, password `orders_pass`.
- **Redpanda** (latest stable, single-broker, KRaft mode) on ports `9092` (Kafka API) and `9644` (admin). Use the official `redpandadata/redpanda` image. On startup, create topic `orders.created` with 3 partitions and `orders.processed` with 3 partitions.
- **backend** service built from `app/backend/`, env vars: `DATABASE_URL`, `REDPANDA_BOOTSTRAP`, `SECRET_KEY`. Depends on postgres and redpanda. Port `8000`.
- **frontend** service built from `app/frontend/`, env var `VITE_API_URL=http://localhost:8000`. Port `3000`.
- **consumer** service built from `app/consumer/`, env vars: `DATABASE_URL`, `REDPANDA_BOOTSTRAP`. Depends on postgres, redpanda, backend.

Include a `healthcheck` for Postgres. Include a `depends_on: condition: service_healthy` for any service that needs Postgres.

---

## 3. Backend — `app/backend/`

### 3.1 Stack

- Python 3.11, FastAPI, SQLAlchemy (async, asyncpg), Alembic, python-jose (JWT auth), passlib, aiokafka (Redpanda producer), structlog, pytest, httpx, testcontainers.
- `requirements.txt` and a `Dockerfile` (python:3.11-slim base, non-root user).

### 3.2 Database models

Create two SQLAlchemy models:

**`User`**: `id` (UUID PK), `email` (unique), `hashed_password`, `role` (enum: `admin`, `editor`, `viewer`), `created_at`.

**`Order`**: `id` (UUID PK), `external_id` (string, unique — used for idempotency), `customer_name`, `items` (JSONB), `total_amount` (NUMERIC — but the app code uses `float` arithmetic, which is the planted bug), `status` (enum: `pending`, `processing`, `completed`, `failed`), `created_at`, `updated_at`.

### 3.3 Auth

- POST `/auth/register` — creates a user. Passwords hashed with bcrypt.
- POST `/auth/login` — returns a JWT (HS256, 24h expiry). Secret from `SECRET_KEY` env var.
- A `get_current_user` dependency that decodes the JWT and returns the user.

### 3.4 Orders endpoints

All endpoints below require `get_current_user` **except one** — see bug B4.

- `GET /orders` — paginated list. Query params: `page` (default 1), `page_size` (default 20), `status` filter, `customer_name` contains filter.
- `GET /orders/{order_id}` — single order.
- `POST /orders` — create order (admin/editor only).
- `PATCH /orders/{order_id}` — update status (admin/editor only).
- `DELETE /orders/{order_id}` — soft-delete (admin only).
- `POST /orders/upload-csv` — bulk create from CSV.
- `GET /orders/stats` — aggregate stats: total orders, totals by status, sum of `total_amount`.

### 3.5 Planted backend bugs — implement ALL of these exactly

**B1 — Off-by-one in pagination**
In `GET /orders`, the OFFSET calculation must be `(page - 1) * page_size - 1` instead of `(page - 1) * page_size`. This causes one record to be skipped at page boundaries and the last item of page N to appear as the first item of page N+1.

**B2 — Missing idempotency on CSV upload**
`POST /orders/upload-csv` must not check whether an `external_id` already exists before inserting. On any retry or duplicate upload of the same CSV, duplicate orders are created with different UUIDs but the same `external_id`. No unique constraint violation because the model does not have a DB-level unique constraint on `external_id` — only a comment saying "TODO: add unique constraint".

**B3 — Float arithmetic for currency**
The `total_amount` computation in `POST /orders` (summing `price * quantity` from the items array) must use Python `float` arithmetic: `total = sum(item['price'] * item['quantity'] for item in items)`. This produces precision drift (e.g., `0.1 + 0.2 != 0.3`). The fix would be `decimal.Decimal`. Do not fix it.

**B4 — Unprotected endpoint**
`GET /orders/stats` must NOT have the `get_current_user` dependency. Any unauthenticated request must return order statistics. This is the security bug.

**B5 — Naive datetime timezone comparison**
In the date-range filter on `GET /orders`, compare `Order.created_at >= start_date` where `start_date` is parsed with `datetime.fromisoformat(request_param)` — no timezone awareness. When a client sends a UTC ISO string and the DB stores UTC, the comparison silently drops the `+00:00` offset, potentially missing or double-counting records across midnight UTC.

**B6 — N+1 query**
In `GET /orders`, after fetching the paginated list of orders, fetch each order's `items` in a separate query inside a Python loop (not via a join or `selectinload`). With 100 orders this fires 101 queries.

### 3.6 Kafka/Redpanda producer

After a successful `POST /orders`, publish a message to `orders.created` using aiokafka.

Plant this bug:

**B7 — Producer acks=1**
Configure the aiokafka producer with `acks=1`. The correct setting for durability is `acks='all'`. With a single-broker Redpanda setup this is usually fine, but under leader re-election it creates a data-loss window. Add a comment `# TODO: change to acks='all' for production` to make it findable but not obvious in the diff.

### 3.7 Structured logging

Use `structlog` with JSON output. Log request ID, user ID (if authenticated), endpoint, and duration on every request via middleware. Deliberately omit logging in the CSV upload handler and in the Kafka producer — these are the "logging gaps" the candidate must find.

---

## 4. Frontend — `app/frontend/`

### 4.1 Stack

- React 18, Vite, TypeScript, React Query v5, React Router v6, Axios, date-fns, a component library (shadcn/ui or Radix + Tailwind — use Tailwind).
- `Dockerfile` (node:20-alpine, multi-stage: build then nginx:alpine to serve dist).

### 4.2 Pages and components

- `/login` — login form, posts to `/auth/login`, stores JWT in `localStorage`.
- `/` (dashboard) — summary cards (total orders, orders by status), a recent-orders table with pagination, and a status filter.
- `/orders` — full paginated orders table with filters (status, customer name, date range).
- `/orders/:id` — order detail view.
- `/upload` — CSV upload form (file input + submit button, shows success/error).

### 4.3 Planted frontend bugs — implement ALL of these exactly

**F1 — Stale closure in `useEffect`**
In the orders list component, write a `useEffect` that captures `filters` in its closure but does not include `filters` in its dependency array. This means when the user changes a filter, the effect re-runs with the stale filter value for one render cycle, briefly showing results for the previous filter.

```tsx
// Plant this pattern exactly:
useEffect(() => {
  fetchOrders(filters); // filters is stale — not in dep array
}, [page]); // BUG: filters missing from deps
```

**F2 — Request race condition**
In the orders fetch, use two competing `useEffect` hooks (or a manual fetch pattern) without an AbortController or cancellation. When the user changes filters rapidly, a slow response from an earlier request can overwrite the result of a newer one. Do not use React Query's built-in cancellation — write a manual `fetch` or axios call inside `useEffect` for this component specifically so the bug exists.

**F3 — Off-by-one in client-side pagination**
In the pagination component, compute total pages as `Math.floor(totalItems / pageSize)` instead of `Math.ceil(totalItems / pageSize)`. When `totalItems` is exactly divisible by `pageSize`, the last page is never shown.

**F4 — setInterval not cleaned up**
In the dashboard summary component, poll for updated stats every 10 seconds using `setInterval`. Do NOT return a cleanup function from the `useEffect`. This creates a memory leak and stacks intervals on every re-render.

```tsx
// Plant this pattern exactly:
useEffect(() => {
  const id = setInterval(fetchStats, 10_000);
  // BUG: no return () => clearInterval(id);
}, []);
```

**F5 — RBAC enforced in UI only**
For the "Delete Order" button, check the user role from the JWT payload stored in `localStorage` and hide the button for `viewer` role. Make no check on the API call itself — if a `viewer` manually calls `DELETE /orders/:id` via curl, it succeeds (also note: the backend does implement the RBAC check, so this bug is specifically that the UI does not provide any visual or error feedback when a viewer attempts the action via the API directly — the UI just hides the button but a savvy user can still trigger the route).

Actually, to make this more interesting: the backend `DELETE /orders/{order_id}` endpoint checks for `admin` role and returns 403 for non-admins. The frontend bug is that the UI hides the button for both `viewer` and `editor`, but `editor` should be able to see it (wrong role check in the UI): the UI uses `role !== 'admin'` to hide, but should only hide for `viewer`. This is a UX RBAC mismatch, not a security hole.

**F6 — Timezone display bug**
Render all `created_at` timestamps using `new Date(timestamp).toLocaleString()` without specifying a timezone. This displays the UTC timestamp in the browser's local timezone without any indication of timezone, causing confusion for distributed teams.

**F7 — Accessibility issues**
- The status filter `<select>` must have no `<label>` associated with it (missing `htmlFor`/`id` pairing).
- Status badge components (`<span>` with background color) must have foreground colors that fail WCAG AA contrast ratio (e.g., yellow text `#FFD700` on white `#FFFFFF`, contrast ratio ~1.07:1).
- The CSV upload `<input type="file">` must have no `aria-label` or associated `<label>`.

---

## 5. Consumer — `app/consumer/`

### 5.1 Stack

Python 3.11, aiokafka, asyncpg (or SQLAlchemy async), structlog, asyncio.

### 5.2 Behavior

Consume from `orders.created` topic, process each message (update the order status to `processing`, do some computation, update to `completed` or `failed`), publish result to `orders.processed`.

Use a consumer group `order-processor-group`. Run `N_WORKERS=3` concurrent asyncio tasks that each pull from a shared queue of fetched messages.

### 5.3 Planted consumer/queue bugs — implement ALL of these exactly

**Q1 — Commit before processing**
Commit the Kafka offset **before** processing the message (before updating Postgres). If the consumer crashes during processing, the offset is already committed and the message is lost.

```python
# Plant this pattern exactly:
await consumer.commit()          # BUG: commit before work
await process_order(message)     # if this throws, message is lost
```

**Q2 — No consumer-side idempotency**
`process_order` must not check whether `order.status` is already `completed` before updating. On consumer rebalance (which re-delivers uncommitted messages), the same order gets processed twice. Since Q1 commits before processing, Q2 may seem moot in normal flow — but under a crash-then-restart scenario, a previously committed offset is not re-delivered, while a rebalance mid-processing CAN re-deliver. Make both bugs present; their interaction is the subtlety.

**Q3 — Out-of-order processing across workers**
The 3 concurrent workers pull messages off a shared `asyncio.Queue` without any partition-key affinity. Two messages for the same `order_id` (e.g., `created` then an immediate `status_update`) can be processed by different workers concurrently. Because there is no locking, the final DB state depends on which worker's UPDATE commits last. Plant this by having the consumer also consume a second message type (`order.status_update`) on the same topic and processing both types in the shared worker pool with no ordering guarantee.

**Q4 — Unbounded prefetch**
Set `max_partition_fetch_bytes` to a very large value (e.g., `52428800` — 50 MB) and `fetch_max_wait_ms=0` so the consumer greedily fetches as many messages as possible. Under burst load (10k messages published rapidly), the consumer's in-memory queue grows without bound, eventually causing OOM.

**Q5 — Producer acks=1** (already planted in backend B7 above — confirm it is wired through to the consumer-facing behavior description in the interviewer guide; no additional code change needed here.)

---

## 6. Seed data — `seed/`

### 6.1 `seed.sql`

Write a SQL file that inserts:
- 3 users: one `admin` (email `admin@example.com`), one `editor` (email `editor@example.com`), one `viewer` (email `viewer@example.com`). Use bcrypt hashes for password `password123` for all three.
- 47 orders across all statuses, with `created_at` values spread across the last 30 days. Use deterministic UUIDs (hardcoded). Include some with `external_id` values that match rows in the CSV (to trigger B2).
- Choose amounts that will produce float precision drift when summed (e.g., `0.1`, `0.2`, `0.7` multiplied by quantities).

### 6.2 `orders_upload.csv`

Create a CSV with columns: `external_id,customer_name,item_name,price,quantity`.

Include 10 rows. 3 of the `external_id` values must match orders already in `seed.sql`. This means a fresh upload after seeding will produce 3 duplicates — the idempotency bug in action.

---

## 7. `dashboard/README.md`

Write exactly:

```markdown
# Part 2 — Test Insights Dashboard

This directory is yours to build in.

Your task is to build a working internal dashboard that an engineer would open on Monday morning to understand the health of the test suite.

**Hard constraints:**
- Real working app (not a static report).
- Ingests results from your Part 1 test runs (Playwright JSON/traces/videos, pytest JUnit/JSON, k6 summary).
- Vendor-neutral OSS only. No SaaS test-reporting services.
- Must come up with a single `docker-compose up` (or one documented command) on a fresh machine.

**Everything else is your call.** Tech stack, schema, which charts and filters to build first, whether to add auth or multi-project support — you decide and defend your decisions in the walkthrough video.

A great dashboard makes it easy to answer:
- What is failing right now, and is it newly failing or chronically flaky?
- How are pass rate, flake rate, and duration trending over the last N runs?
- For an E2E failure, can I watch the step video and see the screenshot without leaving the dashboard?
- How are perf results (latency, throughput, queue lag) trending over time?

We score judgment over breadth. A focused dashboard that nails 2-3 of the above is better than a sprawling one that does many things poorly.
```

---

## 8. `docs/CANDIDATE_README.md`

Write a professional, friendly candidate-facing README. It must cover exactly the following sections (write each in full prose, not just headers):

### 8.1 Context

"You are joining the quality engineering function at RapidCanvas, where engineering teams deploy React DataApps and FastAPI services to production on our platform. Your job is to help teams ship with confidence. This assignment mirrors a real slice of that work."

### 8.2 The system

Brief description of the Order Processing app (React + FastAPI + Redpanda + Postgres). Include the architecture diagram:

```
React DataApp → FastAPI Backend → Redpanda (orders.created) → Python Consumer → Postgres
```

Explain that it has non-trivial issues across all layers and that finding, characterising, and demonstrating those issues is central to Part 1.

### 8.3 Part 1 — Quality engineering (primary deliverable)

List all deliverables clearly:

1. **Test strategy document** (1-2 pages): what you will test and at what layer, what is explicitly out of scope, and a risk-based prioritisation. This is the first thing reviewers read.
2. **Test pyramid**:
   - Unit tests: frontend (Vitest + React Testing Library), backend (pytest).
   - Integration / contract tests: FastAPI + Postgres + Redpanda via testcontainers.
   - E2E: Playwright — at minimum a happy-path suite and one regression per discovered critical bug.
3. **Performance and concurrency harness**: use k6 or Locust for the HTTP layer; write a Python load+chaos script for the consumer (publish burst messages, kill the consumer mid-processing, restart, verify no messages were lost or duplicated). The harness must surface queue race conditions measurably — not just "it looked slow."
4. **Bug discovery report** (markdown): every issue you find, with severity, steps to reproduce, evidence (logs, screenshots, test output), suspected root cause, and recommended fix. We score depth and reasoning, not count.
5. **Logging gap-fill**: identify where structured logging is missing or insufficient and add it. Explain your choices. Don't add a log statement to every line — add logs where they materially improve debuggability.
6. **CI pipeline** (GitHub Actions): runs the pyramid on every PR, fails on coverage regression and perf SLO breach, includes basic flake detection (rerun + flag), publishes test artifacts. Include a one-paragraph written "definition of done" for any feature shipping on this system.

### 8.4 Part 2 — Test insights dashboard

Point to `dashboard/README.md` for full brief. Emphasise:
- This is intentionally open-ended. Your architecture and scoping decisions are the signal.
- Time box it. A working, focused dashboard beats an impressive incomplete one.
- The acceptance demo: run your Part 1 suite (including a deliberately failing E2E and a perf run that breaches SLO), then open your dashboard and walk us through how you would triage on Monday morning.

### 8.5 AI usage

"You are encouraged to use any AI tooling. We evaluate what you effectively built and the judgment you applied — not raw effort or line count.

**Required deliverable: AI Decision Journal** (markdown, ~2 pages):
- The 5-10 most consequential prompts you used and why.
- Where AI was wrong or misleading and how you caught it.
- What you deliberately did not delegate to AI and why.
- One example of an AI suggestion you overrode, with your reasoning."

### 8.6 Getting started

```bash
git clone <your-private-fork>
cd Assignment
docker-compose -f infra/docker-compose.yml up --build
# App: http://localhost:3000
# API: http://localhost:8000/docs
# Seed data is applied automatically on first run
```

Credentials: `admin@example.com / password123`, `editor@example.com / password123`, `viewer@example.com / password123`.

### 8.7 Submission

1. Work in your private fork.
2. Open a PR when done (Day 5 target).
3. Record a 15-20 minute async walkthrough video covering: your bug report, your test strategy, how to run the CI pipeline, and the dashboard Monday-morning triage demo.
4. A 90-minute live review will follow: 60 min deep-dive on your PR, 30 min live AI orchestration task we will give you fresh on the day.

### 8.8 Time expectation

"We expect 15-20 hours self-paced over 3-5 calendar days. If you are significantly over this, you are probably going too deep on something that can be noted as 'would do next' in your strategy doc. Judgment about what to defer is itself part of the signal."

### 8.9 Rubric (publish this openly)

| Dimension | Weight |
|---|---|
| Decision-making and prioritisation (strategy doc, what was deferred and why) | 15% |
| Bug discovery quality (depth, repro, severity reasoning) | 15% |
| Test architecture (pyramid balance, contracts, fixtures, isolation) | 15% |
| Performance and concurrency testing (does it surface the queue races measurably?) | 15% |
| Test insights dashboard (product judgment, scope decisions, would an engineer use it?) | 15% |
| CI/CD quality gates (meaningful gates, not theater) | 10% |
| AI orchestration and judgment (Decision Journal + live session) | 15% |

---

## 9. `docs/INTERVIEWER_GUIDE.md`

Write a comprehensive private guide. Mark the file with a header: `<!-- PRIVATE: DO NOT SHARE WITH CANDIDATES -->`.

### 9.1 Full bug catalog

For every bug (B1–B7, F1–F7, Q1–Q5), write:
- Bug ID and name
- Exact file and line where it lives
- How to reproduce it (steps or test assertion)
- Why a strong candidate will find it vs why a weak candidate misses it
- Suggested remediation (1-3 sentences)
- Severity: Critical / High / Medium / Low with rationale

### 9.2 Scoring guide per rubric dimension

For each of the 7 rubric dimensions, write four descriptors:

- **Below bar**: what this looks like (concrete examples of weak submissions)
- **At bar**: minimum acceptable for a senior IC
- **Above bar**: strong senior / low-end Lead
- **Lead-level**: what distinguishes a Lead SDET from a senior

### 9.3 Live session task bank

Write 5 fresh tasks of 30-minute scope that interviewers can assign during the live session. Each must:
- Be completable in 30 min with AI assistance.
- Test a different dimension (one is a new test, one is a perf assertion, one is a logging/tracing task, one is a bug triage from a production-style log dump, one is a schema/API change with backward compatibility question).
- Include the "what good looks like" answer so interviewers can evaluate in real time.

### 9.4 Calibration notes

- Remind interviewers: score depth not count on the bug report. A candidate who finds 5 bugs with excellent root-cause analysis beats one who lists 15 bugs with "it returned wrong data."
- Dashboard: run the Monday-morning triage demo before scoring. Pretty ≠ useful.
- AI journal: look for honest self-awareness, not AI cheerleading. A candidate who says "AI got the testcontainers config wrong and I caught it because I knew the correct port" is stronger than one who says "AI was great for everything."
- Queue races: a candidate who surfaces Q1 (commit before process) via a kill-mid-process chaos test, not just code inspection, is demonstrating Lead-level thinking.

### 9.5 Go / no-go decision criteria

Write explicit thresholds:
- **Automatic no-go**: no perf/concurrency harness at all; no CI pipeline; test strategy doc missing.
- **Strong pass**: surfaces at least 3 of the 5 queue bugs measurably, dashboard is usable, AI journal shows genuine override of at least one AI suggestion.
- **Lead-level pass**: test strategy doc could be used as a team onboarding artifact; dashboard would be used in production; live session shows fluent AI orchestration with clear "I won't delegate this" moments.

---

## 10. Style and code quality requirements

- All Python code: black-formatted, type-annotated, no `print` statements (use structlog).
- All TypeScript: strict mode, no `any`, ESLint clean.
- All SQL: lowercase keywords, explicit column lists (no `SELECT *`).
- Docker images: non-root users, `.dockerignore` files.
- No secrets hardcoded except in `docker-compose.yml` environment sections (where they are clearly local-dev values).
- Every planted bug must be present in the final code. Run a quick self-check: search for each Bug ID in this file and confirm the corresponding code pattern exists in the output.

---

## 11. Self-verification checklist

Before finishing, verify each item:

- [ ] `docker-compose -f infra/docker-compose.yml up --build` completes without error and all services pass healthchecks.
- [ ] `GET /orders` with page=1, page_size=5 on 10 records returns items 1-5 but item 5 is the same as item 6 on page 2 (B1 present).
- [ ] Uploading `seed/orders_upload.csv` twice creates duplicate orders (B2 present).
- [ ] `GET /orders/stats` returns 200 without a JWT (B4 present).
- [ ] Frontend dashboard polls stats every 10s and does not clean up the interval (F4 present — verify in React DevTools or by watching network tab).
- [ ] Consumer commits offset before processing (Q1 present — visible in consumer source).
- [ ] Consumer group `order-processor-group` has 3 workers sharing a queue with no partition-key affinity (Q3 present).
- [ ] `seed/orders_upload.csv` contains 3 `external_id` values that match rows in `seed.sql`.
- [ ] `docs/INTERVIEWER_GUIDE.md` contains entries for all 17 bugs (B1-B7, F1-F7, Q1-Q5 minus Q5 which references B7).
- [ ] `dashboard/` contains only `README.md` — no scaffold code.
- [ ] `.github/workflows/` contains only `.gitkeep` — no workflow files.
