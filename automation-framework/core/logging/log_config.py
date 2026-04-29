from __future__ import annotations

import os


def get_default_log_level() -> str:
    return os.environ.get("AUTOMATION_LOG_LEVEL", "INFO")
