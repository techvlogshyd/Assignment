# Bug discovery report — Order Processing

Issues are grouped by layer. Severity uses a simple scale: **P0** production blocker / security, **P1** major functional or data integrity, **P2** incorrect UX or reliability, **P3** polish / accessibility.

Reproduction transcripts (curl output, pytest output, source diffs) for the highest-severity issues live under `evidence/`:

- `evidence/B4_stats_unauthenticated.md` — P0 unauth stats endpoint with HTTP traces
- `evidence/B1_pagination_overlap.md` — page-overlap repro, jq diff, source diff
- `evidence/B3_decimal_drift.md` — float arithmetic repro and Decimal fix sketch

Every encoded contract test in `app/backend/tests/test_known_defects.py` uses `pytest.mark.xfail(strict=True)` — when a developer correctly fixes one of these bugs the suite fails the build with an `XPASS`, forcing the marker to be removed and acknowledging the regression guard is now active.

---

## Backend (FastAPI / persistence)

### B1 — Pagination skips a row between pages (P1)

- **Symptom:** Consecutive pages can return the same order twice; some orders never appear when paging through the full list.
- **Repro:** Create more than twenty orders; `GET /orders?page=1&page_size=20` then `page=2` and compare `id` sets — intersection is non-empty.
- **Evidence:** `list_orders` uses `offset = (page - 1) * page_size - 1` in `app/backend/app/routers/orders.py`.
- **Root cause:** Off-by-one in offset calculation.
- **Fix:** Use `offset = (page - 1) * page_size`.

### B2 — CSV upload is not idempotent on `external_id` (P1)

- **Symptom:** Re-uploading the same file creates duplicate orders; seed data documents `EXT-001`…`EXT-003` as collision keys.
- **Repro:** `POST /orders/upload-csv` twice with identical `external_id` values; row count increases each time.
- **Evidence:** No existence check before insert in `upload_csv`.
- **Root cause:** Missing upsert / unique constraint on `external_id` (model TODO notes the same).
- **Fix:** Add a unique index on `external_id` (scoped if needed) and `INSERT … ON CONFLICT` or skip-with-summary.

### B3 — Currency totals use binary floats (P1)

- **Symptom:** Totals can differ from decimal expectations (e.g. `0.1 * 3`).
- **Repro:** `POST /orders` with items `[{ "price": 0.1, "quantity": 3 }]`; compare `total_amount` to `Decimal("0.3")`.
- **Evidence:** `sum(item["price"] * item["quantity"]` in `create_order` and CSV handler.
- **Root cause:** Floating-point arithmetic for money.
- **Fix:** Use `Decimal` end-to-end; store as `Numeric`; round with a declared policy.

### B4 — Order statistics endpoint is unauthenticated (P0)

- **Symptom:** Anyone can read aggregate counts and revenue without a token.
- **Repro:** `curl http://localhost:8000/orders/stats` with no `Authorization` header — returns `200`.
- **Evidence:** `get_order_stats` omits `Depends(get_current_user)` in `orders.py`.
- **Root cause:** Missing dependency.
- **Fix:** Require authentication (and likely role-based policy if stats are sensitive).

### B5 — Date filter parsing drops timezone (P2)

- **Symptom:** Filtered ranges can be wrong for users not in the same zone as naive parsing.
- **Repro:** Persist orders with `timestamptz`; filter with ISO strings carrying offsets; boundary orders appear/disappear incorrectly.
- **Evidence:** `datetime.fromisoformat(start_date)` without normalising to aware UTC before comparing to `DateTime(timezone=True)` columns.
- **Root cause:** Naive datetime comparison.
- **Fix:** Parse with `zoneinfo` / `datetime` aware UTC normalisation.

### B6 — N+1 queries on order list (P2)

- **Symptom:** Listing orders issues one extra query per row for items.
- **Evidence:** Loop with `select(Order.items)` per order in `list_orders`.
- **Root cause:** Eager loading not used; redundant per-row selects.
- **Fix:** `selectinload` / join-loaded JSON or denormalised projection DTO.

### B7 — “Delete” does not delete (P1 / contract)

- **Symptom:** `DELETE /orders/{id}` returns `204` but the row remains queryable with `failed` status.
- **Repro:** Delete as admin; `GET` same id — still `200`.
- **Evidence:** Handler sets `order.status = OrderStatus.failed` instead of removing the row.
- **Root cause:** Soft-delete semantics without API documentation.
- **Fix:** Either hard-delete or return `200` with a body explaining soft-delete, and align UI copy.

---

## Frontend (React)

### F1 — `useOrders` omits filters from `useEffect` deps (P1)

- **Symptom:** Changing filters while staying on the same page does not refetch; data appears “stuck”.
- **Evidence:** `useEffect(..., [page])` only in `useOrders.ts`.
- **Fix:** Include `filters` (or a stable serialised key) in the dependency array with debouncing if needed.

### F2 — No in-flight cancellation for list requests (P2)

- **Symptom:** Rapid filter changes can show results for an older request (race).
- **Evidence:** Axios call without `AbortController` in `useOrders.ts`.
- **Fix:** Abort prior request when deps change.

### F3 — Pagination uses `Math.floor` for total pages (P1)

- **Symptom:** Last page of results is unreachable when `totalItems % pageSize !== 0`.
- **Evidence:** `Pagination.tsx` uses `Math.floor(totalItems / pageSize)`.
- **Fix:** `Math.ceil` and align with backend `total_pages` if exposed.

### F4 — Stats polling leaks intervals (P2)

- **Symptom:** Memory / network churn grows when navigating away from the dashboard.
- **Evidence:** `setInterval` without `clearInterval` on unmount in `useStats.ts`.
- **Fix:** Return cleanup from `useEffect`.

### F5 — Delete affordance inconsistent with backend roles (P2)

- **Symptom:** Delete button hidden for non-admin editors even though the primary workflow might expect editors to retire orders (product decision); backend in any case forbids editor delete with `403`.
- **Evidence:** `DeleteButton.tsx` returns `null` when `role !== "admin"`.
- **Fix:** Align RBAC product rules and surface disabled state with explanation.

### F6 — Order detail timestamps shown without TZ context (P3)

- **Symptom:** Users interpret wall times incorrectly vs UTC storage.
- **Evidence:** `toLocaleString()` without time zone label in `OrderDetail.tsx`.
- **Fix:** Show explicit zone or UTC suffix.

### F7 — Unlabelled form controls on Orders / Upload (P3 / a11y)

- **Symptom:** Status `<select>` and file `<input>` lack associated labels / `aria-label` (called out inline in components).
- **Fix:** Add `<label htmlFor=…>` or `aria-label`.

---

## Logging / observability

### L1 — CSV path had no structured events (addressed in this PR)

- **Gap:** Bulk uploads are high-risk; failures were hard to correlate to a user or file.
- **Change:** `csv_upload_started` / `csv_upload_completed` events with filename, byte size, row count, and `user_id`.

### L2 — Request logs lacked authenticated user (addressed in this PR)

- **Gap:** `LoggingMiddleware` read `request.state.user_id`, but nothing set it.
- **Change:** `get_current_user` now binds `request.state.user_id` after JWT validation, so request logs correlate to principals when auth succeeds.
