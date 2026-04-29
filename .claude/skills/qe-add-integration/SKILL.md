---
name: qe-add-integration
description: >-
  Add a new external integration (Sentry, Grafana, Slack, DB, Jira, or custom)
  following the Python framework's opt-in pattern. Use when adding outbound
  service clients, notification hooks, or telemetry connections.
---

# Add an External Integration

## Pattern

Every integration in this framework follows the same contract:

1. **Env var gate** — does nothing when the env var is empty
2. **Small client wrapper** — one focused module per integration
3. **Structured logging** — logs via `core/logging/logger.py`
4. **Graceful failure** — catches errors and logs warnings, never throws

## Steps

1. **Add env var usage** in config loading:
   - Read from `.env` / process env through `automation-framework/core/config/env_reader.py`
   - Surface app defaults in `automation-framework/configs/base.yaml` when needed

```python
service_url = os.environ.get("MY_SERVICE_URL", "").strip()
```

2. **Create integration client** in `automation-framework/integrations/<name>/<name>_client.py`:

```python
import os
from core.logging.logger import get_logger

LOGGER = get_logger(__name__)

def push_to_my_service(payload: dict) -> None:
    service_url = os.environ.get("MY_SERVICE_URL", "").strip()
    if not service_url:
        LOGGER.debug("MyService skipped: MY_SERVICE_URL not set")
        return
    try:
        # call service with requests/httpx
        LOGGER.info("MyService push attempted")
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("MyService error: %s", exc)
}
```

3. **Wire call site** into the right flow:
   - API/use-case hooks: `automation-framework/core/reporting/` or `automation-framework/scripts/`
   - Test lifecycle hooks: `automation-framework/conftest.py`
   - App-specific flows: `automation-framework/apps/order_processing/...`

4. **Keep it optional in CI/local**:
   - No credentials => skip silently with debug log
   - Credentials present => execute and warn on failure, do not crash unrelated tests

5. **Document required env vars**:
   - `automation-framework/.env.example`
   - `README.md` (or app-specific docs) with setup + fallback behavior

6. **Verify**:
   - `cd automation-framework && python3 -m pytest -m "not demo_intentional_fail"`
   - run with debug logs enabled to confirm skip/success/error paths
