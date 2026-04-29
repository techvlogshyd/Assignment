"""Order Processing SPA — reference ``CustomerAutomationProfile``.

Copy this module when onboarding another app; swap paths, headings, personas, ``api_base_url``."""

from __future__ import annotations

from core.ui.customer_types import CustomerAutomationProfile, PersonaCredentials

ORDER_PROCESSING_CONFIG = CustomerAutomationProfile(
    slug="order_processing",
    login_path="/login",
    orders_path="/orders",
    dashboard_heading="Dashboard",
    orders_heading="Orders",
    admin_user=PersonaCredentials(email="admin@example.com", password="password123"),
    viewer_user=PersonaCredentials(email="viewer@example.com", password="password123"),
    api_base_url="http://127.0.0.1:8000",
)
