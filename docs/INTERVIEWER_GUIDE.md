<!-- PRIVATE: DO NOT SHARE WITH CANDIDATES -->

# Interviewer Guide — Lead SDET Assignment

This document contains the full bug catalog, scoring rubric, live session task bank, calibration notes, and go/no-go criteria. Keep it out of the candidate's fork.

---

## 1. Full Bug Catalog

There are 13 intentional bugs: 6 backend (B1–B6) and 7 frontend (F1–F7). Each entry below gives the exact location, reproduction steps, why strong vs weak candidates find it, remediation, and severity.

---

### B1 — Off-by-One in Pagination

**File:** `app/backend/app/routers/orders.py`, line ~65

**The bug:**
```python
offset = (page - 1) * page_size - 1  # BUG B1: should be (page - 1) * page_size
result = await db.execute(
    query.order_by(Order.created_at.desc()).offset(max(offset, 0)).limit(page_size)
)
```
The `-1` causes page 2 to start one record early, so the last item of page 1 re-appears as the first item of page 2.

**Reproduction:**
```bash
# With 47 orders seeded, fetch pages 1 and 2 (page_size=5)
curl -H "Authorization: Bearer $TOKEN" "http://localhost:8000/orders?page=1&page_size=5"
curl -H "Authorization: Bearer $TOKEN" "http://localhost:8000/orders?page=2&page_size=5"
# item[4] of page 1 == item[0] of page 2
```

**Strong candidate finds it by:** Writing a parametric pagination test that asserts no item ID appears on two consecutive pages. Also catches it in the code review: the formula stands out because the comment says "page offset calculation" without explaining the `-1`.

**Weak candidate misses because:** Tests happy path only (page 1) or doesn't verify cross-page uniqueness.

**Remediation:** Change `(page - 1) * page_size - 1` to `(page - 1) * page_size`.

**Severity:** High — causes data integrity issues in any paginated view; users cannot see all records.

---

### B2 — Missing Idempotency on CSV Upload

**File:** `app/backend/app/routers/orders.py`, line ~155; `app/backend/app/models.py`, line ~41

**The bug:**
The `POST /orders/upload-csv` handler inserts every row in the CSV without checking if `external_id` already exists. The `Order.external_id` column has no database-level `UNIQUE` constraint (comment says `# TODO: add unique constraint`).

**Reproduction:**
```bash
# Upload the CSV once
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -F "file=@seed/orders_upload.csv" http://localhost:8000/orders/upload-csv

# Upload again — creates 10 more orders with same external_ids
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -F "file=@seed/orders_upload.csv" http://localhost:8000/orders/upload-csv

# Query confirms duplicates
psql $DB -c "select external_id, count(*) from orders group by external_id having count(*) > 1;"
```

**Strong candidate finds it by:** Uploading the CSV twice and querying the DB. Also spots the missing constraint in `models.py` and `alembic/versions/0001_initial.py`.

**Weak candidate misses because:** Reads the code only and assumes `external_id` is unique because it's described as an idempotency key.

**Remediation:** Add `unique=True` to `external_id` in models.py and add a DB-level unique constraint in a new migration. Handle `IntegrityError` gracefully in the upload handler (upsert or skip-on-conflict).

**Severity:** Critical — financial systems cannot tolerate duplicate orders; every retry creates phantom records.

---

### B3 — Float Arithmetic for Currency

**File:** `app/backend/app/routers/orders.py`, lines ~117, ~163

**The bug:**
```python
# POST /orders
total = sum(item["price"] * item["quantity"] for item in items)  # BUG B3: float not Decimal

# POST /orders/upload-csv
total = price * quantity  # BUG B3: float arithmetic
```

**Reproduction:**
```bash
# Create an order with price=0.1, quantity=3
curl -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  http://localhost:8000/orders \
  -d '{"external_id":"FLOAT-TEST","customer_name":"Test","items":[{"name":"x","price":0.1,"quantity":3}]}'
# total_amount in response: 0.30000000000000004 (not 0.3)
```

Upload `orders_upload.csv` which contains `price=0.1,quantity=3` (EXT-001) and observe the stored `total_amount`.

