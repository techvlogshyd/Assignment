---
name: qe-debug-failure
description: >-
  Systematically debug a failing test or LLM eval in the QE framework. Use when
  a test fails, an eval score drops, CI is red, or investigating flaky tests.
---

# Debug a Test/Eval Failure

## Step 1: Identify the failure type

| Symptom | Likely cause | Start here |
|---|---|---|
| Playwright spec fails | UI change or app bug | Check page object selectors |
| API spec fails | Endpoint change or auth issue | Check `apps/order_processing/api/` + env vars |
| LLM eval fails | Model regression or bad criteria | Check `apps/order_processing/llm/datasets/` + `core/llm/evaluators/` |
| Evals skipped | LLM gating disabled | Check `RUN_LLM_EVAL` and `requirements-llm.txt` |
| Import/runtime fails | Path/env mismatch | Run targeted `python3 -m pytest` command |

## Step 2: Read the structured logs

Logs and reports to inspect:
- pytest stdout/stderr + `test-results/`
- `test-results/playwright-report.json`
- dashboard API (`/api/summary`, `/api/runs`)

```bash
cd automation-framework
python3 -m pytest apps/order_processing/tests/ui/ -v --tb=short
python3 -m pytest apps/order_processing/tests/api/ -v --tb=short
RUN_LLM_EVAL=1 python3 -m pytest -m llm_eval -v
```

## Step 3: Reproduce locally

```bash
# Single UI test
cd automation-framework
python3 -m pytest apps/order_processing/tests/ui/test_login.py -v

# Single API test
python3 -m pytest apps/order_processing/tests/api/test_orders_api.py -v
```

## Step 4: Check the layers

1. **Selector issue?** -> Update `apps/order_processing/ui/pages/*.py`, rerun UI test
2. **Fixture issue?** -> Check `automation-framework/conftest.py` and `shared/fixtures/`
3. **Env issue?** -> Validate `.env`, `configs/base.yaml`, and CI secrets
4. **Eval issue?** -> Validate criteria/dataset format in `apps/order_processing/llm/datasets/`
5. **Dashboard mismatch?** -> Re-ingest with `POST /api/ingest` and verify `playwright-report.json`

## Step 5: Verify the fix

```bash
cd automation-framework
python3 -m pytest -m "not demo_intentional_fail" -v
```
