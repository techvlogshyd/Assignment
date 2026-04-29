from __future__ import annotations

from playwright.sync_api import expect

from core.ui.base_page import BasePage


class OrdersPage(BasePage):
    def open(self) -> None:
        self.navigate_to_path(self.config.orders_path)

    def expect_loaded(self) -> None:
        expect(
            self.page.get_by_role("heading", name=self.config.orders_heading),
        ).to_be_visible()
        expect(self.page.get_by_role("table")).to_be_visible()