**Strong candidate finds it by:** Noticing the `sum(float * int)` pattern and writing an assertion like `assert Decimal(str(total)) == Decimal("0.3")`. May also add a test with `price=0.1, quantity=3, expected=0.3` that fails.

**Weak candidate misses because:** Float precision issues are non-obvious without running the specific values. A candidate who only tests with round numbers (e.g., `price=10.0`) will not see the drift.

**Remediation:** Use `from decimal import Decimal` and parse item prices as `Decimal(str(item["price"]))`. Store as `NUMERIC(12,4)` — the column type is already correct, only the Python arithmetic needs fixing.

**Severity:** High — financial calculations with float drift lead to penny discrepancies that compound at scale and are a compliance risk.

---

### B4 — Unprotected Stats Endpoint

**File:** `app/backend/app/routers/orders.py`, line ~26

**The bug:**
```python
@router.get("/stats", response_model=OrderStats)
async def get_order_stats(db: AsyncSession = Depends(get_db)) -> OrderStats:
    # BUG B4: no get_current_user dependency
```

**Reproduction:**
```bash
# No Authorization header — returns 200 with full stats
curl http://localhost:8000/orders/stats
```

**Strong candidate finds it by:** Systematically testing every endpoint without a token. A security-minded tester checks this as a baseline step. Also visible in the code: all other `orders.py` handlers have `current_user: User = Depends(get_current_user)` in their signature; this one does not.

**Weak candidate misses because:** The endpoint returns aggregate data, so it "feels" harmless. Candidate only tests authenticated flows.

**Remediation:** Add `current_user: User = Depends(get_current_user)` to `get_order_stats`. Decide (and document) whether viewer role should have access.

**Severity:** High — aggregate order statistics (revenue totals, order counts by status) are business-sensitive data. An unauthenticated endpoint is a security bug regardless of data sensitivity.

---

### B5 — Naive Datetime Timezone Comparison

**File:** `app/backend/app/routers/orders.py`, lines ~57–62

**The bug:**
```python
if start_date:
    start_dt = datetime.fromisoformat(start_date)  # BUG B5: drops timezone info
    query = query.where(Order.created_at >= start_dt)
if end_date:
    end_dt = datetime.fromisoformat(end_date)      # BUG B5: same issue
    query = query.where(Order.created_at <= end_dt)
```

When a client sends `start_date=2024-01-15T00:00:00+00:00`, `fromisoformat` on Python 3.11 correctly parses the `+00:00`, but if sent as `2024-01-15T00:00:00Z`, it raises `ValueError`. More importantly, comparing a timezone-aware `Order.created_at` (stored in UTC) with a naive datetime silently produces incorrect results depending on the SQLAlchemy/asyncpg driver version — or raises a `TypeError` at runtime.

**Reproduction:**
```bash
# Send a UTC date string with Z suffix
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/orders?start_date=2024-01-15T00:00:00Z"
# Either raises 500 or silently excludes records near midnight UTC
```

**Strong candidate finds it by:** Testing the date filter with both `+00:00` and `Z` suffixes, and checking records near midnight UTC boundaries. Writes a test that seeds a record at `23:59:59 UTC` and verifies it appears when `start_date=<that day>T00:00:00Z`.

**Weak candidate misses because:** Only tests with simple date strings like `2024-01-15` (no time component), which works fine.

**Remediation:**
```python
from datetime import timezone
start_dt = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
if start_dt.tzinfo is None:
    start_dt = start_dt.replace(tzinfo=timezone.utc)
```

**Severity:** Medium — date range filters silently return incorrect results in cross-timezone deployments. Data integrity issue rather than a crash.

---

### B6 — N+1 Query

**File:** `app/backend/app/routers/orders.py`, lines ~74–85

**The bug:**
```python
orders = result.scalars().all()

# BUG B6: N+1 — fetching items in a loop instead of a join or selectinload
order_details = []
for order in orders:
    items_result = await db.execute(
        select(Order.items).where(Order.id == order.id)
    )
    items = items_result.scalar_one()
    order_details.append(...)
```

