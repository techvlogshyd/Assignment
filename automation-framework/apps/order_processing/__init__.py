"""Reference UI customer — registers automatically on import."""

from __future__ import annotations

from core.ui.registry import register_customer
from apps.order_processing.ui.bundle import OrderProcessingPages, build_order_processing_pages
from apps.order_processing.config.app_config import ORDER_PROCESSING_CONFIG

register_customer(
    "order_processing",
    ORDER_PROCESSING_CONFIG,
    build_order_processing_pages,
)

__all__ = [
    "ORDER_PROCESSING_CONFIG",
    "OrderProcessingPages",
    "build_order_processing_pages",
]
