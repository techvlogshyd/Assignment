# QE Skills Quick Guide

Use this guide to choose the right skill for common work in this repository.

Need the fastest mapping? See `./skill-selector.md`.

| Skill | Use when | Primary outcomes |
|---|---|---|
| `qe-add-test-suite` | You are adding new UI/API/LLM/functional tests in `automation-framework/` | Correct folder placement, marker usage, and page-object aligned test structure |
| `qe-debug-failure` | A pytest/Playwright/LLM/dashboard run is failing or flaky | Faster root-cause isolation and a repeatable verify-fix loop |
| `qe-add-llm-eval` | You need a new LLM eval dataset, criteria, or evaluator | Consistent dataset format and runner/evaluator wiring |
| `qe-add-integration` | You are adding external service wiring (Slack/Jira/Sentry/Grafana/DB/custom) | Env-gated, optional, non-breaking integration pattern |
| `qe-dashboard-triage` | Dashboard data looks stale/wrong or you need a run-health narrative quickly | Reliable ingest checks, mismatch diagnosis, and evidence-first triage |
| `qe-add-customer-app` | You are onboarding a new app/customer into `automation-framework/apps/` | Reusable app scaffolding with selector-based execution (`AUTOMATION_APP`) |
| `qe-update-ci-pipeline` | CI must be changed for new tests/artifacts/gates | Safe workflow updates without breaking quality or artifact contracts |

## Decision flow

1. **Adding new automated coverage?** -> `qe-add-test-suite`
2. **A test/eval is red or unstable?** -> `qe-debug-failure`
3. **Expanding AI quality gates?** -> `qe-add-llm-eval`
4. **Connecting to external systems?** -> `qe-add-integration`
5. **Dashboard counts/trends look off?** -> `qe-dashboard-triage`
6. **Onboarding a new customer app?** -> `qe-add-customer-app`
7. **Changing CI behavior or artifacts?** -> `qe-update-ci-pipeline`

## Notes for this repo

- Framework root: `automation-framework/`
- Default app bundle: `apps/order_processing/`
- Run tests with `python3 -m pytest` (not `npm`/TypeScript flow)
- Dashboard ingest/triage is part of failure debugging:
  - `POST /api/ingest`
  - inspect `/api/summary` and `/api/ai-analysis`
