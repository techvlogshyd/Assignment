"""DeepEval integration — optional dependency; safe without ``deepeval`` installed."""

from __future__ import annotations

import os
from typing import Optional


def llm_eval_skip_reason() -> Optional[str]:
    """Return None if LLM eval tests should run; otherwise a pytest skip reason."""
    if os.environ.get("RUN_LLM_EVAL", "").strip().lower() not in ("1", "true", "yes"):
        return "Set RUN_LLM_EVAL=1 to enable llm_eval-marked tests"
    try:
        import deepeval  # noqa: F401
    except ImportError:
        return "Install extras: pip install -r requirements-llm.txt"
    return None


def skip_if_llm_eval_not_configured() -> None:
    """Call at start of ``llm_eval`` tests."""
    import pytest

    reason = llm_eval_skip_reason()
    if reason:
        pytest.skip(reason)


def run_answer_relevancy_assert(
    input_text: str,
    actual_output: str,
    *,
    threshold: float = 0.5,
) -> None:
    """DeepEval Answer Relevancy — LLM-as-judge (requires ``OPENAI_API_KEY`` or provider env)."""
    skip_if_llm_eval_not_configured()
    import pytest

    if not os.environ.get("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY not set — skipping LLM-as-judge metric")

    from deepeval import assert_test
    from deepeval.metrics import AnswerRelevancyMetric
    from deepeval.test_case import LLMTestCase

    assert_test(
        LLMTestCase(input=input_text, actual_output=actual_output),
        [AnswerRelevancyMetric(threshold=threshold)],
    )
