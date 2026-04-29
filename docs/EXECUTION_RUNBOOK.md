# Complete execution runbook — stack up/down and test flows

Use this when you need **end-to-end steps**: what to do **before**, how to **start and stop** the Docker stack, how to **run** tests and the dashboard, and what to do **after**.

All paths assume repository root:

```bash
cd Assignment   # or your clone path
```

Replace `docker compose` with `docker-compose` if your Docker install only provides the legacy CLI.

---

## 1. Prerequisites (one-time / per machine)

| Requirement | Notes |
|-------------|--------|
| **Git** | Clone your fork; `main` (or your branch) checked out. |
| **Docker Desktop** (or compatible engine) | Required for **product stack**, **dashboard** image, **Playwright** against localhost, and **testcontainers** (default local Postgres for pytest). |
| **Python 3.11+** | Backend tests and scripts. On macOS, `python` is often missing; `./scripts/run-full-suite.sh` uses **`python3`** first, then `python`. Override with **`PYTHON=/path/to/python3`**. |
| **Node.js 20+** | Frontend unit tests and Playwright package. |

**Pre-flight checks:**

```bash
docker info >/dev/null && echo "Docker OK" || echo "Start Docker"
python3 --version
node --version
```

**Backend Python deps** (host-run pytest / scripts — not inside backend container):

```bash
cd app/backend && pip install -r requirements.txt && cd ../..
```

**Optional — CI-parity Postgres on host:**  
If you do **not** want testcontainers, set `PYTEST_DATABASE_URL` to a **dedicated** database (empty or disposable), same shape as `.github/workflows/ci.yml`:

`postgresql+asyncpg://test:test@localhost:5432/orders_test`

You must run a Postgres instance and create `orders_test` yourself, or use a throwaway container on a free port. **Do not** point pytest at the same `orders_db` the dev stack uses unless you accept data clashes and resets.

---

## 2. Stack up — full application (product)

**When:** manual exploration, API docs, Playwright against real UI/API.

**From repo root:**

```bash
docker compose -f infra/docker-compose.yml up --build
```

**Foreground:** logs in terminal; **Ctrl+C** stops containers (see §7 for clean teardown).

**Detached:**

```bash
docker compose -f infra/docker-compose.yml up --build -d
```

**Wait until healthy:**

- API: http://localhost:8000/health — `curl -fsS http://localhost:8000/health`
- Swagger: http://localhost:8000/docs
- UI: http://localhost:3000

**Services involved:** `postgres`, `backend`, `frontend` (see `infra/docker-compose.yml`). Ports **5432**, **8000**, **3000**.

---

## 3. Stack up — dashboard only

**When:** you already have files under `test-results/` (JUnit, Playwright JSON, media) and want http://localhost:4000.

The dashboard image reads **`../test-results`** read-only and writes SQLite on volume **`dashboard_data`**.

**Option A — dashboard alongside an already-running compose project**

From repo root (same compose file):

```bash
docker compose -f infra/docker-compose.yml up --build dashboard
```

**Option B — detached**

```bash
docker compose -f infra/docker-compose.yml up --build -d dashboard
```

**Then:**

- Open http://localhost:4000  
- Ingest on demand: `curl -X POST http://localhost:4000/api/ingest` (same artifacts → `ingested: false`; use `?force_duplicate=true` to add another run)  
- Wipe history (demo / reset): `curl -X DELETE http://localhost:4000/api/runs`

**Port:** **4000** → container **8000**.

---

## 4. Pre-execution checklist (by activity)

| Activity | Stack | Pre-steps |
|----------|--------|-----------|
| **Use the app** | Full stack up (§2) | Docker running; wait for health URLs. |
| **Backend pytest (host)** | Optional: none if using testcontainers | Docker running for testcontainers; **or** set `PYTEST_DATABASE_URL`; `pip install -r app/backend/requirements.txt`; `mkdir -p test-results` if emitting XML. |
| **Frontend Vitest (host)** | None | `cd app/frontend && npm ci` |
| **Integration suite** | **Full stack up (§2)** | `cd automation-framework && pip install -r requirements.txt && playwright install chromium` (or `python -m playwright install --with-deps chromium` on Linux CI); override URL with `PLAYWRIGHT_BASE_URL` — use http://127.0.0.1:3000 if matching CI. |
| **Dashboard** | Dashboard service (§3) | `test-results/` populated (at least after one test run); optional `mkdir -p test-results` and keep `test-results/.gitkeep`. |
| **Full script** `./scripts/run-full-suite.sh` | Integration suite needs stack | Docker for testcontainers (or set `PYTEST_DATABASE_URL`); bring up **§2** before UI/API tests; script runs pytest → Vitest → full integration suite (`python3 -m pytest`). |

---

## 5. Execution steps — commands

### 5.1 Backend integration tests (pytest)

**Pre:** §4 backend row; artifact directory:

```bash
mkdir -p test-results
cd app/backend
```

**Run (matches README / CI artefact layout):**

```bash
python -m pytest tests/ \
  --junitxml=../../test-results/junit-backend.xml \
  --cov=app \
  --cov-report=term-missing \
  --cov-report=xml:../../test-results/coverage.xml \
  -v
```

**CI-style extras (optional on host):**

