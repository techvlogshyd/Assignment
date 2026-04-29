#!/usr/bin/env bash
# Run backend + frontend unit + Playwright (including intentional failing demo) and refresh artifacts under ./test-results
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="${PYTHON:-}"
if [[ -z "$PY" ]]; then
  if command -v python3 >/dev/null 2>&1; then
    PY=python3
  elif command -v python >/dev/null 2>&1; then
    PY=python
  else
    echo "run-full-suite.sh: need python3 or python on PATH (or set PYTHON=/path/to/python3)" >&2
    exit 1
  fi
fi
mkdir -p "$ROOT/test-results"
cd "$ROOT/app/backend"
# If unset, pytest uses testcontainers (needs Docker). For CI parity, export
# PYTEST_DATABASE_URL=postgresql+asyncpg://... (see .github/workflows/ci.yml).
"$PY" -m pytest tests/ \
  --junitxml="$ROOT/test-results/junit-backend.xml" \
  --cov=app \
  --cov-report=term-missing \
  --cov-report=xml:"$ROOT/test-results/coverage.xml" \
  -v
cd "$ROOT/app/frontend"
npm ci
npm run test
cd "$ROOT/e2e"
npm ci
npx playwright install chromium
npm run test:all
echo "Artifacts under $ROOT/test-results — start dashboard with: docker compose -f infra/docker-compose.yml up dashboard"
