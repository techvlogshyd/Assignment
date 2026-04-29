from __future__ import annotations

import re

from core.ui.base_page import BasePage
from core.ui.customer_types import PersonaCredentials


class LoginPage(BasePage):
    """Login route + credential entry — portable via ``CustomerAutomationProfile`` labels."""

    def goto(self) -> None:
        self.navigate_to_path(self.config.login_path)

    def sign_in_as(self, persona: PersonaCredentials) -> None:
        """Open login screen and submit credentials."""
        self.goto()
        self.actions.fill_and_blur(self.page.get_by_label(self.config.email_field_label), persona.email)
        self.actions.fill_and_blur(self.page.get_by_label(self.config.password_field_label), persona.password)
        self.actions.click_when_ready(self.page.get_by_role(
            "button",
            name=re.compile(self.config.sign_in_button_pattern, re.I),
        ))
