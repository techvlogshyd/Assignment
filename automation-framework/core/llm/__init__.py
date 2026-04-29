"""Optional LLM evaluation (DeepEval-style). Tests skip unless deps + ``RUN_LLM_EVAL``."""

from core.llm.deepeval_adapter import (
    llm_eval_skip_reason,
    run_answer_relevancy_assert,
    skip_if_llm_eval_not_configured,
)
from core.llm.evaluators import (
    completeness_evaluator,
    groundedness_evaluator,
    relevance_evaluator,
    safety_validator,
    schema_validator,
)
from core.llm.models import EvalScore, LLMGoldenCase, LLMEvalResult
from core.llm.runner import EvalRunner

__all__ = [
    "EvalRunner",
    "EvalScore",
    "LLMGoldenCase",
    "LLMEvalResult",
    "llm_eval_skip_reason",
    "completeness_evaluator",
    "groundedness_evaluator",
    "relevance_evaluator",
    "run_answer_relevancy_assert",
    "safety_validator",
    "schema_validator",
    "skip_if_llm_eval_not_configured",
]