For a page of 20 orders, this fires 21 queries (1 count + 1 list + 20 individual item fetches).

**Reproduction:**
Enable SQLAlchemy query logging (`echo=True` on the engine) or use a DB proxy like pgBadger. Fetch `GET /orders?page_size=20` and observe 22 queries in the logs.

**Strong candidate finds it by:** Enabling query logging and counting SQL statements. May also write a test that asserts the query count using a mock or a SQLAlchemy event listener. Lead-level candidates recognise this as the canonical "select N+1" pattern and know the fix without needing to run the code.

**Weak candidate misses because:** The code looks "fine" at a glance — it's just a loop fetching data. Without query logging, it's invisible.

**Remediation:** Remove the loop entirely — `Order.items` is already a JSONB column on the same `Order` row. The loop re-fetches what was already loaded:
```python
order_details = [
    OrderResponse(
        id=order.id, items=order.items, ...  # items already on the model
    )
    for order in orders
]
```

**Severity:** Medium — with 100 orders per page this fires 101 queries. At 10 req/s under load, this saturates the DB connection pool quickly. Becomes High at scale.

---

### F1 — Stale Closure in useEffect

**File:** `app/frontend/src/hooks/useOrders.ts`, line ~30

**The bug:**
```tsx
useEffect(() => {
  // filters is captured from the outer scope but is stale
  axios.get(`${baseURL}/orders`, { params: { page, ...filters } })
    .then(...)
    .finally(...);
}, [page]); // BUG F1: filters missing from dependency array
```

When the user changes a filter without changing the page, the effect does not re-run, so results do not update until the page changes.

**Reproduction:**
1. Load the Orders page. Note the results.
2. Type a customer name in the filter input.
3. Results do not change (the effect ignores the new filter value).
4. Click Next page — now the filter applies (because `page` changed and the effect re-runs, capturing the updated `filters`).

**Strong candidate finds it by:** Using React DevTools to inspect the hook's dependency array, or by noticing the discrepancy between filter state and displayed results during manual testing. Writes a Vitest test with RTL that updates filters and asserts the API is called with the new params.

**Weak candidate misses because:** The filter input visually updates (React state changes), so it looks like it's working. The bug is only observable when a filter changes without a page change.

**Remediation:** Add `filters` (or individual filter values) to the dependency array, or switch to React Query with `queryKey: ['orders', page, filters]`.

**Severity:** Medium — users see stale data silently; the filter UI gives false confidence.

---

### F2 — Request Race Condition

**File:** `app/frontend/src/hooks/useOrders.ts`, line ~28

**The bug:**
```tsx
// BUG F2: no AbortController — rapid filter changes cause race condition
axios.get(`${baseURL}/orders`, { params, ... })
  .then((res) => {
    setOrders(res.data.items);  // overwrites state regardless of request order
    ...
  });
```

When the user changes filters rapidly, multiple in-flight requests can resolve out of order. The last request to resolve (not the last request sent) sets the displayed data.

**Reproduction:** Requires network throttling (Chrome DevTools → Slow 3G). Change filters rapidly 3–4 times. Observe the displayed results flickering and potentially settling on stale data.

**Strong candidate finds it by:** Code review (recognises the pattern immediately) and/or writes a test that simulates two concurrent requests resolving out of order and asserts the second response wins.

**Weak candidate misses because:** The bug requires specific timing conditions (slow network + rapid filter changes). Not triggered in fast local dev.

**Remediation:**
```tsx
useEffect(() => {
  const controller = new AbortController();
  axios.get('/orders', { params, signal: controller.signal })
    .then(...)
  return () => controller.abort();
}, [page, filters]);
```
Or switch to React Query, which handles cancellation automatically.

**Severity:** Low in fast networks; Medium under realistic network conditions. The UX consequence is incorrect data displayed without any error indication.

---

### F3 — Off-by-One in Client-Side Pagination

**File:** `app/frontend/src/components/Pagination.tsx`, line ~14

**The bug:**
```tsx
// BUG F3: Math.floor instead of Math.ceil — last page hidden when total % pageSize !== 0
const totalPages = Math.floor(totalItems / pageSize);
```

