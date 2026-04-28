"""Reusable QE building blocks for any FastAPI/ASGI customer solution.

The Order Processing app uses this package via its conftest, scripts, and
dashboard. A new customer onboarding to this framework imports the same
fixtures and analytics helpers — see docs/ONBOARDING_NEW_CUSTOMER.md.
"""

__version__ = "0.1.0"

__all__ = ["junit", "playwright", "pytest_fixtures", "coverage_gate"]
