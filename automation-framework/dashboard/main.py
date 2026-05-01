"""Test insights dashboard.

Ingests pytest JUnit XML and Playwright JSON from ARTIFACTS_ROOT into a SQLite
run history (DASHBOARD_DB), then answers the three questions from the brief:
  1) what is failing right now,
  2) is it newly failing or chronically flaky,
  3) trends over the last N runs (pass rate / flake rate / duration).

Failure cards link inline to Playwright videos / screenshots / traces served
under /artifacts/, so an engineer can triage without leaving the dashboard.

The JUnit and Playwright parsing primitives live in ``qe_toolkit`` so that a
second customer solution gets the same reporting without forking this file.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

# When running inside the Docker image, qe_toolkit is COPY'd next to main.py.
# When running locally from repo root, it's importable via the package layout.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from qe_toolkit.junit import parse_junit_files  # noqa: E402
from qe_toolkit.playwright import parse_playwright_json  # noqa: E402
from qe_toolkit.text import strip_ansi  # noqa: E402

# Default to repo-root test-results (not CWD) so `uvicorn` from this package dir works.
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_DEFAULT_ARTIFACTS = _REPO_ROOT / "test-results"
ARTIFACTS_ROOT = Path(
    os.environ.get("ARTIFACTS_ROOT", str(_DEFAULT_ARTIFACTS))
).resolve()
def _resolve_ai_report_path() -> Path:
    """Locate the decision journal across local-dev and container layouts.

    - In local dev, the journal lives at <repo_root>/AI_DECISION_JOURNAL.md and
      `_REPO_ROOT` resolves to the repo root from `parent.parent.parent`.
    - In the Docker image, the Dockerfile copies the journal next to `main.py`
      at /app/AI_DECISION_JOURNAL.md, so `_REPO_ROOT` (= /) does not contain it.

    The explicit `AI_ANALYSIS_REPORT` env var always wins. Otherwise we pick
    the first candidate that exists; if none exist we fall back to the local-dev
    path so the "not found" message points at a sensible location.
    """
    override = os.environ.get("AI_ANALYSIS_REPORT")
    if override:
        return Path(override).resolve()

    candidates = [
        Path(__file__).resolve().parent / "AI_DECISION_JOURNAL.md",  # container layout
        _REPO_ROOT / "AI_DECISION_JOURNAL.md",                        # local dev layout
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    return candidates[-1].resolve()


AI_REPORT_PATH = _resolve_ai_report_path()
ARTIFACTS_ROOT.mkdir(parents=True, exist_ok=True)
DB_PATH = Path(os.environ.get("DASHBOARD_DB", str(ARTIFACTS_ROOT / "dashboard.sqlite"))).resolve()
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

PROJECT = os.environ.get("DASHBOARD_PROJECT", "default")
FLAKE_WINDOW = int(os.environ.get("FLAKE_WINDOW", "10"))
TREND_WINDOW = int(os.environ.get("TREND_WINDOW", "20"))


# ---------------------------------------------------------------------------
# SQLite schema and helpers (multi-project ready: every row has a `project`)
# ---------------------------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project TEXT NOT NULL DEFAULT 'default',
  ts TEXT NOT NULL,
  content_hash TEXT NOT NULL,
  junit_total INTEGER NOT NULL DEFAULT 0,
  junit_passed INTEGER NOT NULL DEFAULT 0,
  junit_failed INTEGER NOT NULL DEFAULT 0,
  junit_errors INTEGER NOT NULL DEFAULT 0,
  junit_skipped INTEGER NOT NULL DEFAULT 0,
  pw_total INTEGER NOT NULL DEFAULT 0,
  pw_passed INTEGER NOT NULL DEFAULT 0,
  pw_failed INTEGER NOT NULL DEFAULT 0,
  pw_skipped INTEGER NOT NULL DEFAULT 0,
  duration_ms REAL NOT NULL DEFAULT 0,
  UNIQUE(project, content_hash)
);

CREATE TABLE IF NOT EXISTS outcomes (
  run_id INTEGER NOT NULL,
  project TEXT NOT NULL DEFAULT 'default',
  layer TEXT NOT NULL,
  suite TEXT,
  name TEXT NOT NULL,
  status TEXT NOT NULL,
  duration_ms REAL,
  message TEXT,
  attachments TEXT,
  FOREIGN KEY(run_id) REFERENCES runs(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_outcomes_run ON outcomes(run_id);
CREATE INDEX IF NOT EXISTS idx_outcomes_test ON outcomes(project, layer, suite, name);
"""


def db_connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    _migrate_in_place(conn)
    return conn


