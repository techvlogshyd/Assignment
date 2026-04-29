"""Thin wrappers shared by all customer page objects."""

from __future__ import annotations

from playwright.sync_api import Page

from core.ui.customer_types import CustomerAutomationProfile
from core.ui.actions import UIActions


class BasePage:
    """Every page object receives the Playwright page plus frozen customer profile."""

    def __init__(self, page: Page, config: CustomerAutomationProfile) -> None:
        self._page = page
        self._config = config
        self.actions = UIActions(page)

    @property
    def page(self) -> Page:
        return self._page

    @property
    def config(self) -> CustomerAutomationProfile:
        return self._config

    def navigate_to_path(self, path: str) -> None:
        """Navigate relative to Playwright ``base_url`` (pytest-playwright)."""
        self._page.goto(path)
