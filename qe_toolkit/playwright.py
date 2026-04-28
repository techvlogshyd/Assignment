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

    def _walk(suites: list[Any], prefix: str = "") -> None:
        for suite in suites:
            title = suite.get("title", "")
            full = f"{prefix} › {title}" if prefix else title
            for spec in suite.get("specs", []):
                spec_title = spec.get("title", "")
                for test in spec.get("tests", []):
                    for res in test.get("results", []):
                        st = res.get("status", "")
                        duration = float(res.get("duration", 0) or 0)
                        out.duration_ms += duration
                        atts = _atts_to_links(res.get("attachments") or [])
                        if st == "passed":
                            out.stats["passed"] += 1
                            out.cases.append({"layer": "playwright", "suite": full, "name": spec_title, "status": "passed", "duration_ms": duration, "message": "", "attachments": atts, "rerun_count": 0})
                        elif st in ("failed", "timedOut"):
                            out.stats["failed"] += 1
                            err = res.get("error") or {}
                            msg = str(err.get("message", ""))[:1500]
                            out.failures.append({"title": full, "name": spec_title, "error": msg, "attachments": atts})
                            out.cases.append({"layer": "playwright", "suite": full, "name": spec_title, "status": "failed", "duration_ms": duration, "message": msg, "attachments": atts, "rerun_count": 0})
                        elif st == "skipped":
                            out.stats["skipped"] += 1
                            out.cases.append({"layer": "playwright", "suite": full, "name": spec_title, "status": "skipped", "duration_ms": duration, "message": "", "attachments": atts, "rerun_count": 0})
            _walk(suite.get("suites", []), full)

    _walk(data.get("suites", []))
    return out
