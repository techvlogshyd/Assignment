"""Cross-layer smoke (annotate both ``functional`` and ``api`` for selection)."""

from __future__ import annotations

import pytest

from core.api.client import ApiSyncClient

# ``tests/functional/conftest.py`` applies ``functional``; add cross-layer selectors.
pytestmark = [pytest.mark.api, pytest.mark.regression, pytest.mark.customer_order_processing]


def test_backend_health_matches_registered_customer(api_http_client: ApiSyncClient) -> None:
    """Functional alias for API health — compose pipelines often gate on this."""
    assert api_http_client.get("/health").status_code == 200
