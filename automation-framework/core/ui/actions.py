from __future__ import annotations

from playwright.sync_api import Locator, Page, expect


class UIActions:
    def __init__(self, page: Page) -> None:
        self.page = page

    def click_when_ready(self, locator: Locator, timeout_ms: int = 10_000) -> None:
        expect(locator).to_be_visible(timeout=timeout_ms)
        expect(locator).to_be_enabled(timeout=timeout_ms)
        locator.click(timeout=timeout_ms)

    def fill_and_blur(self, locator: Locator, value: str, timeout_ms: int = 10_000) -> None:
        expect(locator).to_be_visible(timeout=timeout_ms)
        locator.fill(value, timeout=timeout_ms)
        locator.blur()

