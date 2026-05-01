# Bug Report — Order Processing

This report lists the defects found in the Order Processing app. Each issue is written in the same simple format:

- **Problem** — what user/operator impact it creates
- **Actual** — what the app does today
- **Expected** — what the app should do
- **Fix** — recommended direction

## Severity Key

| Severity | Meaning |
| --- | --- |
| **P0** | Security or production blocker. Fix first. |
| **P1** | Major functional, data integrity, or core workflow issue. |
| **P2** | Reliability, performance, or misleading UX issue. |
| **P3** | Polish, accessibility, or clarity issue. |

## Executive Summary

The highest-risk issue is **B4**, where `/orders/stats` exposes order volume and revenue without authentication. The next highest risks are data correctness issues: duplicate CSV imports, float-based money totals, pagination overlap, and an unclear delete contract.

Frontend issues mainly affect stale data, pagination, polling cleanup, role clarity, timestamps, and accessibility. Two logging gaps were fixed in this PR to make bulk upload and authenticated request debugging easier.

Detailed proof for the top defects is in `evidence/`:

- `evidence/B4_stats_unauthenticated.md` — unauthenticated stats endpoint
- `evidence/B1_pagination_overlap.md` — pagination overlap
- `evidence/B3_decimal_drift.md` — float drift vs Decimal

## Quick Reference

| ID | Area | Sev | Actual | Expected |
| --- | --- | --- | --- | --- |
| B4 | Backend | P0 | `/orders/stats` returns `200` with no token. | Return `401 Unauthorized` without a valid JWT. |
| B1 | Backend | P1 | Page 1 and page 2 can overlap. | Each order appears once across pages. |
| B2 | Backend | P1 | Same CSV uploaded twice creates duplicate orders. | Re-upload skips or upserts existing `external_id`s. |
| B3 | Backend | P1 | `0.1 * 3` can store as `0.30000000000000004`. | Money totals use exact decimal handling. |
| B7 | Backend | P1 | `DELETE` returns `204`, but the order still exists. | Either hard-delete or clearly document soft-delete. |
| F1 | Frontend | P1 | Filter changes do not refetch the list. | Table reloads whenever filters change. |
| F3 | Frontend | P1 | 23 items at page size 10 shows only 2 pages. | Show 3 pages using `Math.ceil`. |
| B5 | Backend | P2 | Timezone filters can miss boundary rows. | Normalize input times to UTC before comparing. |
| B6 | Backend | P2 | Listing `N` orders runs `1 + N` queries. | Use eager loading / constant query count. |
| F2 | Frontend | P2 | Older request can overwrite newer filter results. | Cancel old requests; render only latest response. |
| F4 | Frontend | P2 | Stats polling continues after leaving page. | Clear interval on unmount. |
| F5 | Frontend | P2 | Delete button is hidden for editors without explanation. | Match RBAC rules and show disabled state with reason. |
| F6 | Frontend | P3 | Timestamps show no timezone. | Show timezone explicitly. |
| F7 | Frontend | P3 | Select/file controls are missing labels. | Add labels or `aria-label`. |
| L1 | Logging | Fixed | CSV upload had no structured events. | Emits upload started/completed events. |
| L2 | Logging | Fixed | Request logs lacked authenticated `user_id`. | Auth dependency binds `request.state.user_id`. |

## Backend Bugs

### B4 — Stats Endpoint Has No Authentication (P0)

**Problem:** `/orders/stats` returns business-sensitive numbers: total orders, status breakdown, and total revenue. It should require login, but it does not.

**Actual:**

```bash
$ curl -i http://localhost:8000/orders/stats
HTTP/1.1 200 OK

{"total_orders":47,"by_status":{"pending":12,"processing":10,"completed":18,"failed":7},"total_amount":2492.34}
```

**Expected:**

```bash
$ curl -i http://localhost:8000/orders/stats
HTTP/1.1 401 Unauthorized

{"detail":"Not authenticated"}
```

**Why P0:** Anyone who can reach the server can scrape revenue/order-volume signals without an account.

**Root cause:** `get_order_stats` in `app/backend/app/routers/orders.py` is missing `Depends(get_current_user)`.

