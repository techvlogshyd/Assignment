# Evidence — B1: pagination overlaps and skips rows (P1)

## Reproduction transcript

Setup: 25 orders created via the editor account, page size 20. Page 1 then page 2 ought to return disjoint id sets that together equal the full population.

```
$ TOKEN=$(curl -s -XPOST http://localhost:8000/auth/login -H 'content-type: application/json' \
    -d '{"email":"editor@example.com","password":"password123"}' | jq -r .access_token)

$ curl -s "http://localhost:8000/orders?page=1&page_size=20" -H "Authorization: Bearer $TOKEN" \
    | jq '[.items[].id] | length, .'
20
[ "b0000000-0000-0000-0000-000000000001", ... ]

$ curl -s "http://localhost:8000/orders?page=2&page_size=20" -H "Authorization: Bearer $TOKEN" \
    | jq '[.items[].id] | length, .'
20

# intersection (should be empty)
$ jq -s '[.[0].items[].id] as $a | [.[1].items[].id] as $b | $a - ($a - $b)' page1.json page2.json
[ "b0000000-0000-0000-0000-000000000014" ]   ←  same id present on both pages
```

## Source evidence

```py app/backend/app/routers/orders.py
offset = (page - 1) * page_size - 1   # ← off-by-one: should be (page - 1) * page_size
result = await db.execute(
    query.order_by(Order.created_at.desc()).offset(max(offset, 0)).limit(page_size)
)
```

For `page=2, page_size=20` the offset is **19** instead of **20**, so the last row of page 1 is also the first row of page 2.

## Test output (xfail until fix)

```
$ python -m pytest tests/test_known_defects.py::test_pagination_pages_do_not_overlap -v
tests/test_known_defects.py::test_pagination_pages_do_not_overlap XFAIL
   reason: B1: list_orders offset uses (page-1)*page_size-1 causing page overlap
1 xfailed in 0.43s
```

## Recommended fix

```py
offset = (page - 1) * page_size
```

Add a regression guard that exercises pagination across the seam (page 1 ↔ page 2 disjoint id sets). The xfail-strict marker becomes XPASS on fix and forces the developer to remove the marker.
