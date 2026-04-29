from __future__ import annotations

import os

import pytest

from apps.order_processing.api.auth_client import OrderProcessingAuthClient
from core.api.base_client import BaseApiClient

pytestmark = [pytest.mark.api, pytest.mark.regression, pytest.mark.customer_order_processing]


def test_password_auth_client_works_with_env_creds(api_http_client) -> None:
    if not (os.environ.get("AUTH_USERNAME") and os.environ.get("AUTH_PASSWORD")):
        pytest.skip("AUTH_USERNAME/AUTH_PASSWORD not set")
    auth = OrderProcessingAuthClient(api_http_client)
    session = auth.login_as_env_user()
    assert session.access_token
    assert "Authorization" in session.as_header()

