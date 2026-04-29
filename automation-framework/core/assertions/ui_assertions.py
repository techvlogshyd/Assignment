from __future__ import annotations

from playwright.sync_api import Locator, expect


def assert_visible(locator: Locator) -> None:
    expect(locator).to_be_visible()
