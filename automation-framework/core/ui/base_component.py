from __future__ import annotations

from playwright.sync_api import Page


class BaseComponent:
    def __init__(self, page: Page) -> None:
        self.page = page
