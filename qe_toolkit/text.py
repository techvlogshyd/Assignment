"""Plain-text helpers for normalizing test artefacts."""

from __future__ import annotations

import re

# CSI / common control sequences (Playwright and Jest colour expect() diffs).
_ANSI_RE = re.compile(r"\x1b(?:\[[\d;:]*[ -/]*[@-~]|\][^\x07]*\x07|[@-_])")


def strip_ansi(text: str) -> str:
    """Remove ANSI terminal escapes so failure messages render in HTML and JSON."""
    if not text:
        return text
    return _ANSI_RE.sub("", text)
