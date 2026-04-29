"""
Deliberately failing test for Monday-morning triage demo (assignment Part 2).
CI excludes this marker; run the full suite locally to include it.
"""


import pytest


@pytest.mark.demo_intentional_fail
def test_demo_intentional_fail_dashboard_triage_anchor() -> None:
    assert 2 + 2 == 5