With 47 orders and pageSize=20: `Math.floor(47/20) = 2`. The third page (orders 41–47) is never reachable.

**Reproduction:**
1. Log in and go to `/orders`.
2. The backend returns `total=47`. With page_size=20, there should be 3 pages.
3. The pagination shows "Page 1 of 2" and there is no way to reach page 3.

**Strong candidate finds it by:** Checking `Math.floor` vs `Math.ceil` during code review. Simple unit test: `expect(totalPages(47, 20)).toBe(3)`.

**Weak candidate misses because:** With small datasets (e.g., `total=40, pageSize=20`), `Math.floor == Math.ceil` and the bug does not manifest.

**Remediation:** `Math.ceil(totalItems / pageSize)`.

**Severity:** Medium — users cannot access the last page when item count is not perfectly divisible by page size. Data is invisible but not lost.

---

### F4 — setInterval Not Cleaned Up

**File:** `app/frontend/src/hooks/useStats.ts`, line ~19

**The bug:**
```tsx
useEffect(() => {
  const id = setInterval(fetch, 10_000);
  // BUG F4: no return () => clearInterval(id) — interval stacks on re-renders
}, []);
```

Every time the component mounts (e.g., navigating away and back), a new interval is added without clearing the previous one. After 5 navigations, 5 concurrent intervals are polling the stats endpoint simultaneously.

**Reproduction:**
1. Open the Dashboard page.
2. Navigate to Orders and back to Dashboard 5 times.
3. Open Network DevTools — observe 5× the expected `/orders/stats` requests firing every 10 seconds.
4. React DevTools Profiler shows re-render spikes every 10 seconds, multiplied.

**Strong candidate finds it by:** Code review (missing `return () => clearInterval(id)` is a well-known React pattern). Performance testing with navigation. Writes a Vitest test that mounts/unmounts the component and asserts `clearInterval` was called.

**Weak candidate misses because:** The bug is invisible in a single navigation session.

**Remediation:** `return () => clearInterval(id);` at the end of the `useEffect` callback.

**Severity:** Medium — causes memory leaks and excess API load in long sessions. In production with a complex stats query, this degrades DB performance proportionally to user session duration.

---

### F5 — RBAC Mismatch Between UI and API

**File:** `app/frontend/src/components/DeleteButton.tsx`, line ~18

**The bug:**
```tsx
// BUG F5: hides button for role !== 'admin' — editors cannot see the delete button
// The correct check should be role === 'viewer'
if (role !== "admin") return null;
```

The backend `DELETE /orders/{id}` endpoint allows `admin` role only — that is correct. The frontend is supposed to hide the button only from `viewer` role (editors should see it, attempt it, and get a 403). Instead the UI hides it from both `viewer` and `editor`, so editors never discover they can't delete (even though the API correctly rejects them).

This is a UX/RBAC mismatch: the UI is more restrictive than documented intent.

**Reproduction:**
1. Log in as `editor@example.com`.
2. Navigate to any order — there is no Delete button.
3. Per the spec, editors should see the Delete button (and receive a 403 when they try it).
4. Log in as `admin@example.com` — Delete button is visible.

**Strong candidate finds it by:** Testing all three roles systematically. Cross-referencing the UI behavior with the API RBAC logic. Noting that the API returns 403 for editors (correct) but the UI never gives editors the chance to try (incorrect).

**Weak candidate misses because:** The UI appears to "work" — no errors are shown. Candidate only tests happy path (admin deletes successfully).

**Remediation:** Change `if (role !== "admin") return null;` to `if (role === "viewer") return null;`. Then ensure the UI shows an appropriate error when an editor's delete request returns 403.

**Severity:** Low security risk (the API enforces RBAC correctly). Medium UX bug — editor role capabilities are silently hidden, causing confusion about the permission model.

---

### F6 — Timezone Display Bug

**File:** `app/frontend/src/pages/OrderDetail.tsx`, line ~37

**The bug:**
```tsx
{/* BUG F6: no timezone specified — displays UTC as local time without indication */}
<dd>{new Date(order.created_at).toLocaleString()}</dd>
```

