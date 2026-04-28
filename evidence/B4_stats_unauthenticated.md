# Evidence — B4: `GET /orders/stats` is unauthenticated (P0)

## Reproduction transcript

With the stack running locally (`docker compose -f infra/docker-compose.yml up`):

```
$ curl -i http://localhost:8000/orders/stats
HTTP/1.1 200 OK
date: Sun, 26 Apr 2026 16:55:11 GMT
server: uvicorn
content-length: 165
content-type: application/json

{"total_orders":47,"by_status":{"pending":12,"processing":10,"completed":18,"failed":7},"total_amount":2492.34}
```

For comparison, every other order endpoint correctly rejects an unauthenticated caller:

```
$ curl -i http://localhost:8000/orders
HTTP/1.1 401 Unauthorized
www-authenticate: Bearer
content-type: application/json

{"detail":"Not authenticated"}
```

## Source evidence

```py app/backend/app/routers/orders.py
@router.get("/stats", response_model=OrderStats)
async def get_order_stats(db: AsyncSession = Depends(get_db)) -> OrderStats:
    # NOTE: no Depends(get_current_user) — unauthenticated access allowed
    ...
```

Compare with `list_orders` directly below it, which correctly carries `current_user: User = Depends(get_current_user)`.

## Why P0

Aggregate revenue, order volume, and pipeline status are *business-sensitive*; a public competitor or scraper can poll this endpoint to estimate the platform's order velocity and churn between statuses. The defect is a one-line omission, so a fix is cheap, but the impact is data exfiltration without authentication.

## Test that pins this

`app/backend/tests/test_known_defects.py::test_order_stats_requires_authentication` asserts the endpoint should return `401`. It is wrapped in `pytest.mark.xfail(strict=True)` so a correct fix flips the test to `XPASS` and **fails the build**, forcing the developer to remove the `xfail` marker (acknowledging the bug as fixed).

## Recommended fix

```py
@router.get("/stats", response_model=OrderStats)
async def get_order_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> OrderStats:
    ...
```

If aggregate stats are sensitive even within the customer base, gate further by role (`UserRole.admin` only).
