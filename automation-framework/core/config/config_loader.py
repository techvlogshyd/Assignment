from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv
from pydantic import ValidationError
import yaml

from core.config.settings import EnvironmentConfig, FrameworkConfig


class ConfigError(RuntimeError):
    pass


def _read_file(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ConfigError(f"Config file not found: {path}")
    text = path.read_text(encoding="utf-8")
    if path.suffix in (".yaml", ".yml"):
        return yaml.safe_load(text) or {}
    if path.suffix == ".json":
        return json.loads(text)
    raise ConfigError(f"Unsupported config format: {path.suffix}")


def load_framework_config(config_path: Path, env_name: Optional[str] = None) -> tuple[FrameworkConfig, EnvironmentConfig]:
    load_dotenv(override=False)
    raw = _read_file(config_path)
    try:
        cfg = FrameworkConfig.model_validate(raw)
    except ValidationError as exc:
        raise ConfigError(f"Invalid framework config: {exc}") from exc

    selected = env_name or os.environ.get("AUTOMATION_ENV") or os.environ.get("INTEGRATION_ENV") or cfg.default_environment
    if selected not in cfg.environments:
        raise ConfigError(f"Unknown AUTOMATION_ENV '{selected}'. Available: {tuple(cfg.environments.keys())}")
    return cfg, cfg.environments[selected]

