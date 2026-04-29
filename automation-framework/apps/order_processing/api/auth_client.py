from __future__ import annotations

from core.api.auth import PasswordAuthClient
from core.api.base_client import BaseApiClient


class OrderProcessingAuthClient:
    def __init__(self, base_api: BaseApiClient) -> None:
        self._delegate = PasswordAuthClient(base_api, login_path="/auth/login")

    def login_as_env_user(self):
        return self._delegate.login()