The backend stores `created_at` in UTC. `toLocaleString()` without a timezone argument converts to the browser's local timezone silently. A team member in UTC+5:30 sees "3:30 AM" for a record created at 22:00 UTC, while a colleague in UTC sees "10:00 PM". Neither knows which timezone is being shown.

**Reproduction:**
1. Change your system timezone to something non-UTC (e.g., UTC+5:30).
2. Load an order detail page.
3. The `Created` and `Updated` timestamps show local time with no timezone label.
4. Compare with the raw `created_at` value in the API response (UTC).

**Strong candidate finds it by:** Checking timestamp rendering with axe or manual review. Writes a test that renders the component with a known UTC timestamp and asserts the displayed string includes a timezone indicator.

**Weak candidate misses because:** If the tester is in UTC, the times look correct. The bug only manifests in non-UTC timezones.

**Remediation:**
```tsx
{new Date(order.created_at).toLocaleString(undefined, { timeZone: "UTC", timeZoneName: "short" })}
```
Or use `date-fns-tz` for explicit timezone handling.

**Severity:** Low functional impact; Medium in distributed teams or compliance contexts where audit timestamps must be unambiguous.

---

### F7 — Accessibility Issues (Three Violations)

#### F7a — Status Filter Select Missing Label

**File:** `app/frontend/src/pages/Orders.tsx`, line ~29

**The bug:** The `<select>` element has no `id` attribute and no `<label htmlFor>` pairing. Screen readers cannot announce what the control is for.

#### F7b — Status Badge WCAG AA Color Contrast Failure

**File:** `app/frontend/src/components/StatusBadge.tsx`, line ~11

**The bug:**
```tsx
pending:    { color: "#FFD700", backgroundColor: "#FFFFFF" },  // contrast ~1.07:1
processing: { color: "#FFD700", backgroundColor: "#FFFFFF" },  // contrast ~1.07:1
```
WCAG AA requires 4.5:1 for normal text. Yellow (`#FFD700`) on white is nearly invisible and fails by a factor of ~4.

#### F7c — CSV File Input Missing Label

**File:** `app/frontend/src/pages/Upload.tsx`, line ~36

**The bug:** The `<input type="file">` has no `aria-label` attribute and no associated `<label>` element.

**Reproduction for all three:** Run axe DevTools browser extension on `/orders` and `/upload`. All three violations are reported automatically.

**Strong candidate finds it by:** Running axe or Lighthouse and reporting all violations with WCAG criterion references. Writes automated accessibility tests using `@axe-core/playwright` in the Playwright suite.

**Weak candidate misses because:** Manual visual inspection does not catch color contrast issues (the text is visible to people without visual impairments). File input and select violations are also invisible to sighted testers.

**Remediation:**
- F7a: Add `id="status-filter"` to the `<select>` and `<label htmlFor="status-filter">Status</label>` above it.
- F7b: Change pending/processing badge colors to meet 4.5:1 ratio (e.g., amber text `#92400e` on amber background `#fef3c7`, or dark text on colored background).
- F7c: Wrap in `<label>` or add `aria-label="Upload CSV file"` to the `<input>`.

**Severity:** Medium — WCAG AA compliance is a legal requirement in many jurisdictions. Affects users with screen readers or color vision deficiencies.

---

## 2. Scoring Guide per Rubric Dimension

### Dimension 1: Decision-Making and Prioritisation (20%)

**Below bar:** No strategy doc, or a doc that lists "I will test everything." No risk-based ordering. Cannot explain why certain bugs matter more than others.

**At bar:** Strategy doc exists. Correct identification that authentication (B4) and data integrity (B1, B2, B3) are higher priority than UX issues (F5, F6). Some acknowledgment of testing pyramid balance.

**Above bar:** Strategy doc is clear enough to hand to a new engineer as an onboarding artifact. Explicit out-of-scope items with rationale ("I deferred load testing because the single-Postgres setup would bottleneck before app logic"). Severity triage aligns with business impact (financial precision > UX > a11y).

