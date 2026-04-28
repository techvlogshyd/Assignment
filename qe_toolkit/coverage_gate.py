"""Coverage-XML based gate, callable from CI or any project.

The contract: a customer ships a ``coverage.xml`` (Cobertura-compatible) and a
``coverage_baseline.txt`` containing a single floating-point percentage. CI
fails if the actual line coverage drops below the baseline. Raising the
baseline is an explicit, reviewable diff.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path


def line_coverage_percent(coverage_xml_path: str | Path) -> float:
    tree = ET.parse(str(coverage_xml_path))
    root = tree.getroot()
    line_rate = float(root.attrib.get("line-rate", "0"))
    return round(line_rate * 100, 2)


def read_baseline(baseline_path: str | Path) -> float:
    return float(Path(baseline_path).read_text(encoding="utf-8").strip())


def check_against_baseline(
    coverage_xml_path: str | Path, baseline_path: str | Path
) -> tuple[bool, float, float]:
    """Return ``(passed, actual, baseline)``.

    ``passed`` is True iff actual + 0.01 >= baseline (the small tolerance
    avoids false negatives on cobertura's 4-decimal rounding).
    """
    actual = line_coverage_percent(coverage_xml_path)
    baseline = read_baseline(baseline_path)
    return (actual + 0.01 >= baseline, actual, baseline)
