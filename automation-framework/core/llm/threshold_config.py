from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ThresholdConfig:
    warning_threshold: float = 0.65
    fail_threshold: float = 0.5
