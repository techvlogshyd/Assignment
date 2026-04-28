#!/usr/bin/env python3
"""CLI wrapper around ``qe_toolkit.junit.find_flakes`` for use in CI.

Emits one ``::warning::`` annotation per flaky test (rerun-then-passed) and a
summary ``::notice::``. Always exits 0 — this is a *visibility* gate, not a
failure gate; flakes are surfaced but do not block the merge.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qe_toolkit.junit import find_flakes  # noqa: E402


def main() -> int:
    targets = [Path(p) for p in sys.argv[1:]] or [Path("test-results")]
    flake_count = 0
    for target in targets:
        for ev in find_flakes(target):
            if ev["kind"] == "parse_error":
                print(f"::warning::Could not parse {ev['file']}: {ev['message']}")
                continue
            flake_count += 1
            print(
                f"::warning title=Flaky test::"
                f"{ev['suite']}::{ev['name']} passed only after {ev['rerun_count']} rerun(s)"
            )
    if flake_count:
        print(f"::notice::{flake_count} flaky test(s) detected — see warnings above.")
    else:
        print("No flakes detected in JUnit reports.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
