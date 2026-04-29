"""Orders list — viewer persona via shared fixtures."""

from __future__ import annotations

import pytest

from core.ui.customer_types import CustomerAutomationProfile
from apps.order_processing.ui.bundle import OrderProcessingPages

pytestmark = [pytest.mark.smoke, pytest.mark.regression, pytest.mark.customer_order_processing]


@pytest.fixture
def logged_in_viewer(
    pages: OrderProcessingPages,
    customer_config: CustomerAutomationProfile,
) -> OrderProcessingPages:
    pages.login.sign_in_as(customer_config.viewer_user)
    pages.dashboard.expect_loaded()
    return pages


def test_orders_list_loads(logged_in_viewer: OrderProcessingPages) -> None:
    logged_in_viewer.orders.open()
    logged_in_viewer.orders.expect_loaded()
