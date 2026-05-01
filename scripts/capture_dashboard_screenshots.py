"""One-off helper to capture dashboard screenshots for VIDEO_WALKTHROUGH_NARRATION.md.

Usage:
    python scripts/capture_dashboard_screenshots.py

Requires the dashboard to be running on http://localhost:4000 and Playwright
chromium installed (it is, via automation-framework).
"""
from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parents[1] / "docs" / "screenshots"
DASHBOARD = "http://localhost:4000"


def capture(name: str, url: str, viewport: tuple[int, int] = (1440, 900)) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    target = OUT / f"{name}.png"
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(
            viewport={"width": viewport[0], "height": viewport[1]},
            device_scale_factor=2,
            color_scheme="dark",
        )
        page = context.new_page()
        page.goto(url, wait_until="networkidle")
        page.wait_for_timeout(400)
        page.screenshot(path=str(target), full_page=True)
        browser.close()
    print(f"wrote {target}  ({target.stat().st_size // 1024} KB)")
    return target


def main() -> int:
    capture("dashboard-overview-with-failures", f"{DASHBOARD}/")
    capture("dashboard-ai-analysis", f"{DASHBOARD}/ai-analysis")
    return 0


if __name__ == "__main__":
    sys.exit(main())
