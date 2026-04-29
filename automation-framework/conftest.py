"""Automation pytest config: env loader, app registry, UI/API/LLM fixtures, Playwright JSON reporter."""

from __future__ import annotations

import json
import importlib
import logging
import os
from pathlib import Path

import pytest

from core.config.config_loader import load_framework_config
from core.logging.logger import configure_logging
from core.api.client import ApiSyncClient
from core.ui.registry import UnknownCustomerError, build_app_pages, get_customer_config

FRAMEWORK_ROOT = Path(__file__).resolve().parent
REPO_ROOT = FRAMEWORK_ROOT.parent
RESULTS_DIR = REPO_ROOT / "test-results"
PW_JSON = RESULTS_DIR / "playwright-report.json"
CONFIG_PATH = FRAMEWORK_ROOT / "configs" / "base.yaml"

# Final call-phase result per test nodeid (reruns overwrite earlier attempts).
_SESSION_REPORTS: dict[str, dict] = {}
LOGGER = logging.getLogger(__name__)


def _default_base_url() -> str:
    env_override = os.environ.get("PLAYWRIGHT_BASE_URL")
    if env_override:
        return env_override
    _, env_cfg = load_framework_config(CONFIG_PATH)
    return env_cfg.ui_base_url


@pytest.fixture(scope="session")
def framework_config():
    cfg, _ = load_framework_config(CONFIG_PATH)
    return cfg


@pytest.fixture(scope="session")
def env_config():
    _, env_cfg = load_framework_config(CONFIG_PATH)
    return env_cfg


@pytest.fixture(scope="session")
def customer_slug(framework_config) -> str:
    """Which app bundle to load — mirror ``apps/<slug>/`` packages."""
    return os.environ.get("AUTOMATION_APP") or os.environ.get("INTEGRATION_APP") or os.environ.get("E2E_CUSTOMER", "order_processing")


@pytest.fixture(scope="session")
def customer_config(customer_slug: str):
    """Frozen profile for UI routes, API base URL, personas (single registry slug)."""
    module_name = f"apps.{customer_slug.replace('-', '_')}"
    try:
        importlib.import_module(module_name)
    except ModuleNotFoundError:
        LOGGER.debug("No auto-import module for slug '%s' (%s)", customer_slug, module_name)
    try:
        return get_customer_config(customer_slug)
    except UnknownCustomerError as exc:
        pytest.fail(str(exc))


@pytest.fixture
def pages(page, customer_slug: str):
    """Playwright page-object graph for ``customer_slug``."""
    return build_app_pages(page, customer_slug)


@pytest.fixture(scope="session")
def api_http_client(customer_config):
    """REST client scoped to ``customer_config.api_base_url`` (override with AUTOMATION_API_BASE_URL)."""
    client = ApiSyncClient(customer_config)
    yield client
    client.close()


@pytest.fixture(scope="session")
def base_url() -> str:
    return _default_base_url()


def pytest_sessionstart(session: pytest.Session) -> None:
    if getattr(session.config, "workerinput", None):
        return
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "playwright-html").mkdir(parents=True, exist_ok=True)
    configure_logging(RESULTS_DIR / "logs")
    _ = session
    _SESSION_REPORTS.clear()


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call):  # noqa: ANN001
    outcome = yield
    rep = outcome.get_result()
    if getattr(item.config, "workerinput", None):
        return
    if rep.when != "call":
        return
    duration_ms = float(getattr(rep, "duration", 0.0) or 0.0) * 1000.0
    msg = ""
    if rep.failed:
        msg = str(rep.longrepr)[:1500]
        page = item.funcargs.get("page")
        if page:
            screenshot_path = RESULTS_DIR / "playwright-output" / f"{item.name}-failure.png"
            screenshot_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                page.screenshot(path=str(screenshot_path), full_page=True)
                try:
                    import allure  # type: ignore

                    allure.attach.file(str(screenshot_path), name=f"{item.name}-failure", attachment_type=allure.attachment_type.PNG)
                except Exception:
                    LOGGER.debug("allure attach unavailable for screenshot")
            except Exception as exc:  # noqa: BLE001
                LOGGER.warning("Failed to capture screenshot for %s: %s", item.name, exc)
    _SESSION_REPORTS[item.nodeid] = {
        "nodeid": item.nodeid,
        "title": item.name,
        "outcome": rep.outcome,
        "duration_ms": duration_ms,
        "message": msg,
    }


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    if getattr(session.config, "workerinput", None):
        return
    _ = session, exitstatus
    suites = [
        {
            "title": "tests",
            "specs": [],
            "suites": [],
        }
    ]
    for r in _SESSION_REPORTS.values():
        outcome = r["outcome"]
        if outcome == "passed":
            status = "passed"
        elif outcome == "skipped":
            status = "skipped"
        else:
            status = "failed"
        err: dict[str, str] = {}
        if status == "failed":
            err = {"message": r["message"]}
        spec = {
            "title": r["title"],
            "tests": [
                {
                    "results": [
                        {
                            "status": status,
                            "duration": r["duration_ms"],
                            "attachments": [],
                            "error": err,
                        }
                    ]
                }
            ],
        }
        suites[0]["specs"].append(spec)

    PW_JSON.write_text(json.dumps({"suites": suites}, indent=2), encoding="utf-8")
