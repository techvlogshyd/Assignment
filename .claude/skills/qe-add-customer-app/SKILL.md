---
name: qe-add-customer-app
description: >-
  Onboard a new customer/app bundle into the automation framework. Use when
  cloning order_processing patterns for another app with minimal duplication.
---

# Add a New Customer App

## Goal

Create a new app under `automation-framework/apps/<customer_slug>/` that plugs
into shared `core/`, `shared/fixtures/`, and CI without breaking existing apps.

## Steps

1. **Create app structure**
   - `api/`, `config/`, `ui/`, `llm/`, `tests/`
   - Mirror the shape used by `apps/order_processing/`

2. **Define customer config**
   - Add `config/app_config.py` with routes/headings/personas/base URLs
   - Ensure it is importable via `apps.<slug>` package

3. **Register UI bundle**
   - Add page objects in `ui/pages/`
   - Export from `ui/pages/__init__.py`
   - Wire bundle in `ui/bundle.py` so shared `pages` fixture can load it

4. **Add baseline tests**
   - UI smoke: login + one core workflow
   - API smoke: auth + one business contract
   - Optional LLM eval dataset/tests for app-specific prompts

5. **Run by app selector**

```bash
cd automation-framework
AUTOMATION_APP=<customer_slug> python3 -m pytest -m "not demo_intentional_fail" -v
```

6. **Document and CI**
   - Update onboarding docs if conventions changed
   - Add CI matrix/parallel job only if required; otherwise reuse existing gates

## Done criteria

- New app runs with `AUTOMATION_APP=<slug>`
- Existing `order_processing` tests still pass
- Dashboard can ingest artifacts from the new app flow
