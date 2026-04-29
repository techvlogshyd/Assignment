---
name: qe-update-ci-pipeline
description: >-
  Update CI workflow safely for automation-framework changes. Use when adding
  new test layers, artifacts, quality gates, or dashboard ingest steps.
---

# Update CI Pipeline Safely

## Use this when

- New tests/markers are added and CI must include/exclude them
- Artifact paths changed (`test-results/` outputs, dashboard files)
- Coverage/flake gates need adjustment
- Dashboard ingest/snapshot logic needs updates

## Steps

1. **Identify impacted jobs**
   - Backend tests
   - Frontend unit tests
   - Integration/automation-framework tests
   - Insights snapshot/dashboard ingest

2. **Update commands to Python-first flow**
   - Prefer `python3 -m pytest ...`
   - Keep CI exclusion for intentional marker:
     - `-m "not demo_intentional_fail"`

3. **Keep artifact contract stable**
   - JUnit XML under `test-results/`
   - Playwright JSON/media under `test-results/`
   - Dashboard snapshot `test-results/dashboard.sqlite`

4. **Preserve quality gates**
   - Coverage threshold + baseline check
   - Flake annotations from JUnit reruns
   - Failing tests should fail job, skipped-only runs should not appear green by mistake

5. **Validate locally before pushing**

```bash
./scripts/run-full-suite.sh
```

6. **Post-change checks**
   - CI uploads all expected artifacts
   - Insights snapshot ingests successfully
   - README command table remains accurate
