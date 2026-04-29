from __future__ import annotations

from typing import Optional

from core.api.auth import AuthSession


class AuthManager:
    def __init__(self) -> None:
        self._session: Optional[AuthSession] = None

    def set_session(self, session: AuthSession) -> None:
        self._session = session

    def auth_headers(self) -> dict[str, str]:
        return self._session.as_header() if self._session else {}
