# Evidence — B3: order totals use binary floats (P1)

## Reproduction

```
$ curl -s -XPOST http://localhost:8000/orders \
    -H "Authorization: Bearer $TOKEN" -H 'content-type: application/json' \
    -d '{
          "external_id": "DEC-001",
          "customer_name": "Decimal test",
          "items": [{"name": "Widget", "price": 0.1, "quantity": 3}],
          "status": "pending"
        }' | jq .total_amount
0.30000000000000004
```

The seed data also includes orders with `0.1 * 3` and `0.2 * 2` line items so summing aggregate revenue is subject to the same drift.

## Source evidence

```py app/backend/app/routers/orders.py
total = sum(item["price"] * item["quantity"] for item in items)  # binary float
```

The CSV ingest path has the same defect:

```py app/backend/app/routers/orders.py
price = float(row["price"])
quantity = int(row["quantity"])
total = price * quantity
```

## Test output (xfail until fix)

```
$ python -m pytest tests/test_known_defects.py::test_currency_total_uses_exact_decimal_semantics -v
tests/test_known_defects.py::test_currency_total_uses_exact_decimal_semantics XFAIL
   reason: B3: order totals use float arithmetic instead of Decimal
1 xfailed in 0.41s
```

## Recommended fix

Use `decimal.Decimal` end-to-end, with a declared rounding policy:

```py
from decimal import Decimal, ROUND_HALF_UP

def line_total(price: str | float, quantity: int) -> Decimal:
    return (Decimal(str(price)) * Decimal(quantity)).quantize(Decimal("0.01"), ROUND_HALF_UP)

total = sum((line_total(i["price"], i["quantity"]) for i in items), start=Decimal("0"))
```

Storage column `Numeric(12, 4)` already exists; the only change is to stop converting to `float` on the way in.
