#!/usr/bin/env bash
# Run backend + frontend unit + automation tests and refresh artifacts under ./test-results.
# By default this mirrors CI (excludes demo_intentional_fail). Set INCLUDE_DEMO_FAIL=1 to include it.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
STACK_FILE="$ROOT/infra/docker-compose.yml"
STACK_STARTED=0
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

cleanup_stack() {
  # Default behavior: keep stack up for post-run dashboard review.
  # Set AUTO_STACK_DOWN=1 to tear down automatically.
  if [[ "${AUTO_STACK_DOWN:-0}" != "1" ]]; then
    return
  fi
  if [[ "$STACK_STARTED" != "1" ]]; then
    return
  fi
  echo "Bringing stack down..."
  if [[ "${STACK_DOWN_VOLUMES:-0}" == "1" ]]; then
    docker compose -f "$STACK_FILE" down -v || true
  else
    docker compose -f "$STACK_FILE" down || true
  fi
}

trap cleanup_stack EXIT
mkdir -p "$ROOT/test-results"

# Clear stale automation-layer artifacts so the dashboard never re-ingests a
# previous run's failures. Backend coverage/junit are rewritten unconditionally
# below, so we only purge the automation outputs here.
rm -f "$ROOT/test-results/junit-automation.xml" \
      "$ROOT/test-results/playwright-report.json"
rm -rf "$ROOT/test-results/playwright-output" \
       "$ROOT/test-results/playwright-html" \
       "$ROOT/test-results/allure-results"

# Bring up the stack first so backend tests can use localhost DB URLs too.
cd "$ROOT"
docker compose -f "$STACK_FILE" up -d --build
STACK_STARTED=1

# Wait for API/UI/db readiness (best-effort 60s).
for _ in $(seq 1 30); do
  if curl -fsS "http://127.0.0.1:8000/health" >/dev/null 2>&1 && curl -fsS "http://127.0.0.1:3000" >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

cd "$ROOT/app/backend"
# Ensure backend deps (incl. DB drivers like psycopg2/alembic) exist for migrations/tests.
"$PY" -m pip install -r requirements.txt
# Guard against a sync SQLAlchemy URL leaking from shell history.
if [[ "${PYTEST_DATABASE_URL:-}" == *"+psycopg2://"* ]]; then
  export PYTEST_DATABASE_URL="${PYTEST_DATABASE_URL/+psycopg2/+asyncpg}"
fi
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

cd "$ROOT/automation-framework"
"$PY" -m pip install -r requirements.txt
"$PY" -m playwright install chromium
if [[ "${INCLUDE_DEMO_FAIL:-0}" == "1" ]]; then
  "$PY" -m pytest || true
else
  "$PY" -m pytest -m "not demo_intentional_fail"
fi

# Best-effort dashboard ingest so latest artifacts are visible immediately.
if [[ "${AUTO_DASHBOARD_INGEST:-1}" == "1" ]]; then
  curl -fsS -X POST "http://127.0.0.1:4000/api/ingest" >/dev/null || true
fi
echo "Artifacts under $ROOT/test-results — start dashboard with: docker compose -f infra/docker-compose.yml up dashboard"
