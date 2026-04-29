---
name: qe-add-test-suite
description: >-
  Scaffold a new pytest-playwright suite with page object and tests following
  the `automation-framework` conventions. Use when adding new UI/API/functional
  test files and app-specific page objects.
---

# Add a New Test Suite

## Steps

1. **Create/extend page object** in:
   `automation-framework/apps/order_processing/ui/pages/<name>_page.py`

```python
from core.ui.base_page import BasePage

class <Name>Page(BasePage):
    def goto(self) -> None:
        self.page.goto(f"{self.config.ui_base_url}/<route>")

    def expect_loaded(self) -> None:
        self.page.get_by_role("heading", name="<Heading>").wait_for()
}
```

Rules:
- Prefer role/text/test-id locators already used by existing pages
- Each public method = one user action or one assertion
- Keep route and selector details inside page objects, not tests

2. **Use existing `pages` fixture** from `automation-framework/conftest.py`:
   - If adding a new page object, register it in:
     - `automation-framework/apps/order_processing/ui/bundle.py`
     - `automation-framework/apps/order_processing/ui/pages/__init__.py`
   - Avoid creating ad-hoc pytest fixtures unless needed across multiple suites

3. **Create tests** under app-aware directories:
   - UI: `automation-framework/apps/order_processing/tests/ui/test_<name>.py`
   - API: `automation-framework/apps/order_processing/tests/api/test_<name>.py`
   - LLM: `automation-framework/apps/order_processing/tests/llm/test_<name>.py`
   - Cross-app/system: `automation-framework/tests/<layer>/test_<name>.py`

```python
import pytest

pytestmark = [pytest.mark.smoke, pytest.mark.customer_order_processing]

def test_<descriptive_name>(pages) -> None:
    pages.<name>.goto()
    pages.<name>.expect_loaded()
```

4. **Use markers intentionally**:
   - `smoke`, `sanity`, `regression`, `api`, `functional`, `llm_eval`
   - `demo_intentional_fail` only for deliberate dashboard demo reds

5. **Verify**:
   - `cd automation-framework`
   - `python3 -m pytest apps/order_processing/tests/ui/test_<name>.py -v`
   - then run broader gate: `python3 -m pytest -m "not demo_intentional_fail"`

## Checklist

- [ ] Page object methods encapsulate locators + interactions
- [ ] Test file is in the correct `apps/order_processing/tests/<layer>/` folder
- [ ] Markers reflect test intent/layer
- [ ] No direct selector-heavy logic in test body
- [ ] Test passes locally with `python3 -m pytest`
