from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, computed_field


class EvalCase(BaseModel):
    id: str = Field(min_length=3, max_length=80, pattern=r"^[a-z0-9_-]+$")
    description: str = Field(min_length=1, max_length=200)
    user_id: str = "demo-user"
    input: str = Field(min_length=1, max_length=500)
    expected_scenario: Literal[
        "return_failure",
        "billing_dispute",
        "nearby_station",
        "profile_update",
        "unknown",
    ]
    expected_safe_fallback: bool = False
    required_tools: list[str] = Field(default_factory=list)
    forbidden_tools: list[str] = Field(default_factory=list)
    response_contains: list[str] = Field(default_factory=list)


class EvalCaseResult(BaseModel):
    case_id: str
    passed: bool
    actual_scenario: str
    executed_tools: list[str]
    failures: list[str]


class EvalReport(BaseModel):
    results: list[EvalCaseResult]

    @computed_field
    @property
    def total(self) -> int:
        return len(self.results)

    @computed_field
    @property
    def passed(self) -> int:
        return sum(result.passed for result in self.results)

    @computed_field
    @property
    def pass_rate(self) -> float:
        return round(self.passed / self.total, 4) if self.total else 0.0
