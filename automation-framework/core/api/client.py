"""Compatibility façade retaining old name ``ApiSyncClient``."""

from __future__ import annotations

import os
from typing import Optional

from core.api.base_client import BaseApiClient
from core.ui.customer_types import CustomerAutomationProfile


class ApiSyncClient(BaseApiClient):
    def __init__(self, profile: CustomerAutomationProfile, *, timeout_s: Optional[float] = None) -> None:
        raw = os.environ.get("AUTOMATION_API_BASE_URL") or profile.api_base_url
        timeout = timeout_s if timeout_s is not None else float(os.environ.get("API_HTTP_TIMEOUT", "30"))
        super().__init__(base_url=raw, timeout_s=timeout, verify_tls=True)
