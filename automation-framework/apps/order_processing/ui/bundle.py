"""Concrete page-object graph for this customer."""

from __future__ import annotations

from dataclasses import dataclass

from playwright.sync_api import Page

from core.ui.customer_types import CustomerAutomationProfile
from apps.order_processing.ui.pages import DashboardPage, LoginPage, OrdersPage


@dataclass
class OrderProcessingPages:
    """Stable façade tests depend on — add/remove pages when this app's IA changes."""

    login: LoginPage
    dashboard: DashboardPage
    orders: OrdersPage


def build_order_processing_pages(page: Page, config: CustomerAutomationProfile) -> OrderProcessingPages:
    return OrderProcessingPages(
        login=LoginPage(page, config),
        dashboard=DashboardPage(page, config),
        orders=OrdersPage(page, config),
    )
