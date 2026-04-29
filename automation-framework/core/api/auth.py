from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from core.api.base_client import BaseApiClient


@dataclass
class AuthSession:
    access_token: str
    token_type: str = "Bearer"

    def as_header(self) -> dict[str, str]:
        return {"Authorization": f"{self.token_type} {self.access_token}"}


class PasswordAuthClient:
    """Reusable username/password auth; app clients can wrap this."""

    def __init__(self, api: BaseApiClient, login_path: str = "/auth/login") -> None:
        self.api = api
        self.login_path = login_path

    def login(self, username: Optional[str] = None, password: Optional[str] = None) -> AuthSession:
        user = username or os.environ.get("AUTH_USERNAME")
        pwd = password or os.environ.get("AUTH_PASSWORD")
        if not user or not pwd:
            raise RuntimeError("Missing auth credentials: AUTH_USERNAME/AUTH_PASSWORD")
        response = self.api.post(self.login_path, json={"username": user, "password": pwd})
        response.raise_for_status()
        payload = response.json()
        token = payload.get("access_token")
        if not token:
            raise RuntimeError("Login response missing access_token")
        return AuthSession(access_token=token, token_type=payload.get("token_type", "Bearer"))

