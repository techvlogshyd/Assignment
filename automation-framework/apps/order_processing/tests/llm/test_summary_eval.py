"""LLM eval smoke using reusable runner + optional DeepEval judge hook."""

from __future__ import annotations

from pathlib import Path

import pytest

from core.llm import EvalRunner
from core.llm.deepeval_adapter import run_answer_relevancy_assert

pytestmark = [pytest.mark.llm_eval, pytest.mark.regression, pytest.mark.customer_order_processing]


def test_answer_relevancy_smoke() -> None:
    """Minimal Answer Relevancy case (calls hosted judge model when enabled)."""
    run_answer_relevancy_assert(
        input_text="What is two plus two?",
        actual_output="The sum is four.",
        threshold=0.4,
    )


def test_golden_dataset_runner_smoke() -> None:
    dataset = EvalRunner.load_dataset(
        Path(__file__).resolve().parents[2] / "llm" / "datasets" / "order_processing_summary_eval.yaml"
    )
    # Stub model for deterministic CI smoke.
    runner = EvalRunner(lambda prompt: '{"summary":"30 days with invoice","policy_days":30}')
    result = runner.run_case(dataset[0])
    assert result.status in ("pass", "warning")
