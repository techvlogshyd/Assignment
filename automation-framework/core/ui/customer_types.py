"""Unified per-customer profile: UI routes/copy plus API base URL for layered tests."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class PersonaCredentials:
    """Named user/password pair for UI login."""

    email: str
    password: str


@dataclass(frozen=True)
class CustomerAutomationProfile:
    """Single frozen profile shared by UI page objects, API clients, and optional LLM settings.

    Copy ``apps/order_processing/config.py`` when onboarding another app; register once per slug.
    """

    slug: str

    # --- Browser / SPA (pytest-playwright ``base_url`` is separate — PLAYWRIGHT_BASE_URL)
    login_path: str
    orders_path: str
    dashboard_heading: str
    orders_heading: str
    admin_user: PersonaCredentials
    viewer_user: PersonaCredentials

    email_field_label: str = "Email"
    password_field_label: str = "Password"
    sign_in_button_pattern: str = r"sign in"
    post_login_url_regex: str = r"/$"

    # --- REST / GraphQL gateway used by ``tests/api`` and functional flows
    api_base_url: str = "http://127.0.0.1:8000"

    # --- Optional DeepEval / LLM harness (override per customer if needed)
    llm_eval_default_model: Optional[str] = None


# Backwards-compatible alias used in older snippets
CustomerE2EConfig = CustomerAutomationProfile
