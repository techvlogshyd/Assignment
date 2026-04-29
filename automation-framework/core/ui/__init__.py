"""Playwright page-object kernel + UI registry."""

from core.ui.customer_types import CustomerAutomationProfile, CustomerE2EConfig, PersonaCredentials
from core.ui.registry import (
    UnknownCustomerError,
    build_app_pages,
    get_customer_config,
    get_registered_slugs,
    register_customer,
)

__all__ = [
    "CustomerAutomationProfile",
    "CustomerE2EConfig",
    "PersonaCredentials",
    "UnknownCustomerError",
    "build_app_pages",
    "get_customer_config",
    "get_registered_slugs",
    "register_customer",
]
