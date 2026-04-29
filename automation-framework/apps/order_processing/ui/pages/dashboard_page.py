from __future__ import annotations

import re

from playwright.sync_api import expect

from core.ui.base_page import BasePage


class DashboardPage(BasePage):
    def expect_loaded(self) -> None:
        expect(self.page).to_have_url(re.compile(self.config.post_login_url_regex))
        expect(
            self.page.get_by_role("heading", name=self.config.dashboard_heading),
        ).to_be_visible()
