from __future__ import annotations

from playwright.sync_api import BrowserContext


def add_default_context_flags(context: BrowserContext) -> None:
    context.set_default_timeout(15000)
