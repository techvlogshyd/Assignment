"""Plug-and-play registry: ``AUTOMATION_APP`` slug → frozen profile + UI page bundle factory."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from playwright.sync_api import Page

from core.ui.customer_types import CustomerAutomationProfile

BuildPagesFn = Callable[[Page, CustomerAutomationProfile], Any]


class UnknownCustomerError(LookupError):
    """Raised when ``AUTOMATION_APP`` / slug env does not match a registered app."""

    def __init__(self, slug: str, known: tuple[str, ...]) -> None:
        super().__init__(f"Unknown integration app {slug!r}. Registered: {known}")


_REGISTRY: dict[str, tuple[CustomerAutomationProfile, BuildPagesFn]] = {}


def register_customer(slug: str, config: CustomerAutomationProfile, build_pages: BuildPagesFn) -> None:
    """Called once per customer package at import time."""
    if slug in _REGISTRY:
        raise ValueError(f"Duplicate registration for slug {slug!r}")
    if config.slug != slug:
        raise ValueError(f"Config.slug {config.slug!r} must match registration slug {slug!r}")
    _REGISTRY[slug] = (config, build_pages)


def resolve_customer(slug: str) -> tuple[CustomerAutomationProfile, BuildPagesFn]:
    if slug not in _REGISTRY:
        raise UnknownCustomerError(slug, get_registered_slugs())
    return _REGISTRY[slug]


def get_customer_config(slug: str) -> CustomerAutomationProfile:
    cfg, _ = resolve_customer(slug)
    return cfg


def build_app_pages(page: Page, slug: str) -> Any:
    """Instantiate the active customer's page bundle (POM graph)."""
    cfg, factory = resolve_customer(slug)
    return factory(page, cfg)


def get_registered_slugs() -> tuple[str, ...]:
    return tuple(sorted(_REGISTRY.keys()))
