from __future__ import annotations

from typing import Any, Optional


def build_request_kwargs(
    *,
    params: Optional[dict[str, Any]] = None,
    json_body: Optional[dict[str, Any]] = None,
    headers: Optional[dict[str, str]] = None,
) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if params:
        out["params"] = params
    if json_body:
        out["json"] = json_body
    if headers:
        out["headers"] = headers
    return out
