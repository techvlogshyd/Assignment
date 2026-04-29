from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class LLMGoldenCase(BaseModel):
    case_id: str
    prompt: str
    answer: str
    expected_keywords: list[str] = []
    forbidden_claims: list[str] = []
    min_relevance: float = 0.7
    min_completeness: float = 0.6
    output_schema: Optional[dict] = None


class EvalScore(BaseModel):
    metric: str
    score: float = Field(ge=0.0, le=1.0)
    details: str = ""


class LLMEvalResult(BaseModel):
    case_id: str
    status: Literal["pass", "warning", "fail"]
    scores: list[EvalScore]
    failures: list[str] = []

