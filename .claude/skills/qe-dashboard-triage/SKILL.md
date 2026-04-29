---
name: qe-dashboard-triage
description: >-
  Triage test health using the dashboard and artifacts. Use when counts look
  wrong, trends are stale, or you need quick Monday-morning failure insights.
---

# Triage via Dashboard

## Use this when

- Dashboard numbers do not match local test output
- Latest run is not visible
- Playwright/pytest failure counts look inflated
- You need a quick diagnosis summary from recent runs

## Steps

1. **Confirm artifacts were produced**
   - `test-results/junit-*.xml`
   - `test-results/playwright-report.json`
   - `test-results/playwright-output/` (media)

2. **Ingest current artifacts**

```bash
curl -X POST "http://localhost:4000/api/ingest"
```

If artifacts are unchanged and you still need another run row for demo/trend:

```bash
curl -X POST "http://localhost:4000/api/ingest?force_duplicate=true"
```

3. **Validate API views**

```bash
curl "http://localhost:4000/api/summary"
curl "http://localhost:4000/api/runs?limit=5"
curl "http://localhost:4000/api/ai-analysis"
```

4. **Cross-check mismatches**

- Retry inflation: ensure final-outcome counting logic is used for Playwright retries
- Stale data: verify `playwright-report.json` mtime/content changed
- Wrong project filter: check `?project=<name>` and `DASHBOARD_PROJECT`

5. **Capture triage output**

- List newly failing tests first
- Include flaky tests and recent pass-rate direction
- Link evidence (screenshot/video/trace) from `/artifacts/`
