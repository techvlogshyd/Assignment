from __future__ import annotations

from playwright.sync_api import Locator, Page, expect


def wait_for_url_regex(page: Page, regex: str, timeout_ms: int = 15_000) -> None:
    expect(page).to_have_url(regex, timeout=timeout_ms)


def wait_for_visible(locator: Locator, timeout_ms: int = 10_000) -> None:
    expect(locator).to_be_visible(timeout=timeout_ms)

