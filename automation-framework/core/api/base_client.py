from __future__ import annotations

import logging
from typing import Any

import requests

LOGGER = logging.getLogger(__name__)


class BaseApiClient:
    def __init__(self, base_url: str, *, timeout_s: float = 30.0, verify_tls: bool = True) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s
        self.verify_tls = verify_tls
        self.session = requests.Session()

    def request(self, method: str, path: str, **kwargs: Any) -> requests.Response:
        url = f"{self.base_url}{path}"
        kwargs.setdefault("timeout", self.timeout_s)
        kwargs.setdefault("verify", self.verify_tls)
        LOGGER.debug("API %s %s", method, url)
        response = self.session.request(method=method.upper(), url=url, **kwargs)
        LOGGER.debug("API response status=%s url=%s", response.status_code, url)
        return response

    def get(self, path: str, **kwargs: Any) -> requests.Response:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs: Any) -> requests.Response:
        return self.request("POST", path, **kwargs)

    def close(self) -> None:
        self.session.close()