**Fix:** Add the auth dependency. If stats are admin-only, also enforce role checks.

```python
@router.get("/stats", response_model=OrderStats)
async def get_order_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> OrderStats:
    ...
```

### B1 — Pagination Skips Or Duplicates Rows (P1)

**Problem:** Users cannot safely page through the full order list because one row can repeat and another can disappear.

**Actual:** With 25 orders and `page_size=20`:

- Page 1 returns ids `[1..20]`.
- Page 2 returns ids `[20, 21, 22, 23, 24]`.
- Id `20` repeats; id `25` is missing.

**Expected:**

- Page 1 returns `[1..20]`.
- Page 2 returns `[21..25]`.
- Pages do not overlap.

**Root cause:** `list_orders` uses `offset = (page - 1) * page_size - 1`.

**Fix:** Use `offset = (page - 1) * page_size`.

### B2 — CSV Upload Is Not Idempotent (P1)

**Problem:** Re-uploading the same CSV creates duplicate orders and can inflate counts/revenue.

**Actual:** Uploading `EXT-001`, `EXT-002`, `EXT-003` twice creates 6 rows.

**Expected:** The second upload should keep the count at 3 and return a summary such as `{"inserted": 0, "skipped": 3}`.

**Root cause:** `upload_csv` inserts rows without checking whether `external_id` already exists.

**Fix:** Add a unique constraint on `external_id` and use either upsert or skip-with-summary behavior.

### B3 — Money Totals Use Floating-Point Math (P1)

**Problem:** Currency math uses Python `float`, which can produce decimal drift.

**Actual:** Creating an order with `price = 0.1`, `quantity = 3` can return/store `0.30000000000000004`.

**Expected:** Store and return an exact decimal value such as `Decimal("0.30")` or `"0.30"`.

**Root cause:** Totals are calculated with expressions like `item["price"] * item["quantity"]`.

**Fix:** Use `Decimal` end-to-end, store as SQL `Numeric`, and document the rounding rule.

### B5 — Date Filters Mishandle Timezones (P2)

**Problem:** Date range filters can include or exclude the wrong rows for users outside the server timezone.

**Actual:** An order at `2026-04-26T23:30:00Z` can be excluded by `start_date=2026-04-27T00:00:00+05:30`, even though the UTC cutoff is `2026-04-26T18:30:00Z`.

**Expected:** Normalize filter inputs to UTC before comparing with timezone-aware DB columns.

**Root cause:** `datetime.fromisoformat(start_date)` is used without consistent UTC normalization.

**Fix:** Parse timezone-aware input and convert to UTC before applying the SQL filter.

### B6 — Order List Has N+1 Queries (P2)

**Problem:** Listing orders gets slower as the number of rows grows.

**Actual:** Listing 50 orders can run 1 query for orders plus 50 extra queries for items.

**Expected:** Listing should use 1 or 2 total queries via eager loading.

**Root cause:** `list_orders` loads items inside a per-order loop.

**Fix:** Use `selectinload`, a join, or a DTO/query shape that loads items in bulk.

### B7 — Delete API Contract Is Misleading (P1)

**Problem:** The endpoint looks like a hard delete but actually performs a soft delete.

**Actual:**

- `DELETE /orders/42` returns `204 No Content`.
- `GET /orders/42` still returns `200 OK` with `status: "failed"`.

**Expected:** Choose one clear contract:

- **Hard delete:** `GET /orders/42` returns `404`.
- **Soft delete:** `DELETE` returns `200` with a body explaining the new status, and docs/UI say it is archived/retired.

**Root cause:** Handler sets `order.status = OrderStatus.failed` instead of deleting or documenting soft-delete behavior.

**Fix:** Pick one contract and align backend, OpenAPI docs, and UI copy.

## Frontend Bugs

### F1 — Filters Do Not Refetch Orders (P1)

**Problem:** The orders table can show stale data after a filter change.

**Actual:** On page 1, changing Status from `All` to `Completed` sends no new request and the table stays unchanged.

**Expected:** Changing filters sends a new `GET /orders?...&status=completed` request and updates the table.

