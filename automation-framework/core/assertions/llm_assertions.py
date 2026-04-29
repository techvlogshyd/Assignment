from __future__ import annotations

from core.llm.result_model import LLMEvalResult


def assert_llm_pass_or_warning(result: LLMEvalResult) -> None:
    if result.status == "fail":
        raise AssertionError(f"LLM evaluation failed: {result.failures}")
