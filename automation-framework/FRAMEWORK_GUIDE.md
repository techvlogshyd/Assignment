# Integration Automation Framework

Production-ready reusable framework for UI, API, and LLM testing across multiple apps/tenants.

## Layered design

- `engine/core`: config loader (yaml/json + dotenv), pydantic models, logging, assertions.
- `engine/ui`: Playwright base page + actions/waits + app registry.
- `engine/api`: reusable base HTTP client + auth adapters + app API clients.
- `engine/llm`: eval result models, evaluators, eval runner, optional DeepEval bridge.
- `apps/<slug>`: app-specific page objects, bundle, API clients, and profile config.
- `tests/ui|api|functional|llm`: strict separation of suites.

## Onboard new app

1. Copy `apps/acme_sample` → `apps/<new-slug>`.
2. Define app profile in `apps/<new-slug>/config.py`.
3. Add page objects under `apps/<new-slug>/pages`.
4. Add API clients under `apps/<new-slug>/api`.
5. Register app with `register_customer("<new-slug>", ...)`.
6. Import package in `automation-framework/conftest.py`.
7. Run with `AUTOMATION_APP=<new-slug> python3 -m pytest -m smoke`.