```bash
python -m pytest tests/ \
  --junitxml=../../test-results/junit-backend.xml \
  --cov=app \
  --cov-report=xml:../../test-results/coverage.xml \
  --cov-fail-under=48 \
  --reruns 2 --reruns-delay 1 \
  -v --tb=short
```

**Coverage regression gate (optional):**

```bash
python ../../scripts/check_coverage_vs_baseline.py \
  ../../test-results/coverage.xml \
  coverage_baseline.txt
```

**Flake warnings from JUnit (optional):**

```bash
python ../../scripts/flag_flakes_from_junit.py ../../test-results
```

**Post:** `cd ../..`

---

### 5.2 Frontend unit tests (Vitest)

```bash
cd app/frontend
npm ci
npm test
cd ../..
```

---

### 5.3 Integration suite (`automation-framework/`)

**Pre:** full stack **§2** healthy; install browsers once per machine under `automation-framework/`.

```bash
cd automation-framework
pip install -r requirements.txt
python -m playwright install chromium
```

**CI-equivalent (green; excludes intentional red demo):**

```bash
mkdir -p ../test-results
PLAYWRIGHT_BASE_URL=http://127.0.0.1:3000 python3 -m pytest -m "not demo_intentional_fail"
```

**Full suite including Monday-demo failure:**

```bash
PLAYWRIGHT_BASE_URL=http://127.0.0.1:3000 python3 -m pytest
```

**Post:** reports under `test-results/` (`playwright-report.json`, `playwright-html/`, `playwright-output/`, etc.). Tests live under **`tests/ui`**, **`tests/api`**, **`tests/functional`**, **`tests/llm`** with pytest markers (**`ui`**, **`api`**, **`functional`**, **`llm_eval`**); run subsets with **`python3 -m pytest -m ui`** (browser-only), **`-m api`**, etc. **`AUTOMATION_API_BASE_URL`** overrides the REST base URL from the automation profile; **`RUN_LLM_EVAL=1`** plus **`pip install -r requirements-llm.txt`** enables **`llm_eval`** cases.

---

### 5.4 One-shot full local suite (script)

**Pre:**

1. **Docker running** — pytest uses **testcontainers** when `PYTEST_DATABASE_URL` is unset; optionally set that variable to a disposable DB for CI parity (see `.github/workflows/ci.yml`).  
2. Start **full stack §2** so Playwright can reach the app.

```bash
docker compose -f infra/docker-compose.yml up --build -d
# wait for API/UI (curl loops or manual)
./scripts/run-full-suite.sh
```

**Optional — CI-shaped URL instead of testcontainers:**

```bash
docker run -d --rm --name orders-pytest-pg -p 5433:5432 \
  -e POSTGRES_USER=test -e POSTGRES_PASSWORD=test -e POSTGRES_DB=orders_test \
  postgres:15
export PYTEST_DATABASE_URL='postgresql+asyncpg://test:test@localhost:5433/orders_test'
./scripts/run-full-suite.sh
docker stop orders-pytest-pg
```

---

### 5.5 Dashboard ingest workflow

**Pre:** `test-results/` contains outputs from §5.1 / §5.3 (or downloads from CI).

```bash
docker compose -f infra/docker-compose.yml up --build dashboard
# browser: http://localhost:4000
curl -X POST http://localhost:4000/api/ingest   # after new files on disk
```

---

## 6. Post-execution (artifacts, sanity)

- Confirm `test-results/junit-backend.xml`, `test-results/coverage.xml` (if pytest with cov), Playwright outputs — as needed for dashboard or CI debugging.  
- Open HTML report: `test-results/playwright-html/index.html` (if generated).  
- Coverage gate / flake scripts: only meaningful when JUnit/coverage paths exist.

---

## 7. Stack down — stop containers

**Stop services, keep volumes** (DB and dashboard SQLite data persist):

```bash
docker compose -f infra/docker-compose.yml down
```

**Stop and remove volumes** (fresh Postgres + **wiped dashboard history**):

```bash
docker compose -f infra/docker-compose.yml down -v
```

**Post-down checklist:**

- Ports 3000, 4000, 8000, 5432 free for next run.  
- No stray one-off containers (e.g. `orders-pytest-pg`) left running: `docker ps`.

---

## 8. Pre vs post summary (quick)

| Phase | Action |
|-------|--------|
| **Pre** | Docker (and Node/Python) ready; `git` clean or branch committed as you prefer; `mkdir -p test-results` before artefact-emitting runs. |
| **Stack up** | `docker compose -f infra/docker-compose.yml up --build` (+ `-d` optional); add `dashboard` when triaging. |
| **Execute** | pytest / Vitest / Playwright / ingest per §5. |
| **Post** | Inspect `test-results/`; optional `down` or `down -v` per §7. |

---

## 9. GitHub Actions (no local stack)

**Pre:** push or PR to `main`/`master`.  
**Execution:** workflow in `.github/workflows/ci.yml` runs backend (with service Postgres), frontend unit, integration suite (`automation-framework/` job — compose on runner), then `insights-snapshot`.  
**Post:** download artifacts (`backend-test-artifacts`, `playwright-artifacts`, `dashboard-snapshot`) from the Actions run if needed.
