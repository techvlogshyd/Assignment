from __future__ import annotations

from typing import Any


def assert_status(actual: int, expected: int, context: str = "") -> None:
    if actual != expected:
        raise AssertionError(f"Expected HTTP {expected}, got {actual}. {context}".strip())


def assert_contains_subset(payload: dict[str, Any], subset: dict[str, Any]) -> None:
    for k, v in subset.items():
        if payload.get(k) != v:
            raise AssertionError(f"Payload mismatch for key '{k}': expected {v!r}, got {payload.get(k)!r}")

