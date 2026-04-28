"""Assertions encode *correct* behaviour; tests are xfail until product defects are fixed.

Markers use ``strict=True`` on purpose: when a developer correctly fixes one of these
bugs, the test will start passing and ``XPASS`` will fail the build, forcing the
author to remove the ``xfail`` marker (and thereby acknowledging the regression
guard is now active).
"""

from __future__ import annotations

import io

import pytest
from httpx import AsyncClient


@pytest.mark.xfail(reason="B4: GET /orders/stats has no auth dependency", strict=True)
@pytest.mark.asyncio
async def test_order_stats_requires_authentication(client: AsyncClient) -> None:
    r = await client.get("/orders/stats")
    assert r.status_code == 401


@pytest.mark.xfail(
    reason="B1: list_orders offset uses (page-1)*page_size-1 causing page overlap",
    strict=True,
)
@pytest.mark.asyncio
async def test_pagination_pages_do_not_overlap(
    client: AsyncClient, editor_token: str, many_orders: None
) -> None:
    headers = {"Authorization": f"Bearer {editor_token}"}
    p1 = await client.get("/orders", headers=headers, params={"page": 1, "page_size": 20})
    p2 = await client.get("/orders", headers=headers, params={"page": 2, "page_size": 20})
    assert p1.status_code == 200 and p2.status_code == 200
    ids1 = {o["id"] for o in p1.json()["items"]}
    ids2 = {o["id"] for o in p2.json()["items"]}
    assert ids1.isdisjoint(ids2), "duplicate rows across pages"


# B3 note: float arithmetic in source is real, but the `Numeric(12, 4)` column
# silently quantizes 0.1*3 -> 0.3 on the way into Postgres so a "round" case does
# not surface at the response. We document the drift via a precision case where
# the float pipeline loses digits that a Decimal pipeline (with a declared rounding
# policy) would preserve or reject. ``strict=False`` here because the bug is a
# code-quality one whose API observability is partial: a fix may not necessarily
# round-trip these exact digits — we don't want a false-positive XPASS to fail CI.
@pytest.mark.xfail(
    reason="B3: float arithmetic loses precision; Numeric(12,4) silently quantizes",
    strict=False,
)
@pytest.mark.asyncio
async def test_currency_total_preserves_input_precision(
    client: AsyncClient, editor_token: str
) -> None:
    headers = {"Authorization": f"Bearer {editor_token}"}
    r = await client.post(
        "/orders",
        headers=headers,
        json={
            "external_id": "DEC-PREC-001",
            "customer_name": "Precision test",
            "items": [{"name": "Tiny", "price": 0.123456789, "quantity": 1}],
            "status": "pending",
        },
    )
    assert r.status_code == 201
    assert r.json()["total_amount"] == 0.123456789


@pytest.mark.xfail(
    reason="B2: CSV upload always inserts; no idempotency on external_id",
    strict=True,
)
@pytest.mark.asyncio
async def test_csv_upload_idempotent_on_external_id(
    client: AsyncClient, editor_token: str
) -> None:
    headers = {"Authorization": f"Bearer {editor_token}"}
    csv_content = (
        "external_id,customer_name,item_name,price,quantity\n"
        "IDEM-1,Alice,Thing,10.00,1\n"
    )
    files = {"file": ("orders.csv", io.BytesIO(csv_content.encode()), "text/csv")}
    r1 = await client.post("/orders/upload-csv", headers=headers, files=files)
    assert r1.status_code == 201
    files2 = {"file": ("orders.csv", io.BytesIO(csv_content.encode()), "text/csv")}
    r2 = await client.post("/orders/upload-csv", headers=headers, files=files2)
    assert r2.status_code in (409, 422) or r2.json().get("created") == 0


@pytest.mark.xfail(
    reason="DELETE marks order failed instead of removing row (misleading contract)",
    strict=True,
)
@pytest.mark.asyncio
async def test_delete_order_removes_row(
    client: AsyncClient, admin_token: str
) -> None:
    headers = {"Authorization": f"Bearer {admin_token}"}
    r = await client.post(
        "/orders",
        headers=headers,
        json={
            "external_id": "RM-1",
            "customer_name": "X",
            "items": [{"name": "A", "price": 1.0, "quantity": 1}],
        },
    )
    oid = r.json()["id"]
    r2 = await client.delete(f"/orders/{oid}", headers=headers)
    assert r2.status_code == 204
    r3 = await client.get(f"/orders/{oid}", headers=headers)
    assert r3.status_code == 404