def _migrate_in_place(conn: sqlite3.Connection) -> None:
    """Add columns that older versions of this dashboard didn't have.

    SQLite's CREATE TABLE IF NOT EXISTS is a no-op when the table already
    exists, so columns added in a newer schema (e.g. ``project``) need an
    ALTER. This is idempotent: ``OperationalError: duplicate column`` on a
    fresh DB is swallowed.
    """
    for table in ("runs", "outcomes"):
        try:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN project TEXT NOT NULL DEFAULT 'default'")
            conn.commit()
        except sqlite3.OperationalError:
            pass
    try:
        conn.execute("ALTER TABLE outcomes ADD COLUMN rerun_count INTEGER NOT NULL DEFAULT 0")
        conn.commit()
    except sqlite3.OperationalError:
        pass


# ---------------------------------------------------------------------------
# Ingest
# ---------------------------------------------------------------------------

def _ingest_dedupe_key(root: Path) -> str:
    """Key for deduping ingests: report file paths, mtimes, sizes, and raw bytes.

    Outcome-only hashing made every run with the same pass/fail/skip layout look
    like one run. Including file contents (and mtime) means a normal re-run that
    rewrites JUnit / Playwright JSON produces a new dashboard row.
    """
    h = hashlib.sha256()
    paths = sorted(root.rglob("junit*.xml"))
    pw = root / "playwright-report.json"
    if pw.is_file():
        paths = sorted([*paths, pw])
    if not paths:
        return hashlib.sha256(b"(no junit*.xml or playwright-report.json)").hexdigest()
    for p in paths:
        try:
            rel = p.resolve().relative_to(root.resolve()).as_posix().encode()
        except ValueError:
            rel = p.name.encode()
        try:
            st = p.stat()
            h.update(rel)
            h.update(str(st.st_mtime_ns).encode())
            h.update(str(st.st_size).encode())
            h.update(p.read_bytes())
        except OSError:
            h.update(rel)
            h.update(b"(unreadable)")
    return h.hexdigest()


def ingest_current_artifacts(project: str = PROJECT, *, force_duplicate: bool = False) -> dict[str, Any]:
    junit = parse_junit_files(ARTIFACTS_ROOT)
    pw_path = ARTIFACTS_ROOT / "playwright-report.json"
    pw = parse_playwright_json(pw_path, ARTIFACTS_ROOT)
    chash = _ingest_dedupe_key(ARTIFACTS_ROOT)
    # UNIQUE(project, content_hash): same report bytes + outcomes → skip.
    # force_duplicate salts the key so two ingests of identical files still insert.
    ingest_hash = (
        hashlib.sha256(f"{chash}|{uuid.uuid4()}".encode()).hexdigest() if force_duplicate else chash
    )
    duration = (pw.duration_ms if pw else 0.0)

    with db_connect() as conn:
        if not force_duplicate:
            existing = conn.execute(
                "SELECT id FROM runs WHERE project = ? AND content_hash = ?",
                (project, ingest_hash),
            ).fetchone()
            if existing:
                return {
                    "ingested": False,
                    "reason": "same ingest key as an existing run (report files and outcomes unchanged vs that run); POST /api/ingest?force_duplicate=true to append anyway",
                    "run_id": existing["id"],
                    "project": project,
                }

        cur = conn.execute(
            """
            INSERT INTO runs (
                project, ts, content_hash,
                junit_total, junit_passed, junit_failed, junit_errors, junit_skipped,
                pw_total, pw_passed, pw_failed, pw_skipped,
                duration_ms
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project,
                datetime.now(timezone.utc).isoformat(),
                ingest_hash,
                junit.totals["tests"],
                junit.totals["passed"],
                junit.totals["failed"],
                junit.totals["errors"],
                junit.totals["skipped"],
                (pw.stats["passed"] + pw.stats["failed"] + pw.stats["skipped"]) if pw else 0,
                pw.stats["passed"] if pw else 0,
                pw.stats["failed"] if pw else 0,
                pw.stats["skipped"] if pw else 0,
                duration,
            ),
        )
        run_id = cur.lastrowid

        cases: list[dict[str, Any]] = []
        for c in junit.cases:
            cases.append({
                "layer": c.layer,
                "suite": c.suite,
                "name": c.name,
                "status": c.status,
                "duration_ms": c.duration_ms,
                "message": c.message,
                "attachments": [],
                "rerun_count": c.rerun_count,
            })
        if pw:
            cases.extend(pw.cases)

        for c in cases:
            conn.execute(
                """
                INSERT INTO outcomes (run_id, project, layer, suite, name, status, duration_ms, message, attachments, rerun_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    project,
                    c["layer"],
                    c.get("suite") or "",
                    c["name"],
                    c["status"],
                    c.get("duration_ms") or 0.0,
                    c.get("message") or "",
                    json.dumps(c.get("attachments") or []),
                    int(c.get("rerun_count") or 0),
                ),
            )
        conn.commit()
    return {
        "ingested": True,
        "run_id": run_id,
        "project": project,
        "tests_recorded": len(cases),
        "force_duplicate": force_duplicate,
    }