**Root cause:** `useOrders.ts` has `useEffect(..., [page])`; filters are not dependencies.

**Fix:** Add filters (or a stable serialized filter key) to the dependency array. Debounce if needed.

### F2 — Old Requests Can Overwrite Newer Filter Results (P2)

**Problem:** Fast typing/filter changes can display results for an older request.

**Actual:** Requests for `"a"`, `"ab"`, and `"abc"` all fire. If `"a"` returns last, it overwrites the `"abc"` results.

**Expected:** Older in-flight requests are cancelled or ignored.

**Root cause:** Axios call does not use `AbortController` or equivalent stale-response protection.

**Fix:** Abort the previous request when filters change and only render the latest response.

### F3 — Pagination Uses Floor Instead Of Ceiling (P1)

**Problem:** The final partial page can be unreachable.

**Actual:** `totalItems = 23`, `pageSize = 10` shows only 2 pages, so items 21–23 are hidden.

**Expected:** Show 3 pages because `Math.ceil(23 / 10) = 3`.

**Root cause:** `Pagination.tsx` uses `Math.floor(totalItems / pageSize)`.

**Fix:** Use `Math.ceil`, or use `total_pages` from the API if exposed.

### F4 — Stats Polling Is Not Cleaned Up (P2)

**Problem:** The dashboard can keep making network requests after the user leaves the page.

**Actual:** `GET /orders/stats` continues firing after navigation.

**Expected:** Polling stops on component unmount.

**Root cause:** `setInterval` in `useStats.ts` has no `clearInterval` cleanup.

**Fix:** Return a cleanup function from `useEffect`.

### F5 — Delete Button Role Behavior Is Unclear (P2)

**Problem:** Editors do not see a delete button, while the backend also blocks editor delete with `403`. That may be correct, but the UX gives no explanation.

**Actual:** Editor user sees no delete control.

**Expected:** Product should confirm the rule:

- If editors can delete, backend and UI should allow it.
- If editors cannot delete, UI should show a disabled button with an "Admins only" explanation.

**Root cause:** `DeleteButton.tsx` returns `null` when `role !== "admin"`.

**Fix:** Align RBAC rules and show a disabled state with explanation where appropriate.

### F6 — Timestamps Have No Timezone (P3)

**Problem:** Users may misread order times.

**Actual:** `Created: 4/26/2026, 10:55:11 PM` shows no timezone.

**Expected:** Show a timezone, for example `2026-04-26 22:55 UTC` or local time with `IST`/`UTC`.

**Root cause:** `toLocaleString()` is used without a timezone label.

**Fix:** Add `timeZoneName: "short"` or render an explicit suffix.

### F7 — Form Controls Are Missing Labels (P3)

**Problem:** Screen reader users and stable UI tests have less context.

**Actual:** Status `<select>` and CSV `<input type="file">` have no associated label.

**Expected:** Each control has a `<label htmlFor="...">` or `aria-label`.

**Fix:** Add labels to the controls.

## Logging Gaps Fixed In This PR

### L1 — CSV Upload Logging

**Before:** Bulk uploads had no structured log event, so failures were hard to connect to a user or file.

**After:** Added `csv_upload_started` and `csv_upload_completed` with filename, byte size, row count, and `user_id`.

### L2 — Authenticated User In Request Logs

**Before:** `LoggingMiddleware` read `request.state.user_id`, but no auth path populated it.

**After:** `get_current_user` sets `request.state.user_id` after JWT validation, so request logs include the authenticated principal.

## Automated Regression Tracking

Encoded backend defect tests live in `app/backend/tests/test_known_defects.py`. They assert the expected behavior and use `pytest.mark.xfail(strict=True)`.

Why this matters:

- While the bug exists, the test is an expected failure (`XFAIL`) and the suite stays green.
- When the bug is fixed correctly, the test unexpectedly passes (`XPASS`) and pytest fails the build.
- The developer must then remove the `xfail` marker, which confirms the bug is fixed and the regression guard is now active.

Frontend bug F3 uses the same idea with Vitest `it.fails` in `app/frontend/src/components/Pagination.test.tsx`.
