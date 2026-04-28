#!/usr/bin/env python3
"""CLI wrapper around ``qe_toolkit.coverage_gate`` for use in CI."""

from __future__ import annotations

import sys
from pathlib import Path

# Make qe_toolkit importable when this script is invoked from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qe_toolkit.coverage_gate import check_against_baseline  # noqa: E402


def main() -> int:
    if len(sys.argv) != 3:
        print(
            "usage: check_coverage_vs_baseline.py coverage.xml baseline.txt",
            file=sys.stderr,
        )
        return 2
    cov_path, baseline_path = sys.argv[1], sys.argv[2]
    passed, actual, baseline = check_against_baseline(cov_path, baseline_path)
    print(f"Line coverage: {actual}% (baseline floor {baseline}%)")
    if not passed:
        print(
            f"ERROR: coverage {actual}% is below baseline {baseline}%. "
            "Raise the baseline only when deliberately improving coverage.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
