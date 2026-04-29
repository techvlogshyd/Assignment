from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class EnvironmentConfig(BaseModel):
    name: str
    ui_base_url: str = Field(alias="ui_base_url")
    api_base_url: str = Field(alias="api_base_url")
    request_timeout_seconds: float = 30.0
    verify_tls: bool = True
    log_level: str = "INFO"
    llm_enabled: bool = False
    llm_model: Optional[str] = None
    llm_warning_threshold: float = 0.65
    llm_fail_threshold: float = 0.5


class FrameworkConfig(BaseModel):
    default_environment: str = "qa"
    environments: dict[str, EnvironmentConfig]
    app_defaults: dict[str, dict[str, Any]] = {}

