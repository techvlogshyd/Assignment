---
name: qe-add-llm-eval
description: >-
  Add a new LLM evaluation dataset and wire it into the eval runner. Use when
  adding golden datasets, evaluation criteria, LLM judge logic, or extending
  the Python eval pipeline.
---

# Add an LLM Evaluation

## Steps

1. **Create the dataset** under app scope:
   - `automation-framework/apps/order_processing/llm/datasets/<name>.yaml`
   - Optional JSON mirror if your loader expects it

```yaml
- input: "The prompt or question sent to the LLM"
  expected_criteria:
    - "must mention <keyword1>"
    - "must mention <keyword2>"
  sample_answer: "A known-good answer for offline testing"
```

Rules:
- Each criterion starts with `must mention` followed by the key concept
- `sample_answer` should pass all criteria (used for offline/CI runs)
- Add at least 3-5 items per dataset for meaningful coverage

2. **Add or tune evaluators** in:
   - `automation-framework/core/llm/evaluators/`
   - `automation-framework/core/llm/judge/llm_judge.py`
   - keep output compatible with `core/llm/result_model.py`

3. **Wire into runner/tests**:
   - Runner entrypoints: `automation-framework/core/llm/runner.py` and `eval_runner.py`
   - App tests: `automation-framework/apps/order_processing/tests/llm/test_summary_eval.py`
   - Shared fixtures: `automation-framework/shared/fixtures/llm_fixtures.py`

4. **Verify**:
   - `cd automation-framework`
   - `pip install -r requirements-llm.txt` (if not installed)
   - `RUN_LLM_EVAL=1 python3 -m pytest -m llm_eval -v`

## Criteria Writing Guide

| Good Criterion | Bad Criterion |
|---|---|
| `must mention deadline` | `must be good` |
| `must mention error code` | `must be helpful` |
| `must mention user name` | `must sound professional` |

Criteria must be objectively checkable. If a human can't agree on pass/fail, the judge can't either.