# ---------------------------------------------------------------------------
# Analytics queries (project-scoped)
# ---------------------------------------------------------------------------

def latest_run_id(conn: sqlite3.Connection, project: str) -> int | None:
    row = conn.execute(
        "SELECT id FROM runs WHERE project = ? ORDER BY id DESC LIMIT 1",
        (project,),
    ).fetchone()
    return row["id"] if row else None


def recent_runs(conn: sqlite3.Connection, project: str, limit: int = TREND_WINDOW) -> list[sqlite3.Row]:
    return list(
        conn.execute(
            "SELECT * FROM runs WHERE project = ? ORDER BY id DESC LIMIT ?",
            (project, limit),
        )
    )


def newly_failing(conn: sqlite3.Connection, project: str) -> list[dict[str, Any]]:
    rows = list(
        conn.execute(
            "SELECT id FROM runs WHERE project = ? ORDER BY id DESC LIMIT 2",
            (project,),
        )
    )
    if len(rows) < 2:
        return []
    latest_id, prev_id = rows[0]["id"], rows[1]["id"]
    latest_failed = conn.execute(
        "SELECT layer, suite, name, status, message, attachments FROM outcomes WHERE run_id = ? AND status IN ('failed','error')",
        (latest_id,),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for row in latest_failed:
        prev = conn.execute(
            "SELECT status FROM outcomes WHERE run_id = ? AND layer = ? AND suite = ? AND name = ?",
            (prev_id, row["layer"], row["suite"], row["name"]),
        ).fetchone()
        if prev is None or prev["status"] in ("passed", "skipped"):
            out.append(
                {
                    "layer": row["layer"],
                    "suite": row["suite"],
                    "name": row["name"],
                    "status": row["status"],
                    "message": strip_ansi(row["message"] or ""),
                    "attachments": json.loads(row["attachments"] or "[]"),
                }
            )
    return out


def flaky_tests(conn: sqlite3.Connection, project: str, window: int = FLAKE_WINDOW) -> list[dict[str, Any]]:
    """Surface tests that are unreliable in the last ``window`` runs.

    A test is flaky if any of these is true within the window:

    1. **Mixed pass/fail** — it has at least one pass *and* at least one fail.
    2. **Recovered after rerun** — it required pytest-rerunfailures retries
       (``rerun_count > 0`` from the JUnit ``<rerun>`` element) in any run.
    3. **Intermittent presence with failure** — it failed at least once but
       did not appear in every run in the window. This is the canonical case
       for selectively-deselected tests like the dashboard demo failure, and
       for tests that are quarantined/skipped intermittently.

    The ``reason`` field on each row tells the triager which signals fired.
    """
    run_rows = list(
        conn.execute(
            "SELECT id FROM runs WHERE project = ? ORDER BY id DESC LIMIT ?",
            (project, window),
        )
    )
    if not run_rows:
        return []
    run_ids = [r["id"] for r in run_rows]
    n_runs = len(run_ids)
    placeholders = ",".join("?" for _ in run_ids)
    cur = conn.execute(
        f"""
        SELECT layer, suite, name,
               SUM(CASE WHEN status = 'passed' THEN 1 ELSE 0 END) AS passes,
               SUM(CASE WHEN status IN ('failed','error') THEN 1 ELSE 0 END) AS fails,
               SUM(COALESCE(rerun_count, 0)) AS reruns,
               COUNT(*) AS runs_with_outcome
        FROM outcomes
        WHERE run_id IN ({placeholders})
        GROUP BY layer, suite, name
        HAVING (passes > 0 AND fails > 0)
            OR reruns > 0
            OR (fails > 0 AND runs_with_outcome < ?)
        ORDER BY fails DESC, reruns DESC, passes DESC
        """,
        (*run_ids, n_runs),
    )
    out: list[dict[str, Any]] = []
    for r in cur:
        reasons: list[str] = []
        if r["passes"] > 0 and r["fails"] > 0:
            reasons.append("mixed pass/fail")
        if r["reruns"] > 0:
            reasons.append(f"recovered after {r['reruns']} rerun(s)")
        if r["fails"] > 0 and r["runs_with_outcome"] < n_runs:
            reasons.append(f"intermittent ({r['runs_with_outcome']}/{n_runs} runs)")
        out.append(
            {
                "layer": r["layer"],
                "suite": r["suite"],
                "name": r["name"],
                "passes": r["passes"],
                "fails": r["fails"],
                "reruns": r["reruns"],
                "runs_with_outcome": r["runs_with_outcome"],
                "reason": "; ".join(reasons) or "—",
            }
        )
    return out


def _pass_rate_excluding_skips(
    junit_passed: int,
    junit_failed: int,
    junit_errors: int,
    pw_passed: int,
    pw_failed: int,
) -> tuple[float | None, int, int]:
    """Pass rate among tests that had a pass/fail outcome.

    JUnit ``skipped`` (e.g. pytest xfail) and Playwright ``skipped`` are omitted
    from the denominator so expected xfails do not paint the trend red while
    the failure panels correctly show no *failed* cases.
    """
    passed = junit_passed + pw_passed
    failed = junit_failed + junit_errors + pw_failed
    evaluated = passed + failed
    if evaluated == 0:
        return None, passed, failed
    return passed / evaluated, passed, failed


def trend_series(conn: sqlite3.Connection, project: str, limit: int = TREND_WINDOW) -> list[dict[str, Any]]:
    rows = list(reversed(recent_runs(conn, project, limit)))
    out = []
    for r in rows:
        total = r["junit_total"] + r["pw_total"]
        passed = r["junit_passed"] + r["pw_passed"]
        failed = r["junit_failed"] + r["junit_errors"] + r["pw_failed"]
        rate, _, _ = _pass_rate_excluding_skips(
            r["junit_passed"],
            r["junit_failed"],
            r["junit_errors"],
            r["pw_passed"],
            r["pw_failed"],
        )
        evaluated = passed + failed
        out.append(
            {
                "id": r["id"],
                "ts": r["ts"],
                "total": total,
                "evaluated": evaluated,
                "passed": passed,
                "failed": failed,
                "pass_rate": None if rate is None else round(rate, 4),
                "duration_ms": r["duration_ms"],
            }
        )
    return out


def latest_failures(conn: sqlite3.Connection, project: str) -> dict[str, list[dict[str, Any]]]:
    rid = latest_run_id(conn, project)
    if rid is None:
        return {"pytest": [], "playwright": []}
    rows = conn.execute(
        "SELECT layer, suite, name, status, message, attachments FROM outcomes WHERE run_id = ? AND status IN ('failed', 'error')",
        (rid,),
    ).fetchall()
    pytest_fail: list[dict[str, Any]] = []
    pw_fail: list[dict[str, Any]] = []
    for r in rows:
        item = {
            "suite": r["suite"],
            "name": r["name"],
            "status": r["status"],
            "message": strip_ansi(r["message"] or ""),
            "attachments": json.loads(r["attachments"] or "[]"),
        }
        (pytest_fail if r["layer"] == "pytest" else pw_fail).append(item)
    return {"pytest": pytest_fail, "playwright": pw_fail}


def known_projects(conn: sqlite3.Connection) -> list[str]:
    return [r["project"] for r in conn.execute("SELECT DISTINCT project FROM runs ORDER BY project")]


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(title="Test Insights Dashboard", version="2.1.0")


@app.on_event("startup")
def startup() -> None:
    with db_connect():
        pass
    try:
        ingest_current_artifacts()
    except Exception:
        # Best-effort first-boot ingest; UI shows the empty state otherwise.
        pass


@app.post("/api/ingest")
async def api_ingest(
    project: str | None = None,
    force_duplicate: bool = False,
) -> JSONResponse:
    return JSONResponse(
        ingest_current_artifacts(project or PROJECT, force_duplicate=force_duplicate)
    )


@app.get("/api/summary")
async def api_summary(project: str | None = None) -> dict[str, Any]:
    p = project or PROJECT
    with db_connect() as conn:
        return {
            "artifacts_root": str(ARTIFACTS_ROOT),
            "project": p,
            "known_projects": known_projects(conn),
            "trend": trend_series(conn, p),
            "newly_failing": newly_failing(conn, p),
            "flaky": flaky_tests(conn, p),
            "latest_failures": latest_failures(conn, p),
        }


@app.get("/api/runs")
async def api_runs(project: str | None = None, limit: int = TREND_WINDOW) -> dict[str, Any]:
    p = project or PROJECT
    with db_connect() as conn:
        return {"runs": [dict(r) for r in recent_runs(conn, p, limit)]}


@app.get("/api/ai-analysis")
async def api_ai_analysis(project: str | None = None) -> dict[str, Any]:
    p = project or PROJECT
    exists = AI_REPORT_PATH.is_file()
    body = AI_REPORT_PATH.read_text(encoding="utf-8") if exists else ""
    with db_connect() as conn:
        insights = _build_ai_insights(conn, p)
    return {
        "report_path": str(AI_REPORT_PATH),
        "available": exists,
        "content": body,
        "project": p,
        "insights": insights,
    }


@app.delete("/api/runs")
async def api_truncate_runs(project: str | None = None) -> dict[str, Any]:
    """Truncate run history. If ``project`` is omitted, wipes everything."""
    with db_connect() as conn:
        if project:
            conn.execute("DELETE FROM outcomes WHERE project = ?", (project,))
            conn.execute("DELETE FROM runs WHERE project = ?", (project,))
        else:
            conn.execute("DELETE FROM outcomes")
            conn.execute("DELETE FROM runs")
        conn.commit()
    return {"truncated": True, "project": project}


@app.get("/", response_class=HTMLResponse)
async def index(project: str | None = None) -> str:
    p = project or PROJECT
    with db_connect() as conn:
        runs = recent_runs(conn, p, 1)
        if not runs:
            return _render_empty_state(p, known_projects(conn))
        latest = runs[0]
        trend = trend_series(conn, p)
        flaky = flaky_tests(conn, p)
        new_fails = newly_failing(conn, p)
        fails = latest_failures(conn, p)
        projects = known_projects(conn)
    return _render_dashboard_html(
        project=p,
        all_projects=projects,
        latest=latest,
        trend=trend,
        flaky=flaky,
        newly_fail=new_fails,
        failures=fails,
    )


@app.get("/ai-analysis", response_class=HTMLResponse)
async def ai_analysis(project: str | None = None) -> str:
    p = project or PROJECT
    exists = AI_REPORT_PATH.is_file()
    content = AI_REPORT_PATH.read_text(encoding="utf-8") if exists else ""
    with db_connect() as conn:
        insights = _build_ai_insights(conn, p)
        projects = known_projects(conn)
    return _render_ai_report(
        project=p,
        all_projects=projects,
        insights=insights,
        content=content,
        has_report=exists,
    )


# ---------------------------------------------------------------------------
# HTML rendering
# ---------------------------------------------------------------------------

def _bar(value: float, color: str = "#3fb950") -> str:
    pct = max(0.0, min(1.0, value)) * 100
    return f'<div class="bar-track"><div class="bar-fill" style="width:{pct:.1f}%;background:{color}"></div></div>'


def _attachment_inline(att: dict[str, str]) -> str:
    url = att.get("url") or ""
    name = escape(att.get("name", ""))
    ctype = att.get("content_type", "")
    if not url:
        return ""
    if ctype.startswith("video/"):
        return f'<div class="media"><div class="media-label">video — {name}</div><video controls src="{url}"></video></div>'
    if ctype.startswith("image/"):
        return f'<div class="media"><div class="media-label">screenshot — {name}</div><img src="{url}" alt="{name}"/></div>'
    return f'<a class="media-link" href="{url}">{name or url}</a>'


def _failure_card_html(fail: dict[str, Any]) -> str:
    suite = escape(fail.get("suite") or "")
    name = escape(fail.get("name", ""))
    msg = escape(strip_ansi((fail.get("message") or "")[:1500]))
    media = "".join(_attachment_inline(a) for a in fail.get("attachments") or [])
    return (
        f'<li><div class="suite">{suite}</div><div class="case"><code>{name}</code></div>'
        f'<pre>{msg}</pre>{media}</li>'
    )


def _flaky_row(t: dict[str, Any]) -> str:
    return (
        f'<tr><td>{escape(t["layer"])}</td><td>{escape(t["suite"] or "")}</td>'
        f'<td><code>{escape(t["name"])}</code></td>'
        f'<td class="ok">{t["passes"]}</td>'
        f'<td class="bad">{t["fails"]}</td>'
        f'<td>{t.get("reruns", 0)}</td>'
        f'<td>{t["runs_with_outcome"]}</td>'
        f'<td>{escape(t.get("reason", ""))}</td></tr>'
    )


def _trend_sparkline(points: list[dict[str, Any]]) -> str:
    if not points:
        return "(no runs yet)"
    cells = []
    for p in points:
        evaluated = p.get("evaluated", p["passed"] + p["failed"])
        if evaluated == 0:
            title = f"run #{p['id']} — no pass/fail outcomes (all skipped or empty)"
            cells.append(f'<span class="spark-cell" style="background:#30363d" title="{escape(title)}"></span>')
            continue
        pr = p.get("pass_rate")
        if pr is None:
            title = f"run #{p['id']} — n/a"
            cells.append(f'<span class="spark-cell" style="background:#30363d" title="{escape(title)}"></span>')
            continue
        color = "#3fb950" if pr >= 0.95 else ("#d29922" if pr >= 0.7 else "#f85149")
        title = f"run #{p['id']} — {int(pr * 100)}% pass ({p['passed']}/{evaluated} evaluated; {p['total']} incl. skips)"
        cells.append(f'<span class="spark-cell" style="background:{color}" title="{escape(title)}"></span>')
    return f'<div class="spark">{"".join(cells)}</div>'


def _project_picker(current: str, all_projects: list[str]) -> str:
    if not all_projects or all_projects == [current]:
        return f'<span class="badge">project: <strong>{escape(current)}</strong></span>'
    options = "".join(
        f'<option value="{escape(p)}"{" selected" if p == current else ""}>{escape(p)}</option>'
        for p in all_projects
    )
    return (
        '<form method="get" class="project-picker" style="display:inline-block">'
        '<label>Project: <select name="project" onchange="this.form.submit()">'
        f'{options}'
        '</select></label></form>'
    )


def _render_empty_state(project: str, all_projects: list[str]) -> str:
    return f"""<!DOCTYPE html>
<html><head><title>Test insights</title>{_styles()}</head>
<body><h1>Test suite health</h1>
<p class="meta">No runs ingested yet for project <strong>{escape(project)}</strong>.</p>
<p class="meta">{_project_picker(project, all_projects)}</p>
<p class="meta"><a href="/ai-analysis">AI analysis report</a></p>
<p class="meta">Drop a JUnit XML or Playwright JSON under <code>{escape(str(ARTIFACTS_ROOT))}</code> and POST <code>/api/ingest</code> (or restart the dashboard).</p>
</body></html>"""


def _render_dashboard_html(*, project, all_projects, latest, trend, flaky, newly_fail, failures) -> str:
    junit_total = latest["junit_total"]
    pw_total = latest["pw_total"]
    junit_passed = latest["junit_passed"]
    pw_passed = latest["pw_passed"]
    junit_failed = latest["junit_failed"] + latest["junit_errors"]
    pw_failed = latest["pw_failed"]

    pass_rate, _, _ = _pass_rate_excluding_skips(
        latest["junit_passed"],
        latest["junit_failed"],
        latest["junit_errors"],
        latest["pw_passed"],
        latest["pw_failed"],
    )
    total = junit_total + pw_total
    evaluated = (junit_passed + pw_passed) + junit_failed + pw_failed

    flaky_count = len(flaky)
    nf_count = len(newly_fail)
    fail_pytest_html = "".join(_failure_card_html(f) for f in failures["pytest"]) or "<li>(none)</li>"
    fail_pw_html = "".join(_failure_card_html(f) for f in failures["playwright"]) or "<li>(none)</li>"
    new_fail_html = "".join(_failure_card_html(f) for f in newly_fail) or "<li>None — every failing test in the latest run was already failing previously.</li>"
    flaky_rows = "".join(_flaky_row(t) for t in flaky) or '<tr><td colspan="6">No flakes detected in the last window.</td></tr>'
    spark = _trend_sparkline(trend)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <title>Test insights — {escape(project)} run #{latest['id']}</title>
  {_styles()}
</head>
<body>
  <header>
    <h1>Test suite health</h1>
    <div class="meta">
      {_project_picker(project, all_projects)}
      &middot; Run <strong>#{latest['id']}</strong> · {escape(latest['ts'])} ·
      Artifacts: <code>{escape(str(ARTIFACTS_ROOT))}</code> ·
      <a href="/artifacts/">browse files</a> ·
      <a href="/api/summary?project={escape(project)}">JSON</a> ·
      <a href="/ai-analysis">AI analysis report</a>
    </div>
  </header>

  <section>
    <h2>Latest run</h2>
    <div class="cards">
      <div class="card"><div class="label">Pass rate</div><div class="num {'ok' if pass_rate is not None and pass_rate >= 0.95 else ('warn' if pass_rate is not None and pass_rate >= 0.7 else ('bad' if pass_rate is not None else ''))}">{("—" if pass_rate is None else f"{int(pass_rate * 100)}%")}</div>{_bar(pass_rate if pass_rate is not None else 0.0)}<div class="meta">{evaluated} pass/fail · {total} incl. skips</div></div>
      <div class="card"><div class="label">Pytest passed</div><div class="num ok">{junit_passed}</div><div class="meta">of {junit_total}</div></div>
      <div class="card"><div class="label">Pytest failed</div><div class="num bad">{junit_failed}</div></div>
      <div class="card"><div class="label">Playwright passed</div><div class="num ok">{pw_passed}</div><div class="meta">of {pw_total}</div></div>
      <div class="card"><div class="label">Playwright failed</div><div class="num bad">{pw_failed}</div></div>
      <div class="card"><div class="label">Newly failing</div><div class="num {'bad' if nf_count else ''}">{nf_count}</div></div>
      <div class="card"><div class="label">Flaky (last {FLAKE_WINDOW})</div><div class="num {'warn' if flaky_count else ''}">{flaky_count}</div></div>
    </div>
  </section>

  <section>
    <h2>Trend (last {TREND_WINDOW} runs)</h2>
    {spark}
    <p class="meta">Each tile is one run. Rate is passed ÷ (passed + failed); skips (e.g. xfail) are excluded so they do not skew colour. Green ≥ 95%, amber ≥ 70%, red below. Grey = no pass/fail outcomes.</p>
  </section>

  <section>
    <h2>Newly failing in this run</h2>
    <ul class="failures">{new_fail_html}</ul>
  </section>

  <section>
    <h2>Flaky tests in last {FLAKE_WINDOW} runs</h2>
    <p class="meta">A test is flagged when any of: mixed pass/fail, recovered after a rerun, or it failed in some runs but did not appear in every run in the window.</p>
    <table class="flaky">
      <thead><tr><th>Layer</th><th>Suite</th><th>Test</th><th>Passes</th><th>Fails</th><th>Reruns</th><th>Runs</th><th>Why flagged</th></tr></thead>
      <tbody>{flaky_rows}</tbody>
    </table>
  </section>

  <section>
    <h2>Pytest failures in this run</h2>
    <ul class="failures">{fail_pytest_html}</ul>
  </section>

  <section>
    <h2>Playwright failures in this run</h2>
    <p class="meta">Videos / screenshots / traces are inlined when Playwright recorded them.</p>
    <ul class="failures">{fail_pw_html}</ul>
  </section>
</body>
</html>"""


def _build_ai_insights(conn: sqlite3.Connection, project: str) -> dict[str, Any]:
    latest_rows = recent_runs(conn, project, 1)
    trend = trend_series(conn, project, 5)
    flaky = flaky_tests(conn, project, FLAKE_WINDOW)
    newly = newly_failing(conn, project)
    failures = latest_failures(conn, project)
    if not latest_rows:
        return {
            "summary": "No runs ingested yet.",
            "highlights": ["Ingest artifacts first to generate insights."],
            "actions": ["POST /api/ingest after test execution."],
            "counts": {"newly_failing": 0, "flaky": 0, "failures": 0},
        }

    latest = latest_rows[0]
    pass_rate, passed, failed = _pass_rate_excluding_skips(
        latest["junit_passed"],
        latest["junit_failed"],
        latest["junit_errors"],
        latest["pw_passed"],
        latest["pw_failed"],
    )
    current_rate = 0.0 if pass_rate is None else pass_rate
    prev_rate = trend[-2]["pass_rate"] if len(trend) >= 2 else None
    delta = None if prev_rate is None else current_rate - prev_rate

    latest_fail_list = [*failures["pytest"], *failures["playwright"]]
    fail_names = [f.get("name", "") for f in latest_fail_list if f.get("name")]

    highlights: list[str] = []
    highlights.append(
        f"Latest run #{latest['id']} has {int(current_rate * 100)}% pass rate ({passed} passed / {failed} failed among evaluated tests)."
    )
    if delta is not None:
        direction = "up" if delta >= 0 else "down"
        highlights.append(
            f"Pass rate is {direction} {abs(delta) * 100:.1f} points versus previous run."
        )
    if newly:
        highlights.append(f"{len(newly)} newly failing test(s) detected in the latest run.")
    else:
        highlights.append("No newly failing tests versus previous run.")
    if flaky:
        highlights.append(f"{len(flaky)} flaky test(s) observed in the last {FLAKE_WINDOW} runs.")
    else:
        highlights.append(f"No flaky tests detected in the last {FLAKE_WINDOW} runs.")
    if fail_names:
        top = ", ".join(f"`{n}`" for n in fail_names[:3])
        highlights.append(f"Top failures: {top}.")

    actions: list[str] = []
    if newly:
        actions.append("Prioritize newly failing tests first; they are strongest regression signals.")
    if failures["playwright"]:
        actions.append("Use inlined Playwright video/screenshot evidence to speed up UI triage.")
    if flaky:
        actions.append("Quarantine or stabilize flaky tests and track rerun frequency trend.")
    if not actions:
        actions.append("Suite is stable; keep monitoring trend and ingest after each run.")

    return {
        "summary": f"Automated analysis for project '{project}'.",
        "highlights": highlights,
        "actions": actions,
        "counts": {
            "newly_failing": len(newly),
            "flaky": len(flaky),
            "failures": len(latest_fail_list),
        },
    }


def _render_ai_report(*, project: str, all_projects: list[str], insights: dict[str, Any], content: str, has_report: bool) -> str:
    highlights_html = "".join(f"<li>{escape(h)}</li>" for h in insights.get("highlights", []))
    actions_html = "".join(f"<li>{escape(a)}</li>" for a in insights.get("actions", []))
    counts = insights.get("counts", {})
    report_block = (
        f"""<section>
    <h2>Decision journal</h2>
    <div class="meta">
      Source: <code>{escape(str(AI_REPORT_PATH))}</code>
    </div>
    <pre class="report">{escape(content)}</pre>
  </section>"""
        if has_report and content.strip()
        else f"""<section>
    <h2>Decision journal</h2>
    <p class="meta">No readable report content found at <code>{escape(str(AI_REPORT_PATH))}</code>. Set <code>AI_ANALYSIS_REPORT</code> if needed.</p>
  </section>"""
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <title>AI analysis report</title>
  {_styles()}
</head>
<body>
  <header>
    <h1>AI analysis report</h1>
    <div class="meta">
      {_project_picker(project, all_projects)} ·
      <a href="/">Back to dashboard</a> ·
      <a href="/api/ai-analysis?project={escape(project)}">JSON</a>
    </div>
  </header>
  <section>
    <h2>Insights from test results</h2>
    <p class="meta">{escape(insights.get("summary", ""))}</p>
    <div class="cards">
      <div class="card"><div class="label">Newly failing</div><div class="num {'bad' if counts.get('newly_failing', 0) else ''}">{counts.get("newly_failing", 0)}</div></div>
      <div class="card"><div class="label">Flaky tests</div><div class="num {'warn' if counts.get('flaky', 0) else ''}">{counts.get("flaky", 0)}</div></div>
      <div class="card"><div class="label">Current failures</div><div class="num {'bad' if counts.get('failures', 0) else ''}">{counts.get("failures", 0)}</div></div>
    </div>
    <h3>Highlights</h3>
    <ul class="analysis-list">{highlights_html or "<li>No highlights available yet.</li>"}</ul>
    <h3>Recommended actions</h3>
    <ul class="analysis-list">{actions_html or "<li>No actions suggested yet.</li>"}</ul>
  </section>
  {report_block}
</body>
</html>"""


def _styles() -> str:
    return """<style>
    :root { color-scheme: dark; }
    body { font-family: system-ui, -apple-system, sans-serif; margin: 2rem; background: #0d1117; color: #e6edf3; }
    header { border-bottom: 1px solid #30363d; padding-bottom: 1rem; margin-bottom: 1.5rem; }
    h1 { color: #58a6ff; margin: 0; }
    h2 { color: #79c0ff; margin-top: 2rem; }
    section { margin-bottom: 2rem; }
    .meta { color: #8b949e; font-size: 0.9rem; }
    .cards { display: flex; gap: 1rem; flex-wrap: wrap; margin-top: 0.5rem; }
    .card { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 1rem 1.25rem; min-width: 150px; }
    .label { font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.05em; color: #8b949e; }
    .num { font-size: 2rem; font-weight: 700; line-height: 1.1; margin-top: 0.25rem; }
    .ok { color: #3fb950; }
    .bad { color: #f85149; }
    .warn { color: #d29922; }
    .badge { display: inline-block; padding: 0.15rem 0.5rem; background: #161b22; border: 1px solid #30363d; border-radius: 4px; font-size: 0.85rem; }
    .bar-track { background: #21262d; height: 6px; border-radius: 3px; margin-top: 0.5rem; overflow: hidden; }
    .bar-fill { height: 100%; }
    ul.failures { list-style: none; padding: 0; }
    ul.failures li { background: #161b22; border: 1px solid #30363d; margin: 0.5rem 0; padding: 1rem; border-radius: 8px; }
    ul.failures .suite { color: #d2a8ff; font-size: 0.85rem; }
    ul.failures .case { font-size: 0.95rem; margin-bottom: 0.5rem; }
    pre { white-space: pre-wrap; font-size: 0.8rem; color: #c9d1d9; background: #0d1117; padding: 0.6rem; border-radius: 6px; border: 1px solid #21262d; }
    code { background: #21262d; padding: 0.1rem 0.4rem; border-radius: 4px; font-size: 0.85rem; }
    a { color: #58a6ff; }
    .media { margin-top: 0.75rem; padding: 0.5rem; background: #0d1117; border: 1px dashed #30363d; border-radius: 6px; }
    .media-label { font-size: 0.75rem; color: #8b949e; margin-bottom: 0.25rem; }
    .media video, .media img { max-width: 100%; max-height: 320px; border-radius: 4px; display: block; }
    .media-link { display: inline-block; margin-top: 0.5rem; }
    .spark { display: flex; gap: 3px; margin-top: 0.5rem; }
    .spark-cell { display: inline-block; width: 18px; height: 36px; border-radius: 3px; }
    table.flaky { border-collapse: collapse; width: 100%; margin-top: 0.5rem; font-size: 0.9rem; }
    table.flaky th, table.flaky td { border-bottom: 1px solid #21262d; padding: 0.4rem 0.6rem; text-align: left; }
    table.flaky th { color: #8b949e; font-weight: 500; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; }
    select { background: #161b22; color: #e6edf3; border: 1px solid #30363d; border-radius: 4px; padding: 0.2rem 0.4rem; }
    pre.report { white-space: pre-wrap; line-height: 1.4; font-size: 0.9rem; }
    .analysis-list li { margin: 0.35rem 0; }
    </style>"""


app.mount("/artifacts", StaticFiles(directory=str(ARTIFACTS_ROOT), html=True), name="artifacts")
