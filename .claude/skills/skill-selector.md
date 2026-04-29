# Skill Selector (Fast Triage)

Pick the symptom, use the mapped skill, then run the first 3 commands.

| Symptom | Use this skill | First 3 commands |
|---|---|---|
| Need to add a new UI/API/LLM test quickly | `qe-add-test-suite` | `cd automation-framework` -> `python3 -m pytest apps/order_processing/tests/ui/ -v` -> `python3 -m pytest -m "not demo_intentional_fail"` |
| A test is red/flaky and root cause is unclear | `qe-debug-failure` | `cd automation-framework` -> `python3 -m pytest -v --tb=short` -> `python3 -m pytest apps/order_processing/tests/<layer>/test_<name>.py -v` |
| Dashboard numbers look stale/wrong | `qe-dashboard-triage` | `curl -X POST "http://localhost:4000/api/ingest"` -> `curl "http://localhost:4000/api/summary"` -> `curl "http://localhost:4000/api/runs?limit=5"` |
| Need to add or tune LLM eval coverage | `qe-add-llm-eval` | `cd automation-framework` -> `pip install -r requirements-llm.txt` -> `RUN_LLM_EVAL=1 python3 -m pytest -m llm_eval -v` |
| Need to add Slack/Jira/Sentry/Grafana/DB integration | `qe-add-integration` | `cd automation-framework` -> `python3 -m pytest -m "not demo_intentional_fail"` -> verify logs + env-gated skip behavior |
| Onboarding a new customer app bundle | `qe-add-customer-app` | `cd automation-framework` -> `AUTOMATION_APP=<new_slug> python3 -m pytest -m "not demo_intentional_fail" -v` -> `AUTOMATION_APP=order_processing python3 -m pytest -m "not demo_intentional_fail" -v` |
| CI changed and needs safe validation | `qe-update-ci-pipeline` | `./scripts/run-full-suite.sh` -> `python3 -m pytest automation-framework/apps/order_processing/tests/ui/ -v` -> verify outputs under `test-results/` |

## Quick notes

- Default app is `order_processing`; switch with `AUTOMATION_APP=<slug>`.
- Dashboard APIs useful during triage:
  - `/api/summary`
  - `/api/runs`
  - `/api/ai-analysis`
- Use `python3 -m pytest` consistently to avoid PATH issues.
