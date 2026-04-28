#!/usr/bin/env bash
# Run backend + frontend unit + Playwright (including intentional failing demo) and refresh artifacts under ./test-results
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$ROOT/test-results"
cd "$ROOT/app/backend"
if [[ -z "${PYTEST_DATABASE_URL:-}" ]]; then
  echo "Set PYTEST_DATABASE_URL to a Postgres URL (see .github/workflows/ci.yml) or start Docker for testcontainers."
  exit 1
fi
python -m pytest tests/ \
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
