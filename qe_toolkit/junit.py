"""Vendor-neutral JUnit XML helpers.

Used by:
  * the dashboard, to summarise the latest test run and detect flakes
  * the CI flake-flag script, to emit GitHub Actions warnings

Any test runner that emits JUnit XML (pytest, vitest --reporter=junit, jest,
go test -junit, ginkgo, mocha-junit-reporter, dotnet test --logger junit, etc.)
is parsed by these functions without modification.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class JUnitCase:
    layer: str = "pytest"
    suite: str = ""
    name: str = ""
    status: str = "passed"  # passed | failed | error | skipped
    duration_ms: float = 0.0
    message: str = ""
    rerun_count: int = 0


@dataclass
class JUnitSummary:
    files: list[str] = field(default_factory=list)
    totals: dict[str, int] = field(default_factory=lambda: {"tests": 0, "passed": 0, "failed": 0, "errors": 0, "skipped": 0})
    failures: list[dict[str, Any]] = field(default_factory=list)
    cases: list[JUnitCase] = field(default_factory=list)


def _rel_to_root(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)


def parse_junit_files(root: Path, layer: str = "pytest") -> JUnitSummary:
    """Aggregate all ``junit*.xml`` files found under ``root`` (recursive).

    ``layer`` is recorded on each emitted case so the dashboard can group
    cases by source (pytest, vitest, etc.) when consumers want a single
    timeline across multiple suites.
    """
    summary = JUnitSummary()
    files = sorted(root.rglob("junit*.xml"))
    summary.files = [_rel_to_root(f, root) for f in files]

    for fp in files:
        try:
            tree = ET.parse(fp)
        except (ET.ParseError, OSError):
            continue
        for case in tree.getroot().iter("testcase"):
            name = case.attrib.get("name", "")
            classname = case.attrib.get("classname", "")
            duration_ms = float(case.attrib.get("time", 0) or 0) * 1000.0
            rerun_count = sum(1 for _ in case.iter("rerun")) + sum(
                1 for _ in case.iter("flakyFailure")
            )
            failure_el = case.find("failure")
            error_el = case.find("error")
            skipped_el = case.find("skipped")
            if failure_el is not None:
                msg = (failure_el.attrib.get("message") or (failure_el.text or ""))[:1500]
                summary.totals["failed"] += 1
                summary.failures.append(
                    {"suite": classname, "case": name, "message": msg, "source_file": _rel_to_root(fp, root)}
                )
                summary.cases.append(JUnitCase(layer, classname, name, "failed", duration_ms, msg, rerun_count))
            elif error_el is not None:
                msg = (error_el.attrib.get("message") or (error_el.text or ""))[:1500]
                summary.totals["errors"] += 1
                summary.failures.append(
                    {"suite": classname, "case": name, "message": msg, "source_file": _rel_to_root(fp, root)}
                )
                summary.cases.append(JUnitCase(layer, classname, name, "error", duration_ms, msg, rerun_count))
            elif skipped_el is not None:
                summary.totals["skipped"] += 1
                summary.cases.append(JUnitCase(layer, classname, name, "skipped", duration_ms, skipped_el.attrib.get("message", ""), rerun_count))
            else:
                summary.totals["passed"] += 1
                summary.cases.append(JUnitCase(layer, classname, name, "passed", duration_ms, "", rerun_count))

    summary.totals["tests"] = (
        summary.totals["passed"]
        + summary.totals["failed"]
        + summary.totals["errors"]
        + summary.totals["skipped"]
    )
    return summary


def find_flakes(root: Path) -> Iterator[dict[str, Any]]:
    """Yield testcases that passed only after at least one rerun.

    Definition of "flaky" for the CI gate: ``<rerun>`` or ``<flakyFailure>``
    child present, but the final outcome was a pass (no ``<failure>`` or
    ``<error>``). pytest-rerunfailures emits ``<rerun>``; surefire emits
    ``<flakyFailure>``. This script accepts either.
    """
    targets: Iterable[Path] = [root] if root.is_file() else sorted(root.rglob("junit*.xml"))
    for fp in targets:
        try:
            tree = ET.parse(fp)
        except (ET.ParseError, OSError) as exc:
            yield {
                "kind": "parse_error",
                "file": str(fp),
                "message": str(exc),
            }
            continue
        for case in tree.getroot().iter("testcase"):
            rerun = sum(1 for _ in case.iter("rerun")) + sum(
                1 for _ in case.iter("flakyFailure")
            )
            final_failed = case.find("failure") is not None or case.find("error") is not None
            if rerun > 0 and not final_failed:
                yield {
                    "kind": "flaky_pass",
                    "suite": case.attrib.get("classname", ""),
                    "name": case.attrib.get("name", ""),
                    "rerun_count": rerun,
                    "file": str(fp),
                }
