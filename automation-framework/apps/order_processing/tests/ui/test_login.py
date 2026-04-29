"""Smoke: authenticated dashboard — delegates to Order Processing page objects."""

from __future__ import annotations

import pytest

from core.ui.customer_types import CustomerAutomationProfile
from apps.order_processing.ui.bundle import OrderProcessingPages

pytestmark = [pytest.mark.smoke, pytest.mark.sanity, pytest.mark.customer_order_processing]


def test_admin_can_sign_in_and_reach_dashboard(
    pages: OrderProcessingPages,
    customer_config: CustomerAutomationProfile,
) -> None:
    pages.login.sign_in_as(customer_config.admin_user)
    pages.dashboard.expect_loaded()
