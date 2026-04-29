from __future__ import annotations

from pathlib import Path
from typing import Callable

import yaml

from core.llm.evaluators import (
    completeness_evaluator,
    groundedness_evaluator,
    relevance_evaluator,
    safety_validator,
    schema_validator,
)
from core.llm.models import LLMGoldenCase, LLMEvalResult


LLMCallable = Callable[[str], str]


class EvalRunner:
    def __init__(self, llm_callable: LLMCallable, *, warning_threshold: float = 0.65, fail_threshold: float = 0.5) -> None:
        self.llm_callable = llm_callable
        self.warning_threshold = warning_threshold
        self.fail_threshold = fail_threshold

    def run_case(self, case: LLMGoldenCase) -> LLMEvalResult:
        output = self.llm_callable(case.prompt)
        scores = [
            relevance_evaluator(output, case.expected_keywords),
            completeness_evaluator(output),
            groundedness_evaluator(output, case.forbidden_claims),
            schema_validator(output, list(case.output_schema.keys()) if case.output_schema else None),
            safety_validator(output),
        ]
        avg = sum(s.score for s in scores) / len(scores)
        if avg < self.fail_threshold:
            status = "fail"
        elif avg < self.warning_threshold:
            status = "warning"
        else:
            status = "pass"
        failures = [f"{s.metric}:{s.details}" for s in scores if s.score < case.min_completeness and s.metric == "completeness"]
        return LLMEvalResult(case_id=case.case_id, status=status, scores=scores, failures=failures)

    @staticmethod
    def load_dataset(path: Path) -> list[LLMGoldenCase]:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or []
        return [LLMGoldenCase.model_validate(item) for item in raw]

