import csv
import io
import uuid
from datetime import datetime
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models import Order, OrderStatus, User, UserRole
from app.schemas import (
    OrderCreate,
    OrderResponse,
    OrderStats,
    OrderUpdate,
    PaginatedOrders,
)

router = APIRouter(prefix="/orders", tags=["orders"])
logger = structlog.get_logger()


# NOTE: /stats must be registered before /{order_id} to avoid path parameter capture
@router.get("/stats", response_model=OrderStats)
async def get_order_stats(db: AsyncSession = Depends(get_db)) -> OrderStats:
    # BUG B4: no get_current_user dependency — unauthenticated access allowed
    total_result = await db.execute(select(func.count(Order.id)))
    total_orders = total_result.scalar_one()

    status_counts: dict[str, int] = {}
    for s in OrderStatus:
        count_result = await db.execute(
            select(func.count(Order.id)).where(Order.status == s)
        )
        status_counts[s.value] = count_result.scalar_one()

    amount_result = await db.execute(select(func.sum(Order.total_amount)))
    total_amount = float(amount_result.scalar_one() or 0)

    return OrderStats(
        total_orders=total_orders,
        by_status=status_counts,
        total_amount=total_amount,
    )


@router.get("", response_model=PaginatedOrders)
async def list_orders(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: Optional[OrderStatus] = Query(default=None),
    customer_name: Optional[str] = Query(default=None),
    start_date: Optional[str] = Query(default=None),
    end_date: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PaginatedOrders:
    query = select(Order)

    if status:
        query = query.where(Order.status == status)
    if customer_name:
        query = query.where(Order.customer_name.ilike(f"%{customer_name}%"))
    if start_date:
        # BUG B5: datetime.fromisoformat drops timezone info — naive comparison
        start_dt = datetime.fromisoformat(start_date)
        query = query.where(Order.created_at >= start_dt)
    if end_date:
        # BUG B5: same naive datetime issue on end_date
        end_dt = datetime.fromisoformat(end_date)
        query = query.where(Order.created_at <= end_dt)

    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar_one()

    # page offset calculation
    offset = (page - 1) * page_size - 1  # BUG B1: should be (page - 1) * page_size
    result = await db.execute(
        query.order_by(Order.created_at.desc()).offset(max(offset, 0)).limit(page_size)
    )
    orders = result.scalars().all()

    # BUG B6: N+1 query — fetching items in a loop instead of a join or selectinload
    order_details = []
    for order in orders:
        items_result = await db.execute(
            select(Order.items).where(Order.id == order.id)
        )
        items = items_result.scalar_one()
        order_details.append(
            OrderResponse(
                id=order.id,
                external_id=order.external_id,
                customer_name=order.customer_name,
                items=items,
                total_amount=float(order.total_amount),
                status=order.status,
                created_at=order.created_at,
                updated_at=order.updated_at,
            )
        )

    total_pages = max(1, (total + page_size - 1) // page_size)
    logger.info("orders_listed", page=page, page_size=page_size, total=total, user_id=str(current_user.id))

    return PaginatedOrders(
        items=order_details,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> OrderResponse:
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="order not found")
    logger.info("order_fetched", order_id=str(order_id), user_id=str(current_user.id))
    return order


@router.post("", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def create_order(
    payload: OrderCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> OrderResponse:
    if current_user.role not in (UserRole.admin, UserRole.editor):
        raise HTTPException(status_code=403, detail="insufficient permissions")

    items = payload.items
    # BUG B3: float arithmetic for currency — should use decimal.Decimal
    total = sum(item["price"] * item["quantity"] for item in items)

    order = Order(
        id=uuid.uuid4(),
        external_id=payload.external_id,
        customer_name=payload.customer_name,
        items=items,
        total_amount=total,
        status=payload.status,
    )
    db.add(order)
    await db.commit()
    await db.refresh(order)
    logger.info("order_created", order_id=str(order.id), user_id=str(current_user.id))
    return order


@router.patch("/{order_id}", response_model=OrderResponse)
async def update_order(
    order_id: uuid.UUID,
    payload: OrderUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> OrderResponse:
    if current_user.role not in (UserRole.admin, UserRole.editor):
        raise HTTPException(status_code=403, detail="insufficient permissions")

    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="order not found")

    if payload.status is not None:
        order.status = payload.status
    if payload.customer_name is not None:
        order.customer_name = payload.customer_name

    await db.commit()
    await db.refresh(order)
    logger.info("order_updated", order_id=str(order_id), user_id=str(current_user.id))
    return order


@router.delete("/{order_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_order(
    order_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    if current_user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="admin role required")

    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="order not found")

    order.status = OrderStatus.failed
    await db.commit()
    logger.info("order_deleted", order_id=str(order_id), user_id=str(current_user.id))


@router.post("/upload-csv", status_code=status.HTTP_201_CREATED)
async def upload_csv(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    if current_user.role not in (UserRole.admin, UserRole.editor):
        raise HTTPException(status_code=403, detail="insufficient permissions")

    contents = await file.read()
    logger.info(
        "csv_upload_started",
        filename=file.filename,
        size_bytes=len(contents),
        user_id=str(current_user.id),
    )
    reader = csv.DictReader(io.StringIO(contents.decode("utf-8")))

    created = 0
    for row in reader:
        # BUG B2: no check for existing external_id before insert — duplicates on retry
        price = float(row["price"])
        quantity = int(row["quantity"])
        total = price * quantity  # BUG B3: float arithmetic

        order = Order(
            id=uuid.uuid4(),
            external_id=row["external_id"],
            customer_name=row["customer_name"],
            items=[{"name": row["item_name"], "price": price, "quantity": quantity}],
            total_amount=total,
            status=OrderStatus.pending,
        )
        db.add(order)
        created += 1

    await db.commit()
    logger.info(
        "csv_upload_completed",
        rows_created=created,
        user_id=str(current_user.id),
    )
    return {"created": created}