**Lead-level:** Strategy doc reads like an engineering design doc. Includes: risk matrix, test coverage gaps acknowledged upfront, explicit decision log. Candidate can defend every prioritisation call under questioning. Identifies the logging gap as a testability issue (can't write good assertions without logs).

---

### Dimension 2: Bug Discovery Quality (20%)

**Below bar:** Fewer than 4 bugs found. Reports bugs as "it returned wrong data" without root cause. Cannot reproduce consistently.

**At bar:** 6–9 bugs found. Each has steps to reproduce and a suspected root cause. F7 accessibility violations found via tooling. B4 found by testing without auth.

**Above bar:** 10–12 bugs found. Root cause analysis is correct and specific (e.g., "B3 is a float precision issue because Python float is IEEE 754 double, not decimal"). Includes evidence (curl output, DB query, network tab screenshot). Severity reasoning is defensible.

**Lead-level:** All 13 bugs found. Candidates note the *interaction* between bugs (e.g., B1 and F3 both affect pagination but at different layers — a user sees the wrong items AND can't reach the last page). Proposes systemic fixes (e.g., "add a DB constraint on external_id AND add idempotency middleware") not just per-bug patches.

---

### Dimension 3: Test Architecture (20%)

**Below bar:** Only happy-path E2E tests. No unit tests. No testcontainers. Coverage report not included.

**At bar:** All three pyramid layers present. pytest unit tests for order creation logic. At least one testcontainers integration test for the auth flow. Playwright E2E covers login + order list. CI runs the pyramid.

**Above bar:** Contract tests cover RBAC (all roles × all endpoints). Pagination tests parametrised across page/size combinations that expose B1. Test fixtures are isolated (no shared state between tests). Coverage gate in CI.

**Lead-level:** Test suite could be dropped into a production repo unchanged. Uses testcontainers for the full stack test (real DB, real migrations). Has property-based tests for the float arithmetic (e.g., Hypothesis: for any price p and quantity q, `Decimal(str(p)) * q == total`). Flake detection integrated into CI.

---

### Dimension 4: Test Insights Dashboard (15%)

**Below bar:** Static HTML report. No way to query by test run or filter by status. No video/screenshot access.

**At bar:** Real app (not a static report). Ingests pytest JUnit XML and Playwright JSON. Can answer "what failed in the last run?" with one click.

**Above bar:** Pass rate trending over N runs. Flake rate visible (tests that sometimes pass, sometimes fail). Can view Playwright trace/video from within the dashboard. Single `docker-compose up` to start.

**Lead-level:** The dashboard is something an engineer would actually use on Monday morning. Clearly scoped ("I chose not to add multi-project support because it adds complexity without signal"). Decision log in the PR description explains every major design choice. Candidate can demo a failure triage without fumbling.

---

### Dimension 5: CI/CD Quality Gates (10%)

**Below bar:** No CI pipeline. Or a pipeline that always passes.

**At bar:** GitHub Actions runs pytest and Playwright on every PR. Fails on test failure. Publishes artifacts.

**Above bar:** Coverage gate (fails if coverage drops). Flake detection (re-runs failing tests once, flags as flaky if they pass on retry). Distinct jobs for unit/integration/E2E so failures are locatable.

**Lead-level:** Pipeline includes: coverage gate, lint gate, type check gate. Definition of Done is written and included in PR template. Pipeline caches dependencies for speed. E2E job uploads video artifacts on failure.

---

### Dimension 6: Logging Gap-Fill (5%)

**Below bar:** No changes to logging. Or adds a `print` statement.

**At bar:** Adds structlog calls to the CSV upload handler (entry, row count, commit confirmation). Explains why the gap matters (can't debug duplicate uploads without knowing the upload was attempted).

**Above bar:** Adds logging to the CSV handler AND documents which other gaps exist but were left out of scope (e.g., "I did not add per-row logging because it would produce excessive output at scale — a counter per batch is sufficient").

**Lead-level:** Proposes a logging standard: every mutating operation logs the actor (user_id), the resource (order_id), the action, and the outcome. Gap-fill follows this standard. Includes a structured log assertion in the integration test.

---

### Dimension 7: AI Orchestration and Judgment (10%)

**Below bar:** No AI Decision Journal, or a journal that says "AI was great for everything." No examples of overriding AI.

**At bar:** Journal has 5+ meaningful prompts. One honest example of AI being wrong (e.g., "AI suggested using `datetime.utcnow()` which is deprecated; I used `datetime.now(timezone.utc)` instead"). At least one thing deliberately not delegated to AI.

**Above bar:** Journal reveals genuine judgment: candidate delegated scaffolding and syntax to AI, retained architectural decisions and test strategy. Override example is specific and well-reasoned.

**Lead-level:** Journal is insightful enough to be a team onboarding artifact on "how to use AI in quality engineering." Live session shows fluent AI use with clear "I won't delegate this" moments (e.g., "I'm not letting AI write the severity triage because that requires knowing our business context").

---

## 3. Live Session Task Bank

Each task below is scoped to ~30 minutes with AI assistance. Assign one task at the start of the live session and evaluate in real time.

---

### Task L1 — Write a Regression Test for B1 (Pagination)

**Prompt to candidate:** "The pagination in `GET /orders` has a bug. Write a pytest integration test using testcontainers that proves the bug exists, then fix the code and verify the test passes."

**What good looks like:**
```python
@pytest.mark.asyncio
async def test_pagination_no_overlap(client, seeded_db):
    # Get page 1 and page 2 with page_size=5
    r1 = await client.get("/orders?page=1&page_size=5", headers=auth_headers)
    r2 = await client.get("/orders?page=2&page_size=5", headers=auth_headers)
    ids_p1 = {o["id"] for o in r1.json()["items"]}
    ids_p2 = {o["id"] for o in r2.json()["items"]}
    assert ids_p1.isdisjoint(ids_p2), "pages must not share items"
```
Fix: change `(page - 1) * page_size - 1` to `(page - 1) * page_size`.

**Lead-level indicator:** Candidate parametrises the test across multiple page/size combinations without being asked.

---

### Task L2 — Add Structured Logging to the CSV Upload Handler

**Prompt to candidate:** "The CSV upload handler has no logging. Add structlog instrumentation that would help an on-call engineer debug a duplicate upload incident."

**What good looks like:**
```python
async def upload_csv(file, db, current_user):
    logger.info("csv_upload_started", user_id=str(current_user.id), filename=file.filename)
    ...
    for row in reader:
        logger.debug("csv_row_processing", external_id=row["external_id"])
        ...
    await db.commit()
    logger.info("csv_upload_completed", user_id=str(current_user.id), rows_created=created)
```
Candidate should explain: entry log (who uploaded, what file), per-commit log (how many rows), and an exception log (`logger.exception` in a try/except wrapping the whole handler).

**Lead-level indicator:** Mentions that per-row debug logging should be gated behind a log level check to avoid log flooding in production.

---

### Task L3 — Triage a Production-Style Log Dump

**Hand the candidate this log snippet (paste it into the chat):**

```json
{"event": "request", "method": "GET", "path": "/orders", "status_code": 200, "duration_ms": 4823, "request_id": "a1b2c3"}
{"event": "request", "method": "GET", "path": "/orders", "status_code": 200, "duration_ms": 4901, "request_id": "d4e5f6"}
{"event": "request", "method": "GET", "path": "/orders", "status_code": 200, "duration_ms": 4756, "request_id": "g7h8i9"}
```

**Prompt to candidate:** "These are three consecutive `GET /orders` requests from our production API. The p99 for this endpoint is 200ms. What is happening, and how would you confirm and fix it?"

**What good looks like:** Candidate identifies that 4.8s latency on a list endpoint strongly suggests N+1 queries (B6). Confirms by enabling SQLAlchemy echo or query logging and counting queries per request. Fix: remove the items-in-loop pattern and use the already-loaded `Order.items` JSONB column directly.

**Lead-level indicator:** Candidate immediately asks "how many orders are on the page?" (determines N), estimates the expected query count (N+1), and proposes a test that asserts `query_count <= 2` per request.

---

### Task L4 — Fix the Float Currency Bug (B3)

**Prompt to candidate:** "A finance team member reports that order totals are occasionally off by a fraction of a cent. Find the root cause in the codebase and fix it without breaking the existing API contract."

**What good looks like:**
```python
from decimal import Decimal

total = sum(
    Decimal(str(item["price"])) * item["quantity"]
    for item in items
)
# Store as float for the response (API contract unchanged)
order.total_amount = float(total)
```
Candidate explains: `float` is IEEE 754 and cannot represent 0.1 exactly; `Decimal` uses base-10 arithmetic; parsing via `str()` first avoids float contamination. Also updates the CSV upload handler.

**Lead-level indicator:** Proposes adding a property-based test using Hypothesis: generate random `(price, quantity)` pairs and assert `Decimal(str(price)) * quantity == Decimal(str(price * quantity))` — this should fail with the bug and pass after the fix.

---

### Task L5 — Schema Change with Backward Compatibility

**Prompt to candidate:** "The product team wants to add a `tags` field (array of strings) to orders. How would you add this field without breaking existing clients, and what tests would you write to verify backward compatibility?"

**What good looks like:**
1. **Migration:** Add `tags JSONB DEFAULT '[]'::jsonb NOT NULL` — nullable-default approach ensures existing rows get an empty array without a table lock.
2. **API:** Add `tags: list[str] = []` to `OrderCreate` and `OrderResponse` schemas (default ensures existing clients that don't send `tags` still work).
3. **Backward compat test:** Write an integration test that creates an order using a request body without `tags` and asserts the response includes `"tags": []`.
4. **Forward compat:** Test that a client that reads the response but ignores unknown fields still works.

**Lead-level indicator:** Candidate asks about the migration strategy (`DEFAULT` vs `nullable` vs two-phase deploy), mentions that `JSONB DEFAULT '[]'` is safe for Postgres but would need a backfill in some other DBs, and notes that the Alembic migration should be reversible (downgrade removes the column).

---

## 4. Calibration Notes

**On bug count:** Score depth, not count. A candidate who finds 5 bugs with correct root-cause analysis and a failing test for each beats one who lists all 13 as bullet points with "it returned wrong data."

**On the dashboard:** Run the Monday-morning triage demo before scoring. Pretty ≠ useful. Ask the candidate to show you the last failing E2E — if they have to navigate more than 3 clicks to get to the screenshot/video, it's not useful.

**On AI journal:** Look for honest self-awareness. A candidate who says "AI suggested using `datetime.utcnow()` which is deprecated in Python 3.12 and I caught it because I know the stdlib" is stronger than one who says "AI was great for everything." The worst journals are pure AI cheerleading with no override examples.

**On F7 accessibility:** A candidate who finds F7 only via `axe` tooling (no manual discovery) is at bar. A candidate who finds it via manual testing with a screen reader is above bar. A candidate who doesn't find it at all and doesn't run `axe` is below bar.

**On B6 N+1:** A candidate who finds this via code review alone (spots the loop pattern) is above bar. A candidate who finds it via performance testing (high latency, query count in logs) is Lead-level. A candidate who misses it entirely despite running the app for 30 minutes has a significant gap.

---

## 5. Go / No-Go Decision Criteria

### Automatic No-Go
- No CI pipeline (empty `.github/workflows/` with no additions) — indicates candidate cannot operate in a modern engineering team.
- No test strategy document — indicates candidate cannot think at a system level.
- No bug discovery report — indicates candidate did not engage with the assignment.

### Strong Pass
- Finds at least 8 of 13 bugs with correct root causes.
- Test pyramid has all three layers, each with meaningful assertions.
- Dashboard is demonstrably useful (triage demo works, failure is findable in under 3 clicks).
- AI journal shows at least one honest override example.

### Lead-Level Pass
- Test strategy document could be used as a team onboarding artifact.
- Finds all 13 bugs or provides compelling justification for any missed.
- Dashboard would be used in production (focused scope, real data, actionable views).
- Live session shows fluent AI orchestration with clear "I won't delegate this" moments — candidate can explain *why* they retained certain decisions.
- Proposes systemic improvements beyond the per-bug fixes (e.g., "add a linting rule to ban float arithmetic in money calculations", "add a testcontainers fixture shared across all integration tests").
