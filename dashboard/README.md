# Part 2 — Test Insights Dashboard

This directory is yours to build in.

Your task is to build a working internal dashboard that an engineer would open on Monday morning to understand the health of the test suite.

**Hard constraints:**
- Real working app (not a static report).
- Ingests results from your Part 1 test runs (Playwright JSON/traces/videos, pytest JUnit/JSON).
- Vendor-neutral OSS only. No SaaS test-reporting services.
- Must come up with a single `docker-compose up` (or one documented command) on a fresh machine.

**Everything else is your call.** Tech stack, schema, which charts and filters to build first, whether to add auth or multi-project support — you decide and defend your decisions in the walkthrough video.

A great dashboard makes it easy to answer:
- What is failing right now, and is it newly failing or chronically flaky?
- How are pass rate, flake rate, and duration trending over the last N runs?
- For an E2E failure, can I watch the step video and see the screenshot without leaving the dashboard?

We score judgment over breadth. A focused dashboard that nails 2-3 of the above is better than a sprawling one that does many things poorly.
