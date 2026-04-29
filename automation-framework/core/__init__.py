"""Multi-layer reusable automation: UI (Playwright POM), HTTP API, optional LLM eval (DeepEval-style).

Apps plug in via ``apps/<slug>/`` + ``CustomerAutomationProfile``. Select client with ``AUTOMATION_APP`` (legacy: ``E2E_CUSTOMER``).
"""

from core.api import ApiSyncClient
from core.config.config_loader import load_framework_config
from core.config.settings import EnvironmentConfig
from core.logging.logger import configure_logging
from core.llm.deepeval_adapter import llm_eval_skip_reason, run_answer_relevancy_assert
from core.ui import (
    CustomerAutomationProfile,
    CustomerE2EConfig,
    PersonaCredentials,
    UnknownCustomerError,
    build_app_pages,
    get_customer_config,
    get_registered_slugs,
    register_customer,
)

__all__ = [
    "ApiSyncClient",
    "EnvironmentConfig",
    "CustomerAutomationProfile",
    "CustomerE2EConfig",
    "PersonaCredentials",
    "UnknownCustomerError",
    "build_app_pages",
    "get_customer_config",
    "get_registered_slugs",
    "llm_eval_skip_reason",
    "configure_logging",
    "load_framework_config",
    "register_customer",
    "run_answer_relevancy_assert",
]
