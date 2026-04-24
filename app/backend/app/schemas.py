import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, EmailStr

from app.models import OrderStatus, UserRole


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    role: UserRole = UserRole.viewer


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    role: UserRole
    created_at: datetime

    model_config = {"from_attributes": True}


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class OrderCreate(BaseModel):
    external_id: str
    customer_name: str
    items: list[dict[str, Any]]
    status: OrderStatus = OrderStatus.pending


class OrderUpdate(BaseModel):
    status: Optional[OrderStatus] = None
    customer_name: Optional[str] = None


class OrderResponse(BaseModel):
    id: uuid.UUID
    external_id: str
    customer_name: str
    items: list[dict[str, Any]]
    total_amount: float
    status: OrderStatus
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PaginatedOrders(BaseModel):
    items: list[OrderResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class OrderStats(BaseModel):
    total_orders: int
    by_status: dict[str, int]
    total_amount: float
