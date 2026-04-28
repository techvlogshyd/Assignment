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

ARTIFACTS_ROOT = Path(os.environ.get("ARTIFACTS_ROOT", "../test-results")).resolve()
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
            # Column already exists.
            pass


# ---------------------------------------------------------------------------
# Ingest
# ---------------------------------------------------------------------------

def _content_hash(junit_summary, pw_summary) -> str:
    h = hashlib.sha256()
    h.update(json.dumps(junit_summary.totals, sort_keys=True).encode())
    for c in junit_summary.cases:
        h.update(f"{c.layer}|{c.suite}|{c.name}|{c.status}".encode())
    if pw_summary:
        h.update(json.dumps(pw_summary.stats, sort_keys=True).encode())
        for c in pw_summary.cases:
            h.update(f"{c['layer']}|{c['suite']}|{c['name']}|{c['status']}".encode())
    return h.hexdigest()


def ingest_current_artifacts(project: str = PROJECT) -> dict[str, Any]:
    junit = parse_junit_files(ARTIFACTS_ROOT)
    pw_path = ARTIFACTS_ROOT / "playwright-report.json"
    pw = parse_playwright_json(pw_path, ARTIFACTS_ROOT)
    chash = _content_hash(junit, pw)
    duration = (pw.duration_ms if pw else 0.0)

    with db_connect() as conn:
        existing = conn.execute(
            "SELECT id FROM runs WHERE project = ? AND content_hash = ?",
            (project, chash),
        ).fetchone()
        if existing:
            return {"ingested": False, "reason": "identical content hash", "run_id": existing["id"], "project": project}

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
                chash,
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
            cases.append({"layer": c.layer, "suite": c.suite, "name": c.name, "status": c.status, "duration_ms": c.duration_ms, "message": c.message, "attachments": []})
        if pw:
            cases.extend(pw.cases)

        for c in cases:
            conn.execute(
                """
                INSERT INTO outcomes (run_id, project, layer, suite, name, status, duration_ms, message, attachments)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                ),
            )
        conn.commit()
    return {"ingested": True, "run_id": run_id, "project": project, "tests_recorded": len(cases)}


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
                    "message": row["message"],
                    "attachments": json.loads(row["attachments"] or "[]"),
                }
            )
    return out


def flaky_tests(conn: sqlite3.Connection, project: str, window: int = FLAKE_WINDOW) -> list[dict[str, Any]]:
    run_rows = list(
        conn.execute(
            "SELECT id FROM runs WHERE project = ? ORDER BY id DESC LIMIT ?",
            (project, window),
        )
    )
    if not run_rows:
        return []
    run_ids = [r["id"] for r in run_rows]
    placeholders = ",".join("?" for _ in run_ids)
    cur = conn.execute(
        f"""
        SELECT layer, suite, name,
               SUM(CASE WHEN status = 'passed' THEN 1 ELSE 0 END) AS passes,
               SUM(CASE WHEN status IN ('failed','error') THEN 1 ELSE 0 END) AS fails,
               COUNT(*) AS runs_with_outcome
        FROM outcomes
        WHERE run_id IN ({placeholders})
        GROUP BY layer, suite, name
        HAVING passes > 0 AND fails > 0
        ORDER BY fails DESC, passes DESC
        """,
        run_ids,
    )
    return [
        {"layer": r["layer"], "suite": r["suite"], "name": r["name"], "passes": r["passes"], "fails": r["fails"], "runs_with_outcome": r["runs_with_outcome"]}
        for r in cur
    ]


def trend_series(conn: sqlite3.Connection, project: str, limit: int = TREND_WINDOW) -> list[dict[str, Any]]:
    rows = list(reversed(recent_runs(conn, project, limit)))
    out = []
    for r in rows:
        total = r["junit_total"] + r["pw_total"]
        passed = r["junit_passed"] + r["pw_passed"]
        failed = r["junit_failed"] + r["junit_errors"] + r["pw_failed"]
        pass_rate = (passed / total) if total else 0.0
        out.append({"id": r["id"], "ts": r["ts"], "total": total, "passed": passed, "failed": failed, "pass_rate": round(pass_rate, 4), "duration_ms": r["duration_ms"]})
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
        item = {"suite": r["suite"], "name": r["name"], "status": r["status"], "message": r["message"], "attachments": json.loads(r["attachments"] or "[]")}
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
async def api_ingest(project: str | None = None) -> JSONResponse:
    return JSONResponse(ingest_current_artifacts(project or PROJECT))


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
    msg = escape((fail.get("message") or "")[:1500])
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
        f'<td>{t["runs_with_outcome"]}</td></tr>'
    )


def _trend_sparkline(points: list[dict[str, Any]]) -> str:
    if not points:
        return "(no runs yet)"
    cells = []
    for p in points:
        if p["total"] == 0:
            cells.append('<span class="spark-cell" style="background:#30363d" title="no tests"></span>')
            continue
        pct = p["pass_rate"]
        color = "#3fb950" if pct >= 0.95 else ("#d29922" if pct >= 0.7 else "#f85149")
        title = f"run #{p['id']} — {int(pct*100)}% pass ({p['passed']}/{p['total']})"
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
<p class="meta">Drop a JUnit XML or Playwright JSON under <code>{escape(str(ARTIFACTS_ROOT))}</code> and POST <code>/api/ingest</code> (or restart the dashboard).</p>
</body></html>"""


def _render_dashboard_html(*, project, all_projects, latest, trend, flaky, newly_fail, failures) -> str:
    junit_total = latest["junit_total"]
    pw_total = latest["pw_total"]
    junit_passed = latest["junit_passed"]
    pw_passed = latest["pw_passed"]
    junit_failed = latest["junit_failed"] + latest["junit_errors"]
    pw_failed = latest["pw_failed"]

    pass_rate = 0.0
    total = junit_total + pw_total
    if total:
        pass_rate = (junit_passed + pw_passed) / total

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
      <a href="/api/summary?project={escape(project)}">JSON</a>
    </div>
  </header>

  <section>
    <h2>Latest run</h2>
    <div class="cards">
      <div class="card"><div class="label">Pass rate</div><div class="num {'ok' if pass_rate >= 0.95 else ('warn' if pass_rate >= 0.7 else 'bad')}">{int(pass_rate*100)}%</div>{_bar(pass_rate)}</div>
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
    <p class="meta">Each tile is one run. Green ≥ 95% pass, amber ≥ 70%, red below.</p>
  </section>

  <section>
    <h2>Newly failing in this run</h2>
    <ul class="failures">{new_fail_html}</ul>
  </section>

  <section>
    <h2>Flaky tests (mixed pass/fail in last {FLAKE_WINDOW} runs)</h2>
    <table class="flaky">
      <thead><tr><th>Layer</th><th>Suite</th><th>Test</th><th>Passes</th><th>Fails</th><th>Runs</th></tr></thead>
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
    </style>"""


app.mount("/artifacts", StaticFiles(directory=str(ARTIFACTS_ROOT), html=True), name="artifacts")
