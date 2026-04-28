import io

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health(client: AsyncClient) -> None:
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_login_invalid_credentials(client: AsyncClient) -> None:
    r = await client.post(
        "/auth/login",
        json={"email": "nobody@example.com", "password": "wrong"},
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient) -> None:
    import uuid

    email = f"dup-user-{uuid.uuid4().hex[:8]}@example.com"
    r1 = await client.post(
        "/auth/register",
        json={"email": email, "password": "password123", "role": "viewer"},
    )
    assert r1.status_code == 201
    r2 = await client.post(
        "/auth/register",
        json={"email": email, "password": "password123", "role": "viewer"},
    )
    assert r2.status_code == 400


@pytest.mark.asyncio
async def test_orders_list_requires_auth(client: AsyncClient) -> None:
    r = await client.get("/orders")
    # FastAPI's HTTPBearer returns 403 when no Authorization header is sent.
    # If the header is present but invalid, get_current_user raises 401.
    # The contract being asserted here is "unauthenticated callers cannot list".
    assert r.status_code in (401, 403)


@pytest.mark.asyncio
async def test_orders_crud_happy_path(
    client: AsyncClient, editor_token: str
) -> None:
    headers = {"Authorization": f"Bearer {editor_token}"}
    r = await client.post(
        "/orders",
        headers=headers,
        json={
            "external_id": "E2E-001",
            "customer_name": "Test Customer",
            "items": [{"name": "A", "price": 5.0, "quantity": 2}],
            "status": "pending",
        },
    )
    assert r.status_code == 201
    body = r.json()
    oid = body["id"]
    assert body["total_amount"] == 10.0

    r2 = await client.get(f"/orders/{oid}", headers=headers)
    assert r2.status_code == 200

    r3 = await client.patch(
        f"/orders/{oid}",
        headers=headers,
        json={"status": "processing"},
    )
    assert r3.status_code == 200
    assert r3.json()["status"] == "processing"


@pytest.mark.asyncio
async def test_viewer_cannot_create_order(
    client: AsyncClient, viewer_token: str
) -> None:
    headers = {"Authorization": f"Bearer {viewer_token}"}
    r = await client.post(
        "/orders",
        headers=headers,
        json={
            "external_id": "V-001",
            "customer_name": "V",
            "items": [{"name": "A", "price": 1.0, "quantity": 1}],
        },
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_csv_upload_creates_orders(client: AsyncClient, editor_token: str) -> None:
    headers = {"Authorization": f"Bearer {editor_token}"}
    csv_content = (
        "external_id,customer_name,item_name,price,quantity\n"
        "CSV-UP-1,Test Co,LineItem,12.50,2\n"
    )
    files = {"file": ("batch.csv", io.BytesIO(csv_content.encode()), "text/csv")}
    r = await client.post("/orders/upload-csv", headers=headers, files=files)
    assert r.status_code == 201
    assert r.json()["created"] == 1


@pytest.mark.asyncio
async def test_editor_cannot_delete_order(
    client: AsyncClient, editor_token: str
) -> None:
    headers = {"Authorization": f"Bearer {editor_token}"}
    r = await client.post(
        "/orders",
        headers=headers,
        json={
            "external_id": "DEL-001",
            "customer_name": "D",
            "items": [{"name": "A", "price": 1.0, "quantity": 1}],
        },
    )
    assert r.status_code == 201
    oid = r.json()["id"]
    r2 = await client.delete(f"/orders/{oid}", headers=headers)
    assert r2.status_code == 403


@pytest.mark.asyncio
async def test_get_order_includes_line_items(client: AsyncClient, editor_token: str) -> None:
    headers = {"Authorization": f"Bearer {editor_token}"}
    r = await client.post(
        "/orders",
        headers=headers,
        json={
            "external_id": "ITEMS-1",
            "customer_name": "Line item check",
            "items": [{"name": "A", "price": 2.0, "quantity": 3}],
            "status": "pending",
        },
    )
    oid = r.json()["id"]
    r2 = await client.get(f"/orders/{oid}", headers=headers)
    assert r2.status_code == 200
    data = r2.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["quantity"] == 3
