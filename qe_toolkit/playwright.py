"""Playwright JSON reporter parser.

The shape we expect is the standard ``--reporter=json`` output:
``suites -> specs -> tests -> results -> attachments``. We tolerate missing
fields; flaky / interrupted / timedOut all collapse into ``failed`` for
dashboard display.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from qe_toolkit.text import strip_ansi


@dataclass
class PWSummary:
    stats: dict[str, int] = field(default_factory=lambda: {"passed": 0, "failed": 0, "skipped": 0})
    failures: list[dict[str, Any]] = field(default_factory=list)
    cases: list[dict[str, Any]] = field(default_factory=list)
    duration_ms: float = 0.0
    source: str = ""


def _try_relative_artifact(abs_path: str, artifacts_root: Path) -> str | None:
    if not abs_path:
        return None
    try:
        p = Path(abs_path).resolve()
    except (OSError, ValueError):
        return None
    try:
        rel = p.relative_to(artifacts_root.resolve())
        return f"/artifacts/{rel.as_posix()}"
    except ValueError:
        marker = "test-results/"
        idx = abs_path.find(marker)
        if idx == -1:
            return None
        return f"/artifacts/{abs_path[idx + len(marker):]}"


def parse_playwright_json(path: Path, artifacts_root: Path) -> PWSummary | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    out = PWSummary()
    try:
        out.source = str(path.resolve().relative_to(artifacts_root.resolve()))
    except ValueError:
        out.source = str(path)

    def _atts_to_links(atts: Iterable[dict[str, Any]] | None) -> list[dict[str, str]]:
        result: list[dict[str, str]] = []
        for att in atts or []:
            path_str = att.get("path") or ""
            result.append(
                {
                    "name": att.get("name", ""),
                    "content_type": att.get("contentType", ""),
                    "path": path_str,
                    "url": _try_relative_artifact(path_str, artifacts_root) or "",
                }
            )
        return result

    latest_by_test: dict[tuple[str, str], dict[str, Any]] = {}

    def _walk(suites: list[Any], prefix: str = "") -> None:
        for suite in suites:
            title = suite.get("title", "")
            full = f"{prefix} › {title}" if prefix else title
            for spec in suite.get("specs", []):
                spec_title = spec.get("title", "")
                for test in spec.get("tests", []):
                    results = test.get("results", []) or []
                    for res in results:
                        out.duration_ms += float(res.get("duration", 0) or 0)
                    if not results:
                        continue
                    # Use final attempt for status accounting to avoid retry double counting.
                    res = results[-1]
                    st = res.get("status", "")
                    duration = float(res.get("duration", 0) or 0)
                    atts = _atts_to_links(res.get("attachments") or [])
                    status = "skipped"
                    msg = ""
                    if st == "passed":
                        status = "passed"
                    elif st in ("failed", "timedOut"):
                        status = "failed"
                        err = res.get("error") or {}
                        msg = strip_ansi(str(err.get("message", "")))[:1500]
                    elif st == "skipped":
                        status = "skipped"
                    latest_by_test[(full, spec_title)] = {
                        "layer": "playwright",
                        "suite": full,
                        "name": spec_title,
                        "status": status,
                        "duration_ms": duration,
                        "message": msg,
                        "attachments": atts,
                        "rerun_count": 0,
                    }
            _walk(suite.get("suites", []), full)

    _walk(data.get("suites", []))
    for case in latest_by_test.values():
        out.cases.append(case)
        if case["status"] == "passed":
            out.stats["passed"] += 1
        elif case["status"] == "failed":
            out.stats["failed"] += 1
            out.failures.append(
                {
                    "title": case["suite"],
                    "name": case["name"],
                    "error": case["message"],
                    "attachments": case["attachments"],
                }
            )
        else:
            out.stats["skipped"] += 1
    return out
