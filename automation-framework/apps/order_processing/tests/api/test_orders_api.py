"""Contract smoke against active app API base URL."""

from __future__ import annotations

import pytest

from core.api.client import ApiSyncClient
from core.assertions.api_assertions import assert_status

pytestmark = [pytest.mark.smoke, pytest.mark.sanity, pytest.mark.customer_order_processing]


def test_health_returns_ok(api_http_client: ApiSyncClient) -> None:
    response = api_http_client.get("/health")
    assert_status(response.status_code, 200, context=f"url={api_http_client.base_url}/health")
