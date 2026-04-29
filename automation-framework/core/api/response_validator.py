from __future__ import annotations

from typing import Any


def validate_json_fields(payload: dict[str, Any], required_fields: list[str]) -> None:
    missing = [k for k in required_fields if k not in payload]
    if missing:
        raise AssertionError(f"Missing required response fields: {missing}")
